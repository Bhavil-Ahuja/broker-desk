from enum import Enum

class ConversationState(Enum):
    NEW_LEAD = "new_lead"
    COLLECTING_REQUIREMENTS = "collecting_requirements"
    REQUIREMENTS_COMPLETE = "requirements_complete"
    SEARCHING_PROPERTIES = "searching_properties"
    SHOWING_PROPERTIES = "showing_properties"
    AWAITING_APPROVAL = "awaiting_approval"
    VISIT_SCHEDULED = "visit_scheduled"