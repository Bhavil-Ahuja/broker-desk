from kafka import KafkaConsumer, KafkaProducer
import json
import requests
from sqlalchemy.exc import IntegrityError
from app.models import Session, Conversation, Lead, PendingApproval
from app.util.conversation_helper import set_new_state
from app.config.settings import BrokerSettings

API_BASE_URL = 'http://localhost:5001'

try:
    consumer = KafkaConsumer(
        'lead-events-consumer',
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='chat-with-ai-broker'
    )
    print("✅ Connected to Kafka")
except Exception as e:
    print(f"❌ Kafka connection failed: {e}")

print("🎧 Waiting for messages...")

session = Session()

for msg in consumer:
    data = msg.value
    
    lead_id = data.get('lead_id')
    message_text = data.get('body', {}).get('message')
    
    print(f"Lead ID: {lead_id}, Message: {message_text}")
    
    lead = session.get(Lead, lead_id)
    
    if not lead:
        print(f"❌ Error: Lead with id {lead_id} does not exist")
        continue
    
    try:
        recommended_property_ids_this_turn = None  # batch of property IDs for this approval (if any)
        # Save user message first
        user_conversation = Conversation(
            lead_id=lead_id,
            role='user',
            content=message_text
        )
        session.add(user_conversation)
        session.commit()
        
        print(f"Saved user message to DB at {user_conversation.created_at}")
        try:
            requests.post(f'{API_BASE_URL}/internal/ws/lead_message_received/{lead_id}', timeout=3)
        except Exception as e:
            print(f"⚠️ Broker notify failed: {e}")
        
        # Process message (extracts requirements and generates response)
        from app.llm.llm_processor import process_message
        ai_response = process_message(lead_id, message_text, session)
        
        # Update state after processing (requirements may have been updated)
        session.refresh(lead)  # Refresh to get latest state
        existing_state = lead.state
        lead = set_new_state(lead, lead_id, session)
        new_state = lead.state
        print(f"State: {existing_state} → {new_state}")
        
        # Check if requirements just became complete (check BEFORE state, as it transitions immediately)
        from app.services.state_machine import ConversationState
        requirements_just_completed = (
            existing_state == ConversationState.COLLECTING_REQUIREMENTS.value and 
            new_state in [ConversationState.REQUIREMENTS_COMPLETE.value, ConversationState.SEARCHING_PROPERTIES.value]
        )
        
        if requirements_just_completed:
            print(f"✨ Requirements complete! Finding matching properties...")
            
            # Disable auto_send for this lead (broker must approve property recommendations)
            lead.auto_send = 0
            session.commit()
            print(f"🔒 Auto-send disabled for lead {lead_id} - broker approval required for properties")
            
            # Find matching properties
            from app.models.requirements import Requirements
            from app.llm.llm_processor import find_matching_properties, generate_property_recommendation_message
            from app.llm.llm_setup import get_llm
            
            requirements = session.query(Requirements).filter_by(lead_id=lead_id).first()
            if requirements:
                matching_properties = find_matching_properties(session, requirements)
                print(f"🏠 Found {len(matching_properties)} matching properties")
                
                if matching_properties:
                    # Generate property recommendation message
                    llm = get_llm()
                    ai_response = generate_property_recommendation_message(llm, matching_properties, requirements)
                    
                    # Store recommendations in database
                    from app.models import PropertyRecommendation
                    for prop in matching_properties:
                        recommendation = PropertyRecommendation(
                            lead_id=lead_id,
                            property_id=prop.id
                        )
                        session.add(recommendation)
                    session.commit()
                    recommended_property_ids_this_turn = [p.id for p in matching_properties]
                    print(f"📋 Stored {len(matching_properties)} property recommendations")
                else:
                    print(f"⚠️ No matching properties found")
        
        # Check if user is explicitly asking for properties in SEARCHING_PROPERTIES state
        if new_state == ConversationState.SEARCHING_PROPERTIES.value and not requirements_just_completed:
            text_lower = message_text.lower()
            asking_for_properties = any(keyword in text_lower for keyword in ['show', 'properties', 'property', 'recommend', 'find'])
            
            if asking_for_properties:
                print(f"🔍 User asking for properties - refreshing recommendations...")
                from app.models import PropertyRecommendation
                from app.models.requirements import Requirements
                from app.llm.llm_processor import find_matching_properties, generate_property_recommendation_message
                from app.llm.llm_setup import get_llm
                
                existing_recs = session.query(PropertyRecommendation).filter_by(lead_id=lead_id).all()
                existing_property_ids = {r.property_id for r in existing_recs}
                
                requirements = session.query(Requirements).filter_by(lead_id=lead_id).first()
                if requirements:
                    matching_properties = find_matching_properties(session, requirements)
                    print(f"🏠 Found {len(matching_properties)} matching properties (already recommended: {len(existing_property_ids)})")
                    
                    added = 0
                    for prop in matching_properties:
                        if prop.id not in existing_property_ids:
                            session.add(PropertyRecommendation(lead_id=lead_id, property_id=prop.id))
                            existing_property_ids.add(prop.id)
                            added += 1
                            print(f"   💾 Added recommendation for property ID: {prop.id}")
                    
                    if added:
                        session.commit()
                        recommended_property_ids_this_turn = list(existing_property_ids)
                        print(f"📋 Added {added} new property recommendations")
                        llm = get_llm()
                        ai_response = generate_property_recommendation_message(llm, matching_properties, requirements)
                    elif matching_properties:
                        print(f"✅ All matching properties already recommended")
                    else:
                        print(f"⚠️ No matching properties found in broker database")
        
        # Check if auto_send is enabled (query DB for global setting)
        from app.models import GlobalSettings
        global_setting = GlobalSettings.get_auto_send(session)
        auto_send_enabled = BrokerSettings.get_auto_send(session, lead.auto_send)
        print(f"🔍 Auto-send check: Global={global_setting}, Lead={lead.auto_send}, Result={auto_send_enabled}")
        
        if auto_send_enabled:
            # Auto-send: Save to DB and send to user immediately
            print(f"✅ Auto-send enabled - sending response immediately")
            session.add(Conversation(
                lead_id=lead_id,
                role='assistant',
                content=ai_response,
                sent_by='ai'
            ))
            session.commit()
            
            # Send to Kafka for user delivery
            producer = KafkaProducer(
                bootstrap_servers='localhost:9092',
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            producer.send('broker-response', {
                'lead_id': lead_id,
                'original_message': message_text,
                'response': ai_response
            })
            producer.flush()
            print(f"📤 Response sent to user")
            try:
                requests.post(f'{API_BASE_URL}/internal/ws/message_sent/{lead_id}', timeout=3)
            except Exception as e:
                print(f"⚠️ WS trigger failed: {e}")
        else:
            # Manual approval required: Create pending approval
            print(f"⏸️ Auto-send disabled - creating pending approval")
            import json
            pending = PendingApproval(
                lead_id=lead_id,
                user_message_id=user_conversation.id,
                user_message=message_text,
                ai_message=ai_response,
                recommended_property_ids=json.dumps(recommended_property_ids_this_turn) if recommended_property_ids_this_turn else None
            )
            session.add(pending)
            session.commit()
            print(f"📋 Pending approval created (ID: {pending.id})")
            try:
                requests.post(f'{API_BASE_URL}/internal/ws/pending_approval/{lead_id}/{pending.id}', timeout=3)
            except Exception as e:
                print(f"⚠️ WS trigger failed: {e}")
        
    except IntegrityError as e:
        session.rollback()
        print(f"❌ Error: {e}")
        print(f"   Skipping message: {message_text}")