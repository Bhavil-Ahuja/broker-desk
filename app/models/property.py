from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base
import uuid
import enum

class FurnishingStatus(enum.Enum):
    FURNISHED = "furnished"
    SEMI_FURNISHED = "semi-furnished"
    UNFURNISHED = "unfurnished"

class PropertyType(enum.Enum):
    APARTMENT = "apartment"
    VILLA = "villa"
    INDEPENDENT_HOUSE = "independent_house"
    STUDIO = "studio"
    PENTHOUSE = "penthouse"

class PropertyStatus(enum.Enum):
    AVAILABLE = "available"
    RENTED = "rented"
    SOLD = "sold"

class Property(Base):
    __tablename__ = 'properties'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    broker_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    locality = Column(String(100), nullable=False)
    bhk = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)
    furnishing_status = Column(Enum(FurnishingStatus, create_type=False), nullable=False)
    available_from = Column(DateTime, nullable=True)
    property_type = Column(Enum(PropertyType, create_type=False), nullable=False)
    area_sqft = Column(Integer, nullable=True)
    amenities = Column(Text, nullable=True)  # Store as JSON string
    status = Column(Enum(PropertyStatus, create_type=False), nullable=False, default=PropertyStatus.AVAILABLE)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # Relationships
    broker = relationship("Lead", backref="properties")
    media = relationship("PropertyMedia", back_populates="property", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'broker_id': self.broker_id,
            'title': self.title,
            'description': self.description,
            'locality': self.locality,
            'bhk': self.bhk,
            'budget': self.budget,
            'furnishing_status': self.furnishing_status.value if self.furnishing_status else None,
            'available_from': self.available_from.isoformat() if self.available_from else None,
            'property_type': self.property_type.value if self.property_type else None,
            'area_sqft': self.area_sqft,
            'amenities': self.amenities,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'media': [m.to_dict() for m in self.media] if self.media else []
        }
