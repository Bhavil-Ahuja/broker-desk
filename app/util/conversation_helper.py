from app.services.state_machine import ConversationState
from app.models.requirements import Requirements

def check_requirements_complete(lead_id, session):
    """Check if all required fields are captured"""
    req = session.query(Requirements).filter_by(lead_id=lead_id).first()
    
    if not req:
        return False
    
    # Required fields: bhk, locality, budget_max (no min budget)
    required_fields = [
        req.bhk is not None,
        req.preferred_locality is not None and req.preferred_locality.strip() != '',
        req.budget_max is not None
    ]
    
    return all(required_fields)

def set_new_state(existing_lead, lead_id, session):
    """Update lead state based on requirements completion"""
    if not existing_lead:
        return None
    
    current_state = existing_lead.state
    requirements_complete = check_requirements_complete(lead_id, session)
    
    # State transition logic
    if current_state == ConversationState.NEW_LEAD.value:
        # First message - move to collecting requirements
        existing_lead.state = ConversationState.COLLECTING_REQUIREMENTS.value
        session.commit()
        print(f"🔄 State transition: NEW_LEAD → COLLECTING_REQUIREMENTS")
        
    elif current_state == ConversationState.COLLECTING_REQUIREMENTS.value:
        if requirements_complete:
            # Requirements are complete - move to REQUIREMENTS_COMPLETE
            existing_lead.state = ConversationState.REQUIREMENTS_COMPLETE.value
            session.commit()
            print(f"✅ State transition: COLLECTING_REQUIREMENTS → REQUIREMENTS_COMPLETE")
    
    elif current_state == ConversationState.REQUIREMENTS_COMPLETE.value:
        # Brief state - immediately move to searching properties
        existing_lead.state = ConversationState.SEARCHING_PROPERTIES.value
        session.commit()
        print(f"🔍 State transition: REQUIREMENTS_COMPLETE → SEARCHING_PROPERTIES")
    
    return existing_lead