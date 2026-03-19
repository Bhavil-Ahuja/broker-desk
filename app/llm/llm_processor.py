from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from app.services.state_machine import ConversationState
from kafka import KafkaProducer
import json
import re

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def extract_requirements(llm, text):
    """Separate LLM call just for extraction"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a JSON extraction API. Your ONLY job is to return a JSON object.

ABSOLUTE RULES:
1. Return ONLY a single-line JSON object: {{"key": "value"}}
2. NO explanations. NO examples. NO lists. NO numbered items. NO extra text.
3. Extract ONLY what the user explicitly mentions in THIS message.
4. If nothing is mentioned, return: {{}}

Fields (include ONLY if explicitly mentioned):
- bhk: number from "X BHK" (e.g. "4 BHK" → 4)
- furnishing: MUST be exactly "semi" or "full" only. "Semi Furnished" / "semi furnished" → "semi". "Fully furnished" → "full".
- preferred_locality: area/locality name as-is (e.g. "HSR Layout", "Koramangala")
- budget_max: rupees number. "Max 70k" / "70k" / "70 K" → 70000. "40 lakhs" → 4000000. "upto 50k" → 50000.
- move_in_date: "2026-MM-DD" only. "April" / "Move in from April" → "2026-04-01". "March" → "2026-03-01".
- other_requirements: other text

WRONG OUTPUT EXAMPLES (DO NOT DO THIS):
❌ "1. User says..." (numbered list)
❌ "Based on the rules..." (explanation)
❌ Multiple JSON objects

CORRECT OUTPUT (ONLY THIS):
✅ {{"bhk": 2}}
✅ {{}}
✅ {{"bhk": 1, "preferred_locality": "Indiranagar"}}
✅ {{"bhk": 4, "preferred_locality": "HSR Layout", "furnishing": "semi", "budget_max": 70000, "move_in_date": "2026-04-01"}}

Now extract from the user's message below. Return ONLY JSON:"""),
        ("user", "{message}")
    ])

    chain = prompt | llm
    result = chain.invoke({"message": text})
    return result.content.strip()


def process_message(lead_id, text, db_session):
    print(f"Processing - Lead ID: {lead_id}, Message: {text}")

    llm = ChatOllama(model="mistral", temperature=0.0)
    
    # Fetch conversation history (last 10 messages for context)
    from app.models import Conversation, Requirements, Lead
    conversation_history = db_session.query(Conversation)\
        .filter_by(lead_id=lead_id)\
        .order_by(Conversation.created_at.desc())\
        .limit(10)\
        .all()
    conversation_history.reverse()  # Put in chronological order
    
    # Fetch requirements
    requirements = db_session.query(Requirements).filter_by(lead_id=lead_id).first()
    
    # Fetch lead info
    lead = db_session.query(Lead).filter_by(id=lead_id).first()

    # Step 1: Pre-filter to avoid hallucination
    text_lower = text.lower().strip()
    
    # Generic keywords that indicate property requirements (NO specific area names!)
    property_keywords = [
        'bhk', 'bedroom', 'room', 'flat', 'apartment',
        'furnished', 'furnishing', 'semi', 'full',
        'budget', 'lakh', 'lakhs', 'crore', 'rs', 'rupees', '₹',
        'locality', 'location', 'area', 'near', 'in ',
        'date', 'move', 'moving', 'february', 'march', 'april', 'may',
        'looking for', 'need', 'want', 'searching',
        'property', 'properties', 'show', 'recommend'
    ]
    
    # Skip extraction if NO property-related keywords found
    has_property_keyword = any(keyword in text_lower for keyword in property_keywords)
    
    skip_extraction = not has_property_keyword
    
    if skip_extraction:
        print(f"⏭️ Skipping extraction - no property keywords found")
    
    # Step 2: Extract requirements
    requirements_found = False
    if not skip_extraction:
        extraction = extract_requirements(llm, text)
        print(f"📋 Extraction result: {extraction}")

        if extraction and extraction.lower() not in ['null', 'none', '']:
            try:
                # Clean up extraction - remove markdown code blocks if present
                extraction = extraction.replace("```json", "").replace("```", "").strip()
                
                # Handle case where LLM includes "Input:" and "Output:" labels
                if "Output:" in extraction:
                    # Extract only the JSON part after "Output:"
                    extraction = extraction.split("Output:")[-1].strip()
                
                # Try to find JSON object if there's extra text
                json_match = re.search(r'\{.*\}', extraction, re.DOTALL)
                if json_match:
                    extraction = json_match.group(0)
                
                data = json.loads(extraction)
                
                # VALIDATION: Check if extracted data actually appears in user message
                is_hallucination = False
                if data and len(data) > 0:
                    text_lower = text.lower()
                    
                    # Check locality
                    if 'preferred_locality' in data:
                        locality = str(data['preferred_locality']).lower()
                        # Check if any part of the locality name appears in message
                        locality_words = locality.split()
                        if not any(word in text_lower for word in locality_words if len(word) > 2):
                            print(f"❌ HALLUCINATION DETECTED: Locality '{data['preferred_locality']}' not in message: '{text}'")
                            is_hallucination = True
                    
                    # Check BHK
                    if 'bhk' in data:
                        bhk_mentioned = any(keyword in text_lower for keyword in ['bhk', 'bedroom', 'room', '1', '2', '3', '4'])
                        if not bhk_mentioned:
                            print(f"❌ HALLUCINATION DETECTED: BHK '{data['bhk']}' not in message: '{text}'")
                            is_hallucination = True
                    
                    # Check budget (be more lenient - check for numbers or budget keywords)
                    if 'budget_max' in data:
                        budget_mentioned = any(keyword in text_lower for keyword in ['budget', 'lakh', 'lakhs', 'crore', 'rs', 'rupees', '₹', 'price', 'cost', 'max', 'min', 'maximum', 'minimum', 'upto', 'up to'])
                        # Also check if there are any numbers in the message (could be budget)
                        has_numbers = any(char.isdigit() for char in text)
                        if not (budget_mentioned or has_numbers):
                            print(f"❌ HALLUCINATION DETECTED: Budget in extraction but not in message: '{text}'")
                            is_hallucination = True
                    
                    # Check furnishing
                    if 'furnishing' in data:
                        furnishing_mentioned = any(keyword in text_lower for keyword in ['furnish', 'furnished', 'semi', 'full'])
                        if not furnishing_mentioned:
                            print(f"❌ HALLUCINATION DETECTED: Furnishing '{data['furnishing']}' not in message: '{text}'")
                            is_hallucination = True
                
                # Check if we actually got some requirements (not empty dict)
                if data and len(data) > 0 and not is_hallucination:
                    # Skip saving if only "other_requirements" contains greetings/casual chat
                    skip_greeting = False
                    if len(data) == 1 and 'other_requirements' in data:
                        other_req = data['other_requirements'].lower()
                        greetings = ['hi', 'hello', 'hey', 'how are you', 'good morning', 'good evening']
                        if any(greeting in other_req for greeting in greetings):
                            print(f"ℹ️ Greeting detected - not saving to requirements")
                            skip_greeting = True
                    
                    if not skip_greeting:
                        data['lead_id'] = lead_id
                        from app.llm.tools import update_requirements
                        result = update_requirements.invoke(json.dumps(data))
                        requirements_found = True
                        print(f"✅ Tool result: {result}")
                        
                        # Verify requirements were saved
                        from app.models import Requirements
                        req = db_session.query(Requirements).filter_by(lead_id=lead_id).first()
                        if req:
                            print(f"✅ Verified in DB: {req.to_dict()}")
                        else:
                            print(f"⚠️ Warning: Requirements not found in database after update!")
                elif is_hallucination:
                    print(f"🚫 Skipping save - hallucination detected in extraction")
                else:
                    print(f"ℹ️ No requirements found in message (empty extraction)")
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse extraction: '{extraction}', Error: {e}")
            except Exception as e:
                print(f"❌ Error updating requirements: {e}")
                import traceback
                traceback.print_exc()

    # Step 2: Generate reply with conversation history and context
    
    # Build requirements summary
    req_summary = []
    missing_fields = []
    
    if requirements:
        if requirements.bhk:
            req_summary.append(f"BHK: {requirements.bhk}")
        else:
            missing_fields.append("BHK")
            
        if requirements.preferred_locality:
            req_summary.append(f"Location: {requirements.preferred_locality}")
        else:
            missing_fields.append("Location")
            
        if requirements.budget_max:
            req_summary.append(f"Budget: up to ₹{requirements.budget_max:,.0f}")
        else:
            missing_fields.append("Budget")
            
        if requirements.furnishing:
            req_summary.append(f"Furnishing: {requirements.furnishing}")
            
        if requirements.move_in_date:
            req_summary.append(f"Move-in date: {requirements.move_in_date}")
            
        if requirements.other_requirements:
            req_summary.append(f"Other: {requirements.other_requirements}")
    else:
        missing_fields = ["BHK", "Location", "Budget"]
    
    req_context = "\n".join(req_summary) if req_summary else "No requirements captured yet"
    missing_context = f"Still need: {', '.join(missing_fields)}" if missing_fields else "All key requirements captured!"
    
    # Determine behavior based on state
    if lead and lead.state == ConversationState.NEW_LEAD.value:
        state_instruction = "This is a new lead. Welcome them warmly and start gathering requirements."
    elif lead and lead.state == ConversationState.COLLECTING_REQUIREMENTS.value:
        state_instruction = f"Continue gathering requirements. {missing_context}"
    elif lead and lead.state in [ConversationState.REQUIREMENTS_COMPLETE.value, ConversationState.SEARCHING_PROPERTIES.value]:
        state_instruction = "Requirements are complete! Let the customer know you'll search for matching properties."
    else:
        state_instruction = "Continue helping the customer."
    
    # Build conversation messages with history
    messages = [
        ("system", f"""You are a friendly and professional real estate broker helping {lead.name if lead else 'the customer'} find properties.

Customer: {lead.name if lead else 'Customer'} (username: {lead.username if lead else 'unknown'})
State: {lead.state if lead else 'new_lead'}

Requirements captured:
{req_context}

{state_instruction}

Instructions:
- Be context-aware: reference previous messages naturally
- Do NOT repeat questions about already-captured requirements
- Do NOT ask for BHK/location/budget again if already provided
- Keep responses conversational (2-3 sentences max)
- Use the customer's name naturally in conversation

IMPORTANT: 
- Write ONLY natural conversation text
- Do NOT write JSON, code, or function calls
- Do NOT add signatures like "Best regards, [Your Name]" or similar
- Just write the conversation message and nothing else""")
    ]
    
    # Add conversation history
    for conv in conversation_history:
        if conv.role == 'user':
            messages.append(("user", conv.content))
        else:
            messages.append(("assistant", conv.content))
    
    # Add current message
    messages.append(("user", text))
    
    conversation_prompt = ChatPromptTemplate.from_messages(messages)
    chain = conversation_prompt | llm
    response = chain.invoke({})
    llm_response = response.content

    print(f"💬 LLM Response: {llm_response}")

    print(f"💬 LLM Response: {llm_response}")
    
    # Return the response without saving/sending
    # The consumer will decide whether to send immediately or await approval
    return llm_response

def find_matching_properties(db_session, requirements):
    """
    Find properties that match the lead's requirements
    
    Args:
        db_session: SQLAlchemy session
        requirements: Requirements object
    
    Returns:
        list: List of matching Property objects
    """
    from sqlalchemy import or_
    from app.models import Property
    from app.models.property import PropertyStatus, FurnishingStatus
    
    print(f"🔍 Searching with requirements:")
    print(f"   BHK: {requirements.bhk}")
    print(f"   Locality: {requirements.preferred_locality}")
    print(f"   Furnishing: {requirements.furnishing}")
    print(f"   Budget max: {requirements.budget_max}")
    
    query = db_session.query(Property).filter(Property.status == PropertyStatus.AVAILABLE)
    print(f"   Step 1: {query.count()} AVAILABLE properties")
    
    # Filter by BHK
    if requirements.bhk:
        query = query.filter(Property.bhk == requirements.bhk)
        print(f"   Step 2: After BHK filter: {query.count()} properties")
    
    # Filter by locality: match if property locality contains preferred_locality OR any word of preferred_locality
    # (e.g. preferred "HSR Layout" matches property "HSR", and "Koramangala" matches "Koramangala 5th Block")
    if requirements.preferred_locality:
        pref = (requirements.preferred_locality or "").strip()
        if pref:
            words = [w for w in pref.split() if len(w) >= 2]
            if words:
                locality_conditions = [Property.locality.ilike(f'%{w}%') for w in words]
                query = query.filter(or_(*locality_conditions))
            else:
                query = query.filter(Property.locality.ilike(f'%{pref}%'))
        print(f"   Step 3: After locality filter: {query.count()} properties")
    
    # Filter by furnishing (requirements store "full"/"semi", DB enum is FURNISHED/SEMI_FURNISHED/UNFURNISHED)
    if requirements.furnishing:
        f = (requirements.furnishing or "").strip().lower()
        furnishing_enum = None
        if f in ("full", "furnished", "fully furnished"):
            furnishing_enum = FurnishingStatus.FURNISHED
        elif f in ("semi", "semi-furnished", "semi furnished"):
            furnishing_enum = FurnishingStatus.SEMI_FURNISHED
        elif f in ("unfurnished", "none"):
            furnishing_enum = FurnishingStatus.UNFURNISHED
        if furnishing_enum is not None:
            query = query.filter(Property.furnishing_status == furnishing_enum)
            print(f"   Step 4: After furnishing filter: {query.count()} properties")
        else:
            print(f"   Step 4: Furnishing '{requirements.furnishing}' not mapped, skipping")
    
    # Filter by max budget only (no min budget used)
    if requirements.budget_max:
        query = query.filter(Property.budget <= requirements.budget_max)
        print(f"   Step 5: After budget max filter: {query.count()} properties")
    
    # Order by created date (newest first)
    query = query.order_by(Property.created_at.desc())
    
    # Limit to top 5 matches
    properties = query.limit(5).all()
    
    print(f"   ✅ Final result: {len(properties)} properties")
    for p in properties:
        print(f"      - {p.title} (ID: {p.id})")
    
    return properties

def generate_property_recommendation_message(llm, properties, requirements):
    """
    Return a short, fixed message pointing the lead to the Properties tab.
    Uses a template only — no LLM call — so we never list or invent property IDs or details.
    """
    if not properties:
        return "I couldn't find any properties that match your exact requirements right now. Would you like to adjust your preferences, or should I notify you when new properties become available?"
    n = len(properties)
    word = "property" if n == 1 else "properties"
    return (
        f"I've found {n} matching {word} for you. "
        "Please open the **Properties** tab to see the list with details and photos. "
        "Ask me in chat if you want more info on any of them or would like to schedule a viewing!"
    )