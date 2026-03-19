from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone, timedelta
from . import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST as naive datetime (for database storage)"""
    return datetime.now(IST).replace(tzinfo=None)

class Requirements(Base):
    __tablename__ = 'requirements'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)
    bhk = Column(Integer)
    furnishing = Column(String(4))
    preferred_locality = Column(Text)
    budget_max = Column(Integer)
    move_in_date = Column(DateTime)
    other_requirements = Column(Text)
    created_at = Column(DateTime, default=get_ist_now)
    last_modified_at = Column(DateTime, default=get_ist_now)
    
    lead = relationship("Lead", backref="requirements")
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'bhk': self.bhk,
            'furnishing': self.furnishing,
            'preferred_locality': self.preferred_locality,
            'budget_max': self.budget_max,
            'move_in_date': self.move_in_date,
            'other_requirements': self.other_requirements,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_modified_at': self.last_modified_at.isoformat() if self.last_modified_at else None
        }