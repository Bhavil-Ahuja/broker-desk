"""Application settings for broker automation (no secrets — use environment variables elsewhere)."""

import os


class BrokerSettings:
    """Broker automation helpers (auto-send logic only)."""

    # Optional: if you add broker HTTP auth later, read from env — never commit real values.
    BROKER_USERNAME = os.getenv("BROKER_USERNAME", "")
    BROKER_PASSWORD = os.getenv("BROKER_PASSWORD", "")

    @classmethod
    def get_auto_send(cls, session, lead_auto_send=None):
        """
        Determine if auto-send is enabled for a lead.
        Priority: Global OFF overrides all, then lead-specific setting.

        Logic:
        - Global OFF → All OFF (no matter what user setting is)
        - Global ON + User OFF → OFF
        - Global ON + User ON → ON

        Args:
            session: SQLAlchemy session to query database
            lead_auto_send: Lead's auto_send value (0 or 1)
        """
        from app.models import GlobalSettings

        global_auto_send = GlobalSettings.get_auto_send(session)

        if not global_auto_send:
            return False

        if lead_auto_send is not None:
            return bool(lead_auto_send)

        return global_auto_send
