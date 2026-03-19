from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import uuid
import json
from datetime import datetime, timezone, timedelta
from . import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST as naive datetime (for database storage)"""
    return datetime.now(IST).replace(tzinfo=None)

class PendingApproval(Base):
    __tablename__ = 'pending_approvals'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)
    user_message_id = Column(String(36), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    ai_message = Column(Text, nullable=False)
    user_message = Column(Text, nullable=False)
    is_approved = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)
    reviewed_at = Column(DateTime, nullable=True)
    broker_notes = Column(Text, nullable=True)
    # JSON array of property IDs recommended in this batch (for broker to edit before approve)
    recommended_property_ids = Column(Text, nullable=True)

    lead = relationship("Lead", backref="pending_approvals")
    conversation = relationship("Conversation", backref="pending_approvals")

    def to_dict(self):
        out = {
            'id': self.id,
            'lead_id': self.lead_id,
            'ai_message': self.ai_message,
            'user_message': self.user_message,
            'is_approved': self.is_approved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'broker_notes': self.broker_notes
        }
        if self.recommended_property_ids:
            try:
                out['recommended_property_ids'] = json.loads(self.recommended_property_ids)
            except Exception:
                out['recommended_property_ids'] = []
        else:
            out['recommended_property_ids'] = []
        return out
