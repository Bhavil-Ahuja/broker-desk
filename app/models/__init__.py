from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine('postgresql://user:password@localhost:5432/broker_db')
Session = sessionmaker(bind=engine)


def _ensure_enum_types(eng):
    """Create PostgreSQL enum types only if they don't exist (avoids UniqueViolation on restart)."""
    statements = [
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'furnishingstatus') THEN "
        "CREATE TYPE furnishingstatus AS ENUM ('FURNISHED', 'SEMI_FURNISHED', 'UNFURNISHED'); END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'propertytype') THEN "
        "CREATE TYPE propertytype AS ENUM ('APARTMENT', 'VILLA', 'INDEPENDENT_HOUSE', 'STUDIO', 'PENTHOUSE'); END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'propertystatus') THEN "
        "CREATE TYPE propertystatus AS ENUM ('AVAILABLE', 'RENTED', 'SOLD'); END IF; END $$",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mediatype') THEN "
        "CREATE TYPE mediatype AS ENUM ('IMAGE', 'VIDEO'); END IF; END $$",
    ]
    with eng.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()


# Ensure enums exist before tables (so create_type=False in models doesn't fail)
_ensure_enum_types(engine)

# Import all models
from .conversation import Conversation
from .lead import Lead
from .requirements import Requirements
from .pending_approval import PendingApproval
from .global_settings import GlobalSettings
from .property import Property
from .property_media import PropertyMedia
from .property_recommendation import PropertyRecommendation

# Create all tables
Base.metadata.create_all(engine)