from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone, timedelta
from . import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST as naive datetime (for database storage)"""
    return datetime.now(IST).replace(tzinfo=None)

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sent_by = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=get_ist_now)
    
    lead = relationship("Lead", backref="conversations")
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'role': self.role,
            'content': self.content,
            'sent_by': self.sent_by,
            'created_at': self.created_at.isoformat()
        }