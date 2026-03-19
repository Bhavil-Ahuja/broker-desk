from langchain.tools import tool
from typing import Optional
import json
import re

# DB allows furnishing only 4 chars ("semi" / "full")
def _normalize_furnishing(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if "semi" in s:
        return "semi"
    if "full" in s:
        return "full"
    return s[:4] if len(s) > 4 else s

def _parse_move_in_date(v):
    from datetime import datetime
    if v is None:
        return None
    if hasattr(v, "year"):
        return v
    s = str(v).strip()
    if not s:
        return None
    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return datetime.fromisoformat(s[:10])
    # Month name only -> first day of that month in 2026
    months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
              "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    s_lower = s.lower()
    for name, num in months.items():
        if name in s_lower:
            return datetime(2026, num, 1)
    return None

@tool
def update_requirements(input_json: str):
    """
    Use this tool ONLY when the customer explicitly mentions a property requirement.
    Do NOT call this tool for greetings, general questions, or casual conversation.
    
    Pass a JSON string with only the fields the customer mentioned:
    - lead_id (required, integer)
    - bhk (integer, number of bedrooms)
    - furnishing (string, only "full" or "semi")
    - preferred_locality (string)
    - budget_max (integer)
    - move_in_date (string, ISO format YYYY-MM-DD)
    - other_requirements (string)
    
    Example: '{{"lead_id": 1, "bhk": 2, "preferred_locality": "Bangalore", "move_in_date": "2026-02-10"}}'
    Only include fields the customer actually mentioned.
    """
    from app.models import Session, Requirements

    data = json.loads(input_json)
    lead_id = data.get('lead_id')
    if lead_id is None:
        return "Error: lead_id is required"

    from datetime import datetime, timezone, timedelta
    session = Session()
    try:
        req = session.query(Requirements).filter_by(lead_id=lead_id).first()

        if not req:
            req = Requirements(lead_id=lead_id)
            session.add(req)

        # Update fields that are present in the data (with normalization for DB)
        updated_fields = []
        if 'bhk' in data:
            req.bhk = data['bhk']
            updated_fields.append(f"bhk={data['bhk']}")
        if 'furnishing' in data:
            normalized = _normalize_furnishing(data['furnishing'])
            req.furnishing = normalized
            updated_fields.append(f"furnishing={normalized}")
        if 'preferred_locality' in data:
            req.preferred_locality = data['preferred_locality']
            updated_fields.append(f"locality={data['preferred_locality']}")
        if 'budget_max' in data:
            req.budget_max = data['budget_max']
            updated_fields.append(f"budget_max={data['budget_max']}")
        if 'other_requirements' in data:
            req.other_requirements = data['other_requirements']
            updated_fields.append(f"other={data['other_requirements']}")
        if 'move_in_date' in data:
            date_val = data['move_in_date']
            parsed = _parse_move_in_date(date_val)
            if parsed is not None:
                req.move_in_date = parsed
                updated_fields.append(f"move_in_date={date_val}")
            else:
                try:
                    req.move_in_date = datetime.fromisoformat(str(date_val)[:10]) if isinstance(date_val, str) else date_val
                    updated_fields.append(f"move_in_date={date_val}")
                except Exception:
                    pass
        IST = timezone(timedelta(hours=5, minutes=30))
        req.last_modified_at = datetime.now(IST).replace(tzinfo=None)

        session.commit()
        print(f"✅ Requirements updated for lead {lead_id}: {', '.join(updated_fields)}")
        print(f"   Full record: {req.to_dict()}")
        return f"Requirements updated successfully: {', '.join(updated_fields)}"
    except Exception as e:
        session.rollback()
        print(f"❌ update_requirements failed: {e}")
        import traceback
        traceback.print_exc()
        return f"Error updating requirements: {e}"
    finally:
        session.close()