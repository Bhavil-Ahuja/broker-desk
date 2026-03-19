from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base
import uuid
import enum

class MediaType(enum.Enum):
    IMAGE = "image"
    VIDEO = "video"

class PropertyMedia(Base):
    __tablename__ = 'property_media'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    property_id = Column(String(36), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)
    
    cloudinary_public_id = Column(String(255), nullable=False)  # Cloudinary public ID
    cloudinary_url = Column(String(500), nullable=False)  # Full URL to the media
    media_type = Column(Enum(MediaType, create_type=False), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)  # For videos
    file_size = Column(Integer, nullable=True)  # Size in bytes
    order = Column(Integer, nullable=False, default=0)  # For sorting media
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    property = relationship("Property", back_populates="media")

    def to_dict(self):
        return {
            'id': self.id,
            'property_id': self.property_id,
            'cloudinary_public_id': self.cloudinary_public_id,
            'cloudinary_url': self.cloudinary_url,
            'media_type': self.media_type.value if self.media_type else None,
            'thumbnail_url': self.thumbnail_url,
            'file_size': self.file_size,
            'order': self.order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
