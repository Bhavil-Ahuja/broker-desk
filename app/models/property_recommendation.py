from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base
import uuid

class PropertyRecommendation(Base):
    __tablename__ = 'property_recommendations'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    property_id = Column(String(36), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)
    conversation_id = Column(String(36), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=True)
    
    recommended_at = Column(DateTime, nullable=False, default=datetime.now)
    viewed = Column(Integer, nullable=False, default=0)  # 0 = not viewed, 1 = viewed
    interested = Column(Integer, nullable=True)  # NULL = no response, 0 = not interested, 1 = interested
    feedback = Column(Text, nullable=True)

    # Relationships
    lead = relationship("Lead", backref="property_recommendations")
    property = relationship("Property", backref="recommendations")
    conversation = relationship("Conversation", backref="property_recommendation")

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'property_id': self.property_id,
            'conversation_id': self.conversation_id,
            'recommended_at': self.recommended_at.isoformat() if self.recommended_at else None,
            'viewed': bool(self.viewed),
            'interested': self.interested,
            'feedback': self.feedback
        }
