from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from kafka import KafkaProducer
import json
import sys
import os
import secrets
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Session, Conversation, Lead, Property, PropertyMedia

IST = timezone(timedelta(hours=5, minutes=30))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

@app.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.json
    username = data.get('username')
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not name or not email or not password:
        return jsonify({"status": "error", "message": "username, name, email, and password are required"}), 400
    
    session = Session()
    try:
        # Check if username already exists
        existing = session.query(Lead).filter_by(username=username).first()
        if existing:
            return jsonify({"status": "error", "message": "Username already exists"}), 400
        
        # Create new user
        lead = Lead(
            username=username,
            name=name,
            email=email,
            state='new_lead'
        )
        lead.set_password(password)
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        session_expires_at = (datetime.now(IST) + timedelta(hours=24)).replace(tzinfo=None)
        lead.session_token = session_token
        lead.session_expires_at = session_expires_at
        lead.last_login = datetime.now(IST).replace(tzinfo=None)
        
        session.add(lead)
        session.commit()
        session.refresh(lead)
        lead_id = lead.id

        from app.config.settings import BrokerSettings
        auto_send_enabled = BrokerSettings.get_auto_send(session, lead.auto_send)
        
        out = jsonify({
            "status": "success",
            "message": "Registration successful",
            "user": {
                "id": lead.id,
                "username": lead.username,
                "name": lead.name,
                "email": lead.email,
                "auto_send": auto_send_enabled
            },
            "session_token": session_token,
            "expires_at": session_expires_at.isoformat()
        })
        emit_new_lead(lead_id)
        return out
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/login', methods=['POST'])
def login():
    """Login existing user with username and password"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"status": "error", "message": "username and password are required"}), 400
    
    session = Session()
    try:
        # Find user
        lead = session.query(Lead).filter_by(username=username).first()
        
        if not lead:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        
        # Check password
        if not lead.check_password(password):
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        session_expires_at = (datetime.now(IST) + timedelta(hours=24)).replace(tzinfo=None)
        lead.session_token = session_token
        lead.session_expires_at = session_expires_at
        lead.last_login = datetime.now(IST).replace(tzinfo=None)
        
        session.commit()
        session.refresh(lead)
        
        from app.config.settings import BrokerSettings
        auto_send_enabled = BrokerSettings.get_auto_send(session, lead.auto_send)
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {
                "id": lead.id,
                "username": lead.username,
                "name": lead.name,
                "email": lead.email,
                "auto_send": auto_send_enabled
            },
            "session_token": session_token,
            "expires_at": session_expires_at.isoformat()
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/logout', methods=['POST'])
def logout():
    """Logout user by invalidating session token"""
    session_token = request.headers.get('Authorization')
    
    if not session_token:
        return jsonify({"status": "error", "message": "No session token provided"}), 401
    
    session = Session()
    try:
        lead = session.query(Lead).filter_by(session_token=session_token).first()
        
        if lead:
            lead.session_token = None
            lead.session_expires_at = None
            session.commit()
            return jsonify({"status": "success", "message": "Logged out successfully"})
        else:
            return jsonify({"status": "error", "message": "Invalid session"}), 401
    finally:
        session.close()

@app.route('/validate', methods=['GET'])
def validate_session_endpoint():
    """Validate session token and return user data"""
    session_token = request.headers.get('Authorization')
    lead = validate_session(session_token)
    
    if not lead:
        return jsonify({"status": "error", "message": "Invalid or expired session"}), 401
    
    from app.config.settings import BrokerSettings
    from app.models import GlobalSettings
    db_session = Session()
    try:
        auto_send_enabled = BrokerSettings.get_auto_send(db_session, lead.auto_send)
        
        return jsonify({
            "status": "success",
            "user": {
                "id": lead.id,
                "username": lead.username,
                "name": lead.name,
                "email": lead.email,
                "auto_send": auto_send_enabled
            }
        })
    finally:
        db_session.close()

def validate_session(session_token):
    """Validate session token and return lead if valid"""
    if not session_token:
        return None
    
    db_session = Session()
    try:
        lead = db_session.query(Lead).filter_by(session_token=session_token).first()
        
        if not lead:
            return None
        
        # Check if session expired
        if lead.session_expires_at and lead.session_expires_at < datetime.now(IST).replace(tzinfo=None):
            lead.session_token = None
            lead.session_expires_at = None
            db_session.commit()
            return None
        
        return lead
    finally:
        db_session.close()

@app.route('/send', methods=['POST'])
def send_message():
    session_token = request.headers.get('Authorization')
    lead = validate_session(session_token)
    
    if not lead:
        return jsonify({"status": "error", "message": "Unauthorized - please login"}), 401
    
    data = request.json
    message_received = {
        "lead_id": lead.id,
        "body": data
    }
    producer.send('lead-events-consumer', message_received)
    producer.flush()
    return jsonify({"status": "sent", "data": message_received})

@app.route('/history', methods=['GET'])
def get_history():
    """Get conversation history for authenticated user"""
    session_token = request.headers.get('Authorization')
    lead = validate_session(session_token)
    
    if not lead:
        return jsonify({"status": "error", "message": "Unauthorized - please login"}), 401
    
    session = Session()
    try:
        conversations = session.query(Conversation)\
            .filter_by(lead_id=lead.id)\
            .order_by(Conversation.created_at.asc())\
            .all()
        
        history = [
            {
                'role': conv.role,
                'content': conv.content,
                'created_at': conv.created_at.isoformat()
            }
            for conv in conversations
        ]
        return jsonify({"history": history})
    finally:
        session.close()

@app.route('/clear', methods=['DELETE'])
def clear_chat():
    """Clear all conversations, requirements, and property recommendations for authenticated user"""
    session_token = request.headers.get('Authorization')
    lead = validate_session(session_token)
    
    if not lead:
        return jsonify({"status": "error", "message": "Unauthorized - please login"}), 401
    
    from models import Requirements
    from app.models import PropertyRecommendation
    session = Session()
    try:
        deleted_conversations = session.query(Conversation)\
            .filter_by(lead_id=lead.id)\
            .delete()
        
        deleted_requirements = session.query(Requirements)\
            .filter_by(lead_id=lead.id)\
            .delete()
        
        deleted_recommendations = session.query(PropertyRecommendation)\
            .filter_by(lead_id=lead.id)\
            .delete()
        
        session.commit()
        
        print(f"🗑️ Cleared for lead {lead.id}: {deleted_conversations} convos, {deleted_requirements} reqs, {deleted_recommendations} recommendations")
        
        return jsonify({
            "status": "success",
            "message": f"Cleared {deleted_conversations} conversations, {deleted_requirements} requirements, and {deleted_recommendations} recommendations",
            "deleted": {
                "conversations": deleted_conversations,
                "requirements": deleted_requirements
            }
        })
    except Exception as e:
        session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        session.close()

@app.route('/user', methods=['DELETE'])
def delete_user():
    """Delete authenticated user and all associated data (lead, conversations, requirements)"""
    session_token = request.headers.get('Authorization')
    lead = validate_session(session_token)
    
    if not lead:
        return jsonify({"status": "error", "message": "Unauthorized - please login"}), 401
    
    from models import Requirements
    session = Session()
    try:
        lead_id = lead.id
        
        deleted_conversations = session.query(Conversation)\
            .filter_by(lead_id=lead_id)\
            .delete()
        
        deleted_requirements = session.query(Requirements)\
            .filter_by(lead_id=lead_id)\
            .delete()
        
        deleted_lead = session.query(Lead)\
            .filter_by(id=lead_id)\
            .delete()
        
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "User deleted completely",
            "deleted": {
                "lead": deleted_lead,
                "conversations": deleted_conversations,
                "requirements": deleted_requirements
            }
        })
    except Exception as e:
        session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        session.close()

# ============ BROKER ENDPOINTS ============

@app.route('/broker/leads', methods=['GET'])
def get_all_leads():
    """Get all leads with their latest conversation"""
    session = Session()
    try:
        from models import Requirements
        leads = session.query(Lead).order_by(Lead.last_login.desc()).all()
        
        result = []
        for lead in leads:
            # Get latest conversation
            latest_conv = session.query(Conversation)\
                .filter_by(lead_id=lead.id)\
                .order_by(Conversation.created_at.desc())\
                .first()
            
            # Get requirements
            req = session.query(Requirements).filter_by(lead_id=lead.id).first()
            
            # Get pending approvals count
            from models import PendingApproval
            pending_count = session.query(PendingApproval)\
                .filter_by(lead_id=lead.id, is_approved=None)\
                .count()
            
            result.append({
                'lead': lead.to_dict(),
                'latest_message': latest_conv.content if latest_conv else None,
                'latest_message_time': latest_conv.created_at.isoformat() if latest_conv else None,
                'pending_approvals': pending_count,
                'requirements_complete': req is not None and all([
                    req.bhk, req.preferred_locality, req.budget_max
                ]) if req else False
            })
        
        return jsonify({"leads": result})
    finally:
        session.close()

@app.route('/broker/lead/<int:lead_id>', methods=['GET'])
def get_lead_details(lead_id):
    """Get detailed information about a specific lead"""
    session = Session()
    try:
        from models import Requirements
        lead = session.get(Lead, lead_id)
        
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        # Get all conversations
        conversations = session.query(Conversation)\
            .filter_by(lead_id=lead_id)\
            .order_by(Conversation.created_at.asc())\
            .all()
        
        # Get requirements
        req = session.query(Requirements).filter_by(lead_id=lead_id).first()
        
        # Get pending approvals (with recommended_properties for broker to edit)
        from models import PendingApproval
        pending = session.query(PendingApproval)\
            .filter_by(lead_id=lead_id, is_approved=None)\
            .order_by(PendingApproval.created_at.desc())\
            .all()
        pending_list = []
        for p in pending:
            d = p.to_dict()
            ids = d.get('recommended_property_ids') or []
            if ids:
                props = session.query(Property).filter(Property.id.in_(ids)).all()
                d['recommended_properties'] = [prop.to_dict() for prop in props]
            else:
                d['recommended_properties'] = []
            pending_list.append(d)
        
        return jsonify({
            "lead": lead.to_dict(),
            "conversations": [{"role": c.role, "content": c.content, "sent_by": c.sent_by, "created_at": c.created_at.isoformat()} for c in conversations],
            "requirements": req.to_dict() if req else None,
            "pending_approvals": pending_list
        })
    finally:
        session.close()

@app.route('/broker/lead/<int:lead_id>/auto_send', methods=['PUT'])
def toggle_auto_send(lead_id):
    """Toggle auto_send for a specific lead"""
    data = request.json
    auto_send = data.get('auto_send')
    
    if auto_send is None:
        return jsonify({"status": "error", "message": "auto_send field required"}), 400
    
    session = Session()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        lead.auto_send = 1 if auto_send else 0
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Auto-send {'enabled' if auto_send else 'disabled'} for {lead.name}",
            "auto_send": bool(lead.auto_send)
        })
    finally:
        session.close()

@app.route('/broker/approval/<approval_id>/approve', methods=['POST'])
def approve_message(approval_id):
    """Approve and send a pending message (with optional custom message and recommended_property_ids)"""
    data = request.json or {}
    broker_notes = data.get('broker_notes', '')
    custom_message = data.get('custom_message', '')
    new_recommended_ids = data.get('recommended_property_ids')
    
    session = Session()
    try:
        from models import PendingApproval
        from app.models import PropertyRecommendation
        approval = session.query(PendingApproval).filter_by(id=approval_id).first()
        
        if not approval:
            return jsonify({"status": "error", "message": "Approval not found"}), 404
        
        if approval.is_approved is not None:
            return jsonify({"status": "error", "message": "Already reviewed"}), 400
        
        # Sync property recommendations if this approval had a list and broker sent a modified list
        original_ids = []
        if approval.recommended_property_ids:
            try:
                original_ids = json.loads(approval.recommended_property_ids)
            except Exception:
                pass
        if new_recommended_ids is not None and approval.recommended_property_ids:
            original_set = set(original_ids)
            new_set = set(new_recommended_ids)
            lead_id = approval.lead_id
            to_remove = original_set - new_set
            for pid in to_remove:
                session.query(PropertyRecommendation).filter_by(lead_id=lead_id, property_id=pid).delete(synchronize_session=False)
            existing = {r.property_id for r in session.query(PropertyRecommendation).filter_by(lead_id=lead_id).all()}
            for pid in new_set - existing:
                session.add(PropertyRecommendation(lead_id=lead_id, property_id=pid))
        
        # Mark as approved
        approval.is_approved = True
        approval.reviewed_at = datetime.now(IST).replace(tzinfo=None)
        approval.broker_notes = broker_notes
        
        # Use custom message if provided, otherwise use AI message
        message_to_send = custom_message.strip() if custom_message else approval.ai_message
        sent_by = 'broker' if custom_message and custom_message.strip() else 'ai'
        
        # Save message to conversations
        session.add(Conversation(
            lead_id=approval.lead_id,
            role='assistant',
            content=message_to_send,
            sent_by=sent_by
        ))
        
        session.commit()
        
        # Send to Kafka
        from kafka import KafkaProducer
        kafka_producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        kafka_producer.send('broker-response', {
            'lead_id': approval.lead_id,
            'original_message': approval.user_message,
            'response': message_to_send
        })
        kafka_producer.flush()
        
        emit_message_sent(approval.lead_id)
        return jsonify({
            "status": "success",
            "message": "Message approved and sent" + (" (custom)" if custom_message else "")
        })
    finally:
        session.close()

@app.route('/broker/approval/<approval_id>/reject', methods=['POST'])
def reject_message(approval_id):
    """Reject a pending message"""
    data = request.json
    broker_notes = data.get('broker_notes', '')
    custom_message = data.get('custom_message', '')
    
    session = Session()
    try:
        from models import PendingApproval
        approval = session.query(PendingApproval).filter_by(id=approval_id).first()
        
        if not approval:
            return jsonify({"status": "error", "message": "Approval not found"}), 404
        
        if approval.is_approved is not None:
            return jsonify({"status": "error", "message": "Already reviewed"}), 400
        
        # Mark as rejected
        approval.is_approved = False
        approval.reviewed_at = datetime.now(IST).replace(tzinfo=None)
        approval.broker_notes = broker_notes
        
        session.commit()
        
        # If custom message provided, send that instead
        if custom_message:
            session.add(Conversation(
                lead_id=approval.lead_id,
                role='assistant',
                content=custom_message,
                sent_by='broker'
            ))
            session.commit()
            
            # Send to Kafka
            from kafka import KafkaProducer
            kafka_producer = KafkaProducer(
                bootstrap_servers='localhost:9092',
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            kafka_producer.send('broker-response', {
                'lead_id': approval.lead_id,
                'original_message': approval.user_message,
                'response': custom_message
            })
            kafka_producer.flush()
            emit_message_sent(approval.lead_id)
        
        return jsonify({
            "status": "success",
            "message": "Message rejected" + (" and custom message sent" if custom_message else "")
        })
    finally:
        session.close()

@app.route('/broker/global_settings', methods=['GET', 'PUT'])
def global_settings():
    """Get or update global broker settings"""
    from app.models import GlobalSettings
    
    session = Session()
    try:
        if request.method == 'GET':
            global_auto_send = GlobalSettings.get_auto_send(session)
            return jsonify({
                "global_auto_send": global_auto_send
            })
        else:
            data = request.json
            if 'global_auto_send' in data:
                GlobalSettings.set_auto_send(session, data['global_auto_send'])
                return jsonify({
                    "status": "success",
                    "message": f"Global auto-send {'enabled' if data['global_auto_send'] else 'disabled'}",
                    "global_auto_send": data['global_auto_send']
                })
            return jsonify({"status": "error", "message": "global_auto_send field required"}), 400
    finally:
        session.close()

@app.route('/broker/send_message', methods=['POST'])
def broker_send_message():
    """Send a message from broker to a lead"""
    data = request.json
    lead_id = data.get('lead_id')
    message = data.get('message')
    
    if not lead_id or not message:
        return jsonify({"status": "error", "message": "lead_id and message are required"}), 400
    
    session = Session()
    try:
        # Check if lead exists
        lead = session.get(Lead, lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        # Save to conversations
        session.add(Conversation(
            lead_id=lead_id,
            role='assistant',
            content=message,
            sent_by='broker'
        ))
        session.commit()
        
        # Send to Kafka
        kafka_producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        kafka_producer.send('broker-response', {
            'lead_id': lead_id,
            'original_message': '',
            'response': message
        })
        kafka_producer.flush()
        
        emit_message_sent(lead_id)
        return jsonify({
            "status": "success",
            "message": "Message sent successfully"
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

# ============ SOCKET.IO ============

@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    pass

@socketio.on('join_broker')
def handle_join_broker():
    from flask_socketio import join_room
    join_room('broker_room')
    emit('joined', {'room': 'broker_room'})

@socketio.on('join_lead')
def handle_join_lead(data):
    from flask_socketio import join_room
    lead_id = data.get('lead_id')
    if lead_id is not None:
        join_room(f'lead_{lead_id}')
        emit('joined', {'room': f'lead_{lead_id}'})

def emit_message_sent(lead_id):
    try:
        socketio.emit('message_sent', {'lead_id': lead_id, 'timestamp': datetime.now(IST).replace(tzinfo=None).isoformat()}, room='broker_room')
        socketio.emit('message_for_lead', {'lead_id': lead_id, 'timestamp': datetime.now(IST).replace(tzinfo=None).isoformat()}, room=f'lead_{lead_id}')
    except Exception as e:
        print(f"❌ emit_message_sent: {e}")

def emit_new_lead(lead_id):
    """Notify broker UI that a new lead signed up so the leads list can refresh."""
    try:
        socketio.emit('new_lead', {'lead_id': lead_id, 'timestamp': datetime.now(IST).replace(tzinfo=None).isoformat()}, room='broker_room')
    except Exception as e:
        print(f"❌ emit_new_lead: {e}")

@app.route('/internal/ws/lead_message_received/<int:lead_id>', methods=['POST'])
def ws_lead_message_received(lead_id):
    try:
        socketio.emit('new_lead_message', {'lead_id': lead_id, 'timestamp': datetime.now(IST).replace(tzinfo=None).isoformat()}, room='broker_room')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/internal/ws/message_sent/<int:lead_id>', methods=['POST'])
def ws_message_sent(lead_id):
    try:
        emit_message_sent(lead_id)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/internal/ws/pending_approval/<int:lead_id>/<approval_id>', methods=['POST'])
def ws_pending_approval(lead_id, approval_id):
    try:
        socketio.emit('new_pending_approval', {'lead_id': lead_id, 'approval_id': approval_id, 'timestamp': datetime.now(IST).replace(tzinfo=None).isoformat()}, room='broker_room')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============ PROPERTY ENDPOINTS ============

@app.route('/broker/properties', methods=['GET'])
def get_broker_properties():
    """Get all properties for a broker"""
    session = Session()
    try:
        # For now, we'll get broker_id from query param or header
        # TODO: Get from authenticated broker session
        broker_id = request.args.get('broker_id')
        
        if not broker_id:
            return jsonify({"status": "error", "message": "broker_id is required"}), 400
        
        # Convert to integer
        try:
            broker_id = int(broker_id)
        except ValueError:
            return jsonify({"status": "error", "message": "broker_id must be an integer"}), 400
        
        from models import Property
        properties = session.query(Property).filter_by(broker_id=broker_id).order_by(Property.created_at.desc()).all()
        
        return jsonify({
            "status": "success",
            "properties": [p.to_dict() for p in properties]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/broker/property', methods=['POST'])
def add_property():
    """Add a new property"""
    session = Session()
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['broker_id', 'title', 'locality', 'bhk', 'budget', 'furnishing_status', 'property_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"{field} is required"}), 400
        
        broker_id = int(data['broker_id'])
        broker = session.get(Lead, broker_id)
        if not broker:
            return jsonify({
                "status": "error",
                "message": "Broker account not found. If you cleared all data, please log in or register again."
            }), 400
        
        from models import Property
        from models.property import FurnishingStatus, PropertyType, PropertyStatus
        
        # Create property
        property_obj = Property(
            broker_id=broker_id,
            title=data['title'],
            description=data.get('description'),
            locality=data['locality'],
            bhk=int(data['bhk']),
            budget=float(data['budget']),
            furnishing_status=FurnishingStatus(data['furnishing_status']),
            property_type=PropertyType(data['property_type']),
            area_sqft=int(data['area_sqft']) if data.get('area_sqft') else None,
            amenities=data.get('amenities'),
            status=PropertyStatus.AVAILABLE
        )
        
        # Handle available_from date
        if data.get('available_from'):
            try:
                property_obj.available_from = datetime.fromisoformat(data['available_from'])
            except:
                pass
        
        session.add(property_obj)
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Property added successfully",
            "property": property_obj.to_dict()
        })
    except ValueError as e:
        session.rollback()
        return jsonify({"status": "error", "message": f"Invalid value: {str(e)}"}), 400
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/broker/property/<property_id>', methods=['PUT'])
def update_property(property_id):
    """Update a property"""
    session = Session()
    try:
        from models import Property
        from models.property import FurnishingStatus, PropertyType, PropertyStatus
        
        property_obj = session.query(Property).filter_by(id=property_id).first()
        if not property_obj:
            return jsonify({"status": "error", "message": "Property not found"}), 404
        
        data = request.json
        
        # Update fields
        if 'title' in data:
            property_obj.title = data['title']
        if 'description' in data:
            property_obj.description = data['description']
        if 'locality' in data:
            property_obj.locality = data['locality']
        if 'bhk' in data:
            property_obj.bhk = int(data['bhk'])
        if 'budget' in data:
            property_obj.budget = float(data['budget'])
        if 'furnishing_status' in data:
            property_obj.furnishing_status = FurnishingStatus(data['furnishing_status'])
        if 'property_type' in data:
            property_obj.property_type = PropertyType(data['property_type'])
        if 'area_sqft' in data:
            property_obj.area_sqft = int(data['area_sqft']) if data['area_sqft'] else None
        if 'amenities' in data:
            property_obj.amenities = data['amenities']
        if 'status' in data:
            property_obj.status = PropertyStatus(data['status'])
        if 'available_from' in data:
            try:
                property_obj.available_from = datetime.fromisoformat(data['available_from'])
            except:
                pass
        
        property_obj.updated_at = datetime.now(IST).replace(tzinfo=None)
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Property updated successfully",
            "property": property_obj.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/broker/property/<property_id>', methods=['DELETE'])
def delete_property(property_id):
    """Delete a property"""
    session = Session()
    try:
        from models import Property, PropertyMedia
        from app.config.cloudinary_config import delete_media
        
        property_obj = session.query(Property).filter_by(id=property_id).first()
        if not property_obj:
            return jsonify({"status": "error", "message": "Property not found"}), 404
        
        # Delete all media from Cloudinary
        for media in property_obj.media:
            resource_type = "video" if media.media_type.value == "video" else "image"
            delete_media(media.cloudinary_public_id, resource_type)
        
        # Delete property (cascade will delete media records)
        session.delete(property_obj)
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Property deleted successfully"
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/broker/property/<property_id>/media', methods=['POST'])
def upload_property_media(property_id):
    """Upload media for a property"""
    session = Session()
    try:
        from models import Property, PropertyMedia
        from models.property_media import MediaType
        from app.config.cloudinary_config import upload_media, generate_thumbnail
        
        property_obj = session.query(Property).filter_by(id=property_id).first()
        if not property_obj:
            return jsonify({"status": "error", "message": "Property not found"}), 404
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        # Upload to Cloudinary
        result = upload_media(file, folder=f"properties/{property_id}")
        
        if not result['success']:
            return jsonify({"status": "error", "message": result['error']}), 500
        
        # Determine media type
        media_type = MediaType.VIDEO if result['resource_type'] == 'video' else MediaType.IMAGE
        
        # Generate thumbnail for videos
        thumbnail_url = None
        if media_type == MediaType.VIDEO:
            thumbnail_url = generate_thumbnail(result['public_id'])
        
        # Get current max order
        max_order = session.query(PropertyMedia).filter_by(property_id=property_id).count()
        
        # Create media record
        media_obj = PropertyMedia(
            property_id=property_id,
            cloudinary_public_id=result['public_id'],
            cloudinary_url=result['url'],
            media_type=media_type,
            thumbnail_url=thumbnail_url,
            file_size=result['bytes'],
            order=max_order
        )
        
        session.add(media_obj)
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Media uploaded successfully",
            "media": media_obj.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/broker/property/media/<media_id>', methods=['DELETE'])
def delete_property_media(media_id):
    """Delete a specific media file"""
    session = Session()
    try:
        from models import PropertyMedia
        from app.config.cloudinary_config import delete_media
        
        media_obj = session.query(PropertyMedia).filter_by(id=media_id).first()
        if not media_obj:
            return jsonify({"status": "error", "message": "Media not found"}), 404
        
        # Delete from Cloudinary
        resource_type = "video" if media_obj.media_type.value == "video" else "image"
        delete_result = delete_media(media_obj.cloudinary_public_id, resource_type)
        
        if not delete_result['success']:
            return jsonify({"status": "error", "message": delete_result['error']}), 500
        
        # Delete from database
        session.delete(media_obj)
        session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Media deleted successfully"
        })
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

@app.route('/lead/properties/recommended', methods=['GET'])
def get_recommended_properties():
    """Get all recommended properties for a lead"""
    lead_id = request.args.get('lead_id', type=int)
    
    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400
    
    try:
        session = Session()
        from app.models import PropertyRecommendation, Property
        
        # Get all recommendations with property details
        recommendations = session.query(PropertyRecommendation).filter_by(
            lead_id=lead_id
        ).order_by(PropertyRecommendation.recommended_at.desc()).all()
        
        result = []
        for rec in recommendations:
            prop = session.query(Property).filter_by(id=rec.property_id).first()
            if prop:
                rec_data = rec.to_dict()
                rec_data['property'] = prop.to_dict()
                result.append(rec_data)
        
        session.close()
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error fetching recommended properties: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/lead/property/<property_id>/view', methods=['POST'])
def mark_property_viewed(property_id):
    """Mark a property as viewed by a lead"""
    data = request.json
    lead_id = data.get('lead_id')
    
    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400
    
    try:
        session = Session()
        from app.models import PropertyRecommendation
        
        recommendation = session.query(PropertyRecommendation).filter_by(
            lead_id=lead_id,
            property_id=property_id
        ).first()
        
        if recommendation:
            recommendation.viewed = 1
            session.commit()
            session.close()
            return jsonify({'status': 'success', 'viewed': True})
        else:
            session.close()
            return jsonify({'error': 'Recommendation not found'}), 404
            
    except Exception as e:
        print(f"❌ Error marking property as viewed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/lead/property/<property_id>/interest', methods=['POST'])
def update_property_interest(property_id):
    """Update interest status for a property"""
    data = request.json
    lead_id = data.get('lead_id')
    interested = data.get('interested')  # True, False, or None
    feedback = data.get('feedback')
    
    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400
    
    try:
        session = Session()
        from app.models import PropertyRecommendation
        
        recommendation = session.query(PropertyRecommendation).filter_by(
            lead_id=lead_id,
            property_id=property_id
        ).first()
        
        if recommendation:
            if interested is not None:
                recommendation.interested = 1 if interested else 0
            if feedback:
                recommendation.feedback = feedback
            session.commit()
            session.close()
            return jsonify({'status': 'success'})
        else:
            session.close()
            return jsonify({'error': 'Recommendation not found'}), 404
            
    except Exception as e:
        print(f"❌ Error updating property interest: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug/clear-recommendations/<int:lead_id>', methods=['DELETE'])
def clear_recommendations(lead_id):
    """DEBUG: Clear all recommendations for a lead"""
    try:
        session = Session()
        from app.models import PropertyRecommendation
        
        deleted = session.query(PropertyRecommendation).filter_by(lead_id=lead_id).delete()
        session.commit()
        session.close()
        
        print(f"🗑️ Cleared {deleted} recommendations for lead {lead_id}")
        return jsonify({'status': 'success', 'deleted': deleted})
    except Exception as e:
        print(f"❌ Error clearing recommendations: {e}")
        return jsonify({'error': str(e)}), 500


def _do_clear_all_tables(session):
    """Perform the actual clear-all. Returns deleted dict on success. Raises on failure."""
    from models import Requirements
    from app.models import PendingApproval, GlobalSettings, PropertyRecommendation
    from sqlalchemy import text

    deleted = {}
    deleted['property_media'] = session.query(PropertyMedia).delete()
    deleted['property_recommendations'] = session.query(PropertyRecommendation).delete()
    deleted['conversations'] = session.query(Conversation).delete()
    deleted['requirements'] = session.query(Requirements).delete()
    deleted['pending_approvals'] = session.query(PendingApproval).delete()
    deleted['properties'] = session.query(Property).delete()
    deleted['leads'] = session.query(Lead).delete()
    deleted['global_settings'] = session.query(GlobalSettings).delete()
    session.execute(text("SELECT setval(pg_get_serial_sequence('leads', 'id'), 1, false)"))
    session.commit()
    return deleted


CLEAR_ALL_CONFIRM_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Clear all data – Confirm</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 420px; margin: 60px auto; padding: 24px; }
    h1 { color: #c00; }
    p { color: #333; }
    input { width: 100%; padding: 10px; margin: 8px 0; box-sizing: border-box; }
    button { padding: 12px 24px; background: #c00; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }
    button:hover { background: #a00; }
    .muted { color: #666; font-size: 0.9rem; }
    .success { color: #060; }
    .error { color: #c00; }
  </style>
</head>
<body>
  <h1>⚠️ Clear all data</h1>
  <p>This will permanently delete all data from every table (leads, properties, conversations, etc.).</p>
  <p class="muted">Type <strong>confirm</strong> below to proceed.</p>
  <input type="text" id="confirmInput" placeholder="Type: confirm" autocomplete="off">
  <button type="button" id="submitBtn">Clear all data</button>
  <script>
    document.getElementById('submitBtn').onclick = function() {
      if (document.getElementById('confirmInput').value.trim().toLowerCase() === 'confirm') {
        window.location.href = '/admin/clear-all?confirm=confirm';
      } else {
        alert("Type exactly 'confirm' to proceed.");
      }
    };
  </script>
</body>
</html>
"""


@app.route('/admin/clear-all', methods=['GET', 'DELETE'])
def clear_all_tables():
    """GET: show confirmation page; with ?confirm=confirm run clear. DELETE: run clear (no confirmation)."""
    # GET without confirmation -> show browser confirmation page
    if request.method == 'GET' and request.args.get('confirm') != 'confirm':
        return CLEAR_ALL_CONFIRM_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}

    session = Session()
    try:
        deleted = _do_clear_all_tables(session)
        total = sum(deleted.values())
        print(f"🗑️ Cleared all tables: {deleted} (total rows: {total}), leads.id sequence reset to 1")
        if request.method == 'GET':
            lines = [f"<p class='success'>Deleted {total} rows across all tables.</p>", "<ul>"]
            for table, count in deleted.items():
                lines.append(f"<li>{table}: {count}</li>")
            lines.append("</ul>")
            return (
                "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Done</title>"
                "<style>body{font-family:system-ui;max-width:420px;margin:60px auto;} .success{color:#060;}</style></head>"
                f"<body><h1>Done</h1>{''.join(lines)}</body></html>"
            ), 200, {'Content-Type': 'text/html; charset=utf-8'}
        return jsonify({
            "status": "success",
            "message": f"Deleted {total} rows across all tables",
            "deleted": deleted
        })
    except Exception as e:
        session.rollback()
        print(f"❌ Error clearing all tables: {e}")
        if request.method == 'GET':
            return f"<html><body><p class='error'>Error: {e}</p></body></html>", 500, {'Content-Type': 'text/html; charset=utf-8'}
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()


if __name__ == '__main__':
    print("🚀 Starting Flask API with Socket.IO on port 5001...")
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)