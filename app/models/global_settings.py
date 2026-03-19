"""Global settings stored in database for cross-process access"""
from sqlalchemy import Column, String, Integer
from . import Base

class GlobalSettings(Base):
    __tablename__ = 'global_settings'
    
    key = Column(String(50), primary_key=True)
    value = Column(Integer, nullable=False)
    
    @staticmethod
    def get_auto_send(session):
        """Get global auto-send setting from database"""
        setting = session.query(GlobalSettings).filter_by(key='global_auto_send').first()
        if setting:
            return bool(setting.value)
        # Default to True if not set
        return True
    
    @staticmethod
    def set_auto_send(session, enabled):
        """Set global auto-send setting in database"""
        setting = session.query(GlobalSettings).filter_by(key='global_auto_send').first()
        if setting:
            setting.value = 1 if enabled else 0
        else:
            setting = GlobalSettings(key='global_auto_send', value=1 if enabled else 0)
            session.add(setting)
        session.commit()
    
    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value
        }
