from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from . import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST as naive datetime (for database storage)"""
    return datetime.now(IST).replace(tzinfo=None)

class Lead(Base):
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    state = Column(String(36), nullable=False, default='new_lead')
    auto_send = Column(Integer, nullable=False, default=1)
    session_token = Column(String(100), unique=True, nullable=True)
    session_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)
    last_login = Column(DateTime, nullable=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'state': self.state,
            'auto_send': self.auto_send,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }