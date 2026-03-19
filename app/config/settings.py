"""Global application settings"""

class BrokerSettings:
    """Global settings for broker automation"""
    
    # Broker credentials for admin UI
    BROKER_USERNAME = "broker_admin"
    BROKER_PASSWORD = "broker123"  # Change this in production!
    
    @classmethod
    def get_auto_send(cls, session, lead_auto_send=None):
        """
        Determine if auto-send is enabled for a lead
        Priority: Global OFF overrides all, then lead-specific setting
        
        Logic:
        - Global OFF → All OFF (no matter what user setting is)
        - Global ON + User OFF → OFF
        - Global ON + User ON → ON
        
        Args:
            session: SQLAlchemy session to query database
            lead_auto_send: Lead's auto_send value (0 or 1)
        """
        from app.models import GlobalSettings
        
        # Get global setting from database
        global_auto_send = GlobalSettings.get_auto_send(session)
        
        # Global setting overrides if it's OFF
        if not global_auto_send:
            return False
        
        # If global is ON, use lead-specific setting
        if lead_auto_send is not None:
            return bool(lead_auto_send)
        
        # Default to global setting
        return global_auto_send
