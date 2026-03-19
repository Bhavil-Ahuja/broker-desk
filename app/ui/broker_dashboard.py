import streamlit as st
import streamlit.components.v1 as components
import requests
import time

API_BASE_URL = 'http://localhost:5001'

st.set_page_config(page_title="Broker Dashboard", page_icon="🏢", layout="wide")

# Polling-based refresh (no WebSockets - works reliably with Streamlit)
def broker_polling_listener(initial_pending_count):
    """Poll /broker/leads every 1.5s; reload if new messages or new pending approvals."""
    html_code = f"""
    <script>
        let lastSignature = null;
        function getSignature(data) {{
            const leads = data.leads || [];
            const pending = leads.reduce((s, l) => s + (l.pending_approvals || 0), 0);
            const times = leads.map(l => (l.lead && l.lead.id) + ':' + (l.latest_message_time || '')).join('|');
            return pending + ':' + times;
        }}
        function showNotification(message) {{
            const notif = document.createElement('div');
            notif.style.cssText = 'position:fixed;top:80px;right:20px;background:#ffc107;color:#000;padding:12px 18px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);font-weight:bold;';
            notif.textContent = message;
            document.body.appendChild(notif);
            setTimeout(() => notif.remove(), 2500);
        }}
        setInterval(() => {{
            fetch('{API_BASE_URL}/broker/leads')
                .then(r => r.json())
                .then(data => {{
                    const sig = getSignature(data);
                    if (lastSignature !== null && sig !== lastSignature) {{
                        const pending = data.leads.reduce((s, l) => s + l.pending_approvals, 0);
                        const prevPending = lastSignature.split(':')[0];
                        if (parseInt(pending, 10) > parseInt(prevPending, 10)) showNotification('🔔 New approval needed');
                        else showNotification('📩 New activity');
                        setTimeout(() => window.location.reload(), 400);
                    }}
                    lastSignature = sig;
                }})
                .catch(() => {{}});
        }}, 1500);
    </script>
    """
    return components.html(html_code, height=0)

# Initialize session state
if 'selected_lead_id' not in st.session_state:
    st.session_state.selected_lead_id = None
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'clear_message_box' not in st.session_state:
    st.session_state.clear_message_box = False
if 'broker_id' not in st.session_state:
    st.session_state.broker_id = 1  # TODO: Get from authentication
if 'show_add_property' not in st.session_state:
    st.session_state.show_add_property = False
if 'show_upload_media' not in st.session_state:
    st.session_state.show_upload_media = False
if 'new_property_id' not in st.session_state:
    st.session_state.new_property_id = None

# Get page from query params, default to 'leads'
query_params = st.query_params
current_page = query_params.get('page', 'leads')

def set_page(page_name):
    """Set the current page and persist in query params"""
    st.query_params['page'] = page_name
    st.rerun()

# Restore selected_lead_id from query params
query_params = st.query_params
if 'lead_id' in query_params and not st.session_state.selected_lead_id:
    try:
        st.session_state.selected_lead_id = int(query_params['lead_id'])
    except:
        pass

def set_selected_lead(lead_id):
    """Set selected lead and persist in query params"""
    st.session_state.selected_lead_id = lead_id
    if lead_id:
        st.query_params['lead_id'] = str(lead_id)
    else:
        st.query_params.clear()

def get_all_leads():
    """Fetch all leads"""
    try:
        response = requests.get(f'{API_BASE_URL}/broker/leads', timeout=5)
        if response.status_code == 200:
            return response.json().get('leads', [])
    except Exception as e:
        st.error(f"Error fetching leads: {e}")
    return []

def get_lead_details(lead_id):
    """Fetch detailed information about a lead"""
    try:
        response = requests.get(f'{API_BASE_URL}/broker/lead/{lead_id}', timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching lead details: {e}")
    return None

def toggle_auto_send(lead_id, auto_send):
    """Toggle auto_send for a lead"""
    try:
        response = requests.put(
            f'{API_BASE_URL}/broker/lead/{lead_id}/auto_send',
            json={'auto_send': auto_send},
            timeout=5
        )
        if response.status_code == 200:
            return True, response.json().get('message')
        else:
            return False, response.json().get('message', 'Failed')
    except Exception as e:
        return False, str(e)

def approve_message(approval_id, broker_notes='', custom_message=''):
    """Approve and send a pending message (with optional custom message)"""
    try:
        response = requests.post(
            f'{API_BASE_URL}/broker/approval/{approval_id}/approve',
            json={'broker_notes': broker_notes, 'custom_message': custom_message},
            timeout=5
        )
        if response.status_code == 200:
            return True, response.json().get('message', 'Message sent')
        else:
            return False, response.json().get('message', 'Failed')
    except Exception as e:
        return False, str(e)

def reject_message(approval_id, custom_message='', broker_notes=''):
    """Reject a pending message"""
    try:
        response = requests.post(
            f'{API_BASE_URL}/broker/approval/{approval_id}/reject',
            json={'broker_notes': broker_notes, 'custom_message': custom_message},
            timeout=5
        )
        if response.status_code == 200:
            return True, response.json().get('message')
        else:
            return False, response.json().get('message', 'Failed')
    except Exception as e:
        return False, str(e)

def send_broker_message(lead_id, message):
    """Send a message from broker to lead"""
    try:
        response = requests.post(
            f'{API_BASE_URL}/broker/send_message',
            json={'lead_id': lead_id, 'message': message},
            timeout=5
        )
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            return False, response.json().get('message', 'Failed')
    except Exception as e:
        return False, str(e)

def get_broker_properties(broker_id):
    """Fetch all properties for a broker"""
    try:
        response = requests.get(f'{API_BASE_URL}/broker/properties?broker_id={broker_id}', timeout=5)
        if response.status_code == 200:
            return response.json().get('properties', [])
    except Exception as e:
        st.error(f"Error fetching properties: {e}")
    return []

def add_property(property_data):
    """Add a new property"""
    try:
        response = requests.post(f'{API_BASE_URL}/broker/property', json=property_data, timeout=10)
        if response.status_code == 200:
            return True, response.json().get('property')
        else:
            return False, response.json().get('message', 'Failed to add property')
    except Exception as e:
        return False, str(e)

def upload_property_media(property_id, file):
    """Upload media for a property"""
    try:
        files = {'file': file}
        response = requests.post(
            f'{API_BASE_URL}/broker/property/{property_id}/media',
            files=files,
            timeout=30
        )
        if response.status_code == 200:
            return True, response.json().get('media')
        else:
            return False, response.json().get('message', 'Failed to upload media')
    except Exception as e:
        return False, str(e)

def delete_property(property_id):
    """Delete a property"""
    try:
        response = requests.delete(f'{API_BASE_URL}/broker/property/{property_id}', timeout=10)
        if response.status_code == 200:
            return True, response.json().get('message')
        else:
            return False, response.json().get('message', 'Failed to delete property')
    except Exception as e:
        return False, str(e)

def delete_media(media_id):
    """Delete a specific media file"""
    try:
        response = requests.delete(f'{API_BASE_URL}/broker/property/media/{media_id}', timeout=10)
        if response.status_code == 200:
            return True, response.json().get('message')
        else:
            return False, response.json().get('message', 'Failed to delete media')
    except Exception as e:
        return False, str(e)

def get_global_settings():
    """Fetch global settings"""
    try:
        response = requests.get(f'{API_BASE_URL}/broker/global_settings', timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {'global_auto_send': True}

def update_global_auto_send(enabled):
    """Update global auto_send setting"""
    try:
        response = requests.put(
            f'{API_BASE_URL}/broker/global_settings',
            json={'global_auto_send': enabled},
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

def generate_ai_insights(lead, requirements, conversations):
    """Generate AI insights about a lead"""
    insights = []
    
    # Urgency analysis
    if requirements and requirements.get('move_in_date'):
        from datetime import datetime
        try:
            move_in = datetime.fromisoformat(requirements['move_in_date'][:10])
            days_until = (move_in - datetime.now()).days
            if days_until < 15:
                insights.append({
                    'type': 'warning',
                    'text': f"🔥 URGENT: Wants to move in {days_until} days ({move_in.strftime('%b %d')})"
                })
            elif days_until < 30:
                insights.append({
                    'type': 'info',
                    'text': f"⏰ Moderate urgency: Move-in in {days_until} days"
                })
        except:
            pass
    
    # Engagement analysis
    message_count = len(conversations)
    if message_count == 0:
        insights.append({'type': 'info', 'text': '🆕 New lead - no messages yet'})
    elif message_count < 3:
        insights.append({'type': 'info', 'text': '👋 Early stage - just started conversation'})
    elif message_count > 10:
        insights.append({'type': 'success', 'text': f'💪 Highly engaged - {message_count} messages exchanged'})
    
    # Requirements completeness
    if requirements:
        complete_fields = sum([
            bool(requirements.get('bhk')),
            bool(requirements.get('preferred_locality')),
            bool(requirements.get('budget_max')),
            bool(requirements.get('furnishing')),
            bool(requirements.get('move_in_date'))
        ])
        
        if complete_fields >= 4:
            insights.append({'type': 'success', 'text': f'✨ {complete_fields}/5 requirements captured - ready to search!'})
        elif complete_fields >= 2:
            insights.append({'type': 'info', 'text': f'📋 {complete_fields}/5 requirements captured - gathering more info'})
        else:
            insights.append({'type': 'warning', 'text': f'⚠️ Only {complete_fields}/5 requirements - needs more conversation'})
    
    # Budget analysis
    if requirements and requirements.get('budget_max'):
        budget = requirements['budget_max']
        if budget > 10000000:
            insights.append({'type': 'success', 'text': '💎 Premium segment - High budget client'})
        elif budget < 2000000:
            insights.append({'type': 'info', 'text': '💰 Budget-conscious - Focus on value properties'})
    
    # State analysis
    state = lead.get('state', 'new_lead')
    if state == 'searching_properties':
        insights.append({'type': 'success', 'text': '🔍 Ready for property matching - Requirements complete!'})
    elif state == 'collecting_requirements':
        insights.append({'type': 'info', 'text': '📝 Actively collecting requirements'})
    elif state == 'new_lead':
        insights.append({'type': 'info', 'text': '🌱 Brand new lead - Make a great first impression!'})
    
    # Activity analysis
    if lead.get('last_login'):
        from datetime import datetime
        try:
            last_login = datetime.fromisoformat(lead['last_login'][:19])
            hours_since = (datetime.now() - last_login).total_seconds() / 3600
            if hours_since < 1:
                insights.append({'type': 'success', 'text': '🟢 Active now - Last seen < 1 hour ago'})
            elif hours_since < 24:
                insights.append({'type': 'info', 'text': f'🟡 Last seen {int(hours_since)} hours ago'})
            else:
                insights.append({'type': 'warning', 'text': f'🔴 Inactive - Last seen {int(hours_since/24)} days ago'})
        except:
            pass
    
    return insights if insights else [{'type': 'info', 'text': '📊 Not enough data for insights yet'}]

# Main UI
st.title("🏢 Broker Dashboard")

# Navigation buttons
nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 4])
with nav_col1:
    if st.button("👥 Leads", use_container_width=True, type="primary" if current_page == 'leads' else "secondary"):
        set_page('leads')
with nav_col2:
    if st.button("🏠 Properties", use_container_width=True, type="primary" if current_page == 'properties' else "secondary"):
        set_page('properties')

st.divider()

# ============ LEADS PAGE ============
if current_page == 'leads':
    all_leads_data = get_all_leads()
    total_pending = sum(lead['pending_approvals'] for lead in all_leads_data) if all_leads_data else 0
    
    # Inject WebSocket listener for real-time updates
    broker_polling_listener(total_pending)
    
    # Top bar - Global settings
    col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
    with col1:
        st.subheader("Lead Management")
    with col2:
        global_settings = get_global_settings()
        global_auto_send = st.toggle(
            "🌐 Global Auto-Send",
            value=global_settings.get('global_auto_send', True),
            key='global_auto_send_toggle'
        )
        if global_auto_send != global_settings.get('global_auto_send', True):
            if update_global_auto_send(global_auto_send):
                st.success("✅ Global setting updated")
                time.sleep(0.5)
                st.rerun()
    with col3:
        st.metric("Leads", len(all_leads_data))
    with col4:
        st.metric("⏸️ Pending", total_pending)
    with col5:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.session_state.refresh_counter += 1
            st.rerun()
    
    st.divider()
    
    # Main layout: Sidebar for leads list, main area for details
    leads = all_leads_data
    
    if not leads:
        st.info("📭 No leads found. Waiting for users to register...")
    else:
        # Sidebar - Leads list
        with st.sidebar:
            st.header("📋 All Leads")
            st.caption(f"{len(leads)} total leads")
            
            for lead_data in leads:
                lead = lead_data['lead']
                pending = lead_data['pending_approvals']
                
                # Create a card for each lead
                with st.container():
                    col_name, col_badge = st.columns([3, 1])
                    
                    with col_name:
                        if st.button(
                            f"👤 {lead['name']}",
                            key=f"lead_{lead['id']}",
                            use_container_width=True,
                            type="primary" if st.session_state.selected_lead_id == lead['id'] else "secondary"
                        ):
                            set_selected_lead(lead['id'])
                            st.rerun()
                    
                    with col_badge:
                        if pending > 0:
                            st.markdown(f"🔔 **{pending}**")
                    
                    st.caption(f"@{lead['username']} • {lead['state']}")
                    if lead_data['latest_message']:
                        st.caption(f"💬 {lead_data['latest_message'][:40]}...")
                    st.divider()
        
        # Main area - Lead details with 2-column layout
        if st.session_state.selected_lead_id:
            lead_details = get_lead_details(st.session_state.selected_lead_id)
            
            if lead_details:
                lead = lead_details['lead']
                conversations = lead_details['conversations']
                requirements = lead_details['requirements']
                pending_approvals = lead_details['pending_approvals']
                
                # Header with lead info and auto-send toggle
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.header(f"👤 {lead['name']}")
                    st.caption(f"@{lead['username']} • {lead['email']}")
                with col2:
                    st.metric("State", lead['state'].replace('_', ' ').title())
                with col3:
                    auto_send_enabled = st.toggle(
                        "🤖 Auto-Send",
                        value=bool(lead.get('auto_send', 1)),
                        key=f"auto_send_{lead['id']}"
                    )
                    if auto_send_enabled != bool(lead.get('auto_send', 1)):
                        success, message = toggle_auto_send(lead['id'], auto_send_enabled)
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                
                st.divider()
                
                # 2-column layout: Main chat + Right sidebar
                col_main, col_right = st.columns([2, 1])
                
                # LEFT: Main chat area
                with col_main:
                    st.subheader("💬 Conversation History")
                    
                    # Chat history with auto-scroll
                    chat_container = st.container()
                    with chat_container:
                        if conversations:
                            for conv in conversations:
                                if conv['role'] == 'user':
                                    with st.chat_message("user"):
                                        st.write(conv['content'])
                                        st.caption(conv['created_at'][:19])
                                else:
                                    with st.chat_message("assistant"):
                                        st.write(conv['content'])
                                        sent_by = conv.get('sent_by', 'ai')
                                        if sent_by == 'broker':
                                            st.caption(f"👤 Sent by Broker • {conv['created_at'][:19]}")
                                        else:
                                            st.caption(f"🤖 AI Generated • {conv['created_at'][:19]}")
                        else:
                            st.info("No conversation history yet")
                    
                    # Auto-scroll to bottom
                    components.html("""
                        <script>
                            setTimeout(() => {
                                const messages = window.parent.document.querySelectorAll('[data-testid="stChatMessageContent"]');
                                if (messages.length > 0) {
                                    messages[messages.length - 1].scrollIntoView({behavior: 'smooth', block: 'end'});
                                }
                            }, 100);
                        </script>
                    """, height=0)
                    
                    st.divider()
                    
                    # Send message box at bottom
                    st.markdown("### ✉️ Send Message to Lead")
                    with st.form(key=f"send_msg_form_{lead['id']}_{st.session_state.refresh_counter}"):
                        broker_msg = st.text_area(
                            "Type your message",
                            placeholder="Write a message to send directly to this lead...",
                            height=100
                        )
                        submit = st.form_submit_button("📤 Send Message", type="primary", use_container_width=True)
                        
                        if submit:
                            if broker_msg and broker_msg.strip():
                                success, message = send_broker_message(lead['id'], broker_msg)
                                if success:
                                    st.success(message)
                                    st.session_state.refresh_counter += 1
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("Please enter a message")
                
                # RIGHT: Sidebar for requirements, insights, pending approvals
                with col_right:
                    # Requirements section
                    with st.container():
                        st.markdown("### 📝 Requirements")
                        if requirements:
                            st.metric("BHK", requirements.get('bhk', 'Not specified'))
                            st.metric("Location", requirements.get('preferred_locality', 'Not specified'))
                            
                            budget_max = requirements.get('budget_max')
                            if budget_max is not None:
                                budget = f"Up to ₹{budget_max/100000:.1f}L" if budget_max >= 100000 else f"Up to ₹{budget_max:,.0f}"
                            else:
                                budget = 'Not specified'
                            st.metric("Budget", budget)
                            
                            furnishing = requirements.get('furnishing', 'Not specified')
                            if furnishing == 'full':
                                furnishing = 'Fully Furnished'
                            elif furnishing == 'semi':
                                furnishing = 'Semi Furnished'
                            st.metric("Furnishing", furnishing)
                            
                            if requirements.get('move_in_date'):
                                st.info(f"📅 {requirements['move_in_date'][:10]}")
                            if requirements.get('other_requirements'):
                                st.info(f"💭 {requirements['other_requirements']}")
                            
                            st.caption(f"Created: {requirements.get('created_at', 'N/A')[:19]}")
                            st.caption(f"Updated: {requirements.get('last_modified_at', 'N/A')[:19]}")
                        else:
                            st.info("No requirements yet")
                        
                        st.divider()
                    
                    # AI Insights section
                    with st.container():
                        st.markdown("### 🧠 AI Insights")
                        insights = generate_ai_insights(lead, requirements, conversations)
                        for insight in insights:
                            if insight['type'] == 'warning':
                                st.warning(f"{insight['text']}")
                            elif insight['type'] == 'info':
                                st.info(f"{insight['text']}")
                            elif insight['type'] == 'success':
                                st.success(f"{insight['text']}")
                        
                        st.divider()
                    
                    # Pending approvals section
                    with st.container():
                        st.markdown(f"### ⏸️ Approvals ({len(pending_approvals)})")
                        
                        if pending_approvals:
                            for approval in pending_approvals:
                                with st.expander(f"📬 {approval['created_at'][:19]}", expanded=True):
                                    st.markdown("**User:**")
                                    st.caption(approval['user_message'])
                                    
                                    st.markdown("**AI:**")
                                    st.caption(approval['ai_message'])
                                    
                                    # Edit message
                                    edit_message = st.text_area(
                                        "✏️ Edit (optional)",
                                        key=f"edit_{approval['id']}",
                                        placeholder="Override AI...",
                                        height=80
                                    )
                                    
                                    # Broker notes
                                    broker_notes = st.text_input(
                                        "📝 Notes",
                                        key=f"notes_{approval['id']}",
                                        placeholder="Internal notes..."
                                    )
                                    
                                    # Action buttons
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("✅", key=f"approve_{approval['id']}", use_container_width=True, type="primary"):
                                            success, message = approve_message(approval['id'], broker_notes, edit_message)
                                            if success:
                                                st.success(message)
                                                time.sleep(0.5)
                                                st.rerun()
                                            else:
                                                st.error(message)
                                    with col2:
                                        if st.button("❌", key=f"reject_{approval['id']}", use_container_width=True):
                                            success, message = reject_message(approval['id'], '', broker_notes)
                                            if success:
                                                st.success(message)
                                                time.sleep(0.5)
                                                st.rerun()
                                            else:
                                                st.error(message)
                        else:
                            st.info("No pending approvals")
        else:
            st.info("👈 Select a lead from the sidebar to view details")

# ============ PROPERTIES PAGE ============
if current_page == 'properties':
    
    st.subheader("🏠 Property Management")
    
    # Top bar
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.caption("Manage your property listings")
    with col2:
        if st.button("➕ Add New Property", use_container_width=True, type="primary"):
            st.session_state.show_add_property = True
            st.session_state.new_property_id = None  # Reset upload state
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # Add new property form
    if st.session_state.get('show_add_property', False):
        st.markdown("### ➕ Add New Property")
        
        with st.form("add_property_form"):
            st.markdown("#### 📝 Property Details")
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("Property Title*", placeholder="e.g., 3BHK Luxury Apartment in Whitefield")
                locality = st.text_input("Locality*", placeholder="e.g., Whitefield, Koramangala")
                bhk = st.number_input("BHK*", min_value=1, max_value=10, value=2)
                budget = st.number_input("Budget (₹)*", min_value=0, value=5000000, step=100000)
            
            with col2:
                property_type = st.selectbox("Property Type*", 
                    ["apartment", "villa", "independent_house", "studio", "penthouse"])
                furnishing_status = st.selectbox("Furnishing*", 
                    ["furnished", "semi-furnished", "unfurnished"])
                area_sqft = st.number_input("Area (sq ft)", min_value=0, value=1200, step=50)
                available_from = st.date_input("Available From")
            
            amenities = st.text_area("Amenities", 
                placeholder="e.g., Gym, Swimming Pool, Parking, Security", height=80)
            
            description = st.text_area("Description", 
                placeholder="Describe the property...", height=100)
            
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                submit = st.form_submit_button("💾 Save & Continue to Upload Media", use_container_width=True, type="primary")
            with col_cancel:
                cancel_form = st.form_submit_button("❌ Cancel", use_container_width=True)
            
            if cancel_form:
                st.session_state.show_add_property = False
                st.rerun()
            
            if submit:
                if not title or not locality:
                    st.error("Title and Locality are required!")
                else:
                    property_data = {
                        'broker_id': st.session_state.broker_id,
                        'title': title,
                        'description': description,
                        'locality': locality,
                        'bhk': bhk,
                        'budget': budget,
                        'furnishing_status': furnishing_status,
                        'property_type': property_type,
                        'area_sqft': area_sqft,
                        'amenities': amenities,
                        'available_from': available_from.isoformat() if available_from else None
                    }
                    
                    success, result = add_property(property_data)
                    if success:
                        st.success("✅ Property added successfully!")
                        st.session_state.show_add_property = False
                        st.session_state.new_property_id = result['id']
                        st.session_state.show_upload_media = True
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"Failed to add property: {result}")
    
    # Upload media for newly added property
    if st.session_state.get('show_upload_media') and st.session_state.get('new_property_id'):
        property_id = st.session_state.new_property_id
        
        st.markdown("### 📸 Upload Property Media")
        st.info(f"✅ Property created! Now add images and videos.")
        
        uploaded_files = st.file_uploader(
            "Choose images or videos",
            type=['jpg', 'jpeg', 'png', 'mp4', 'mov', 'webp'],
            accept_multiple_files=True,
            key=f"upload_new_{property_id}",
            help="You can select multiple files at once"
        )
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if uploaded_files and st.button("📤 Upload All Files", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                success_count = 0
                
                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Uploading {file.name}...")
                    success, result = upload_property_media(property_id, file)
                    if success:
                        success_count += 1
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                st.success(f"✅ Uploaded {success_count}/{len(uploaded_files)} files!")
                time.sleep(1)
                st.session_state.new_property_id = None
                st.session_state.show_upload_media = False
                st.rerun()
        
        with col2:
            if st.button("⏭️ Skip", use_container_width=True):
                st.session_state.new_property_id = None
                st.session_state.show_upload_media = False
                st.rerun()
        
        with col3:
            if st.button("✅ Done", use_container_width=True, type="secondary"):
                st.session_state.new_property_id = None
                st.session_state.show_upload_media = False
                st.rerun()
        
        st.divider()
    
    # List all properties
    if not st.session_state.get('show_add_property') and not st.session_state.get('show_upload_media'):
        st.markdown("### 📋 Your Property Listings")
        properties = get_broker_properties(st.session_state.broker_id)
        
        if not properties:
            st.info("📭 No properties found. Click 'Add New Property' to get started!")
        else:
            st.caption(f"Showing {len(properties)} properties")
            
            # Display properties in a grid
            for prop in properties:
                with st.container():
                    st.markdown(f"#### 🏠 {prop['title']}")
                    
                    # Property details in columns
                    col1, col2, col3 = st.columns([3, 3, 2])
                    
                    with col1:
                        st.markdown(f"""
                        **📍 Location:** {prop['locality']}  
                        **🛏️ Configuration:** {prop['bhk']} BHK  
                        **💰 Budget:** ₹{prop['budget']:,.0f}  
                        **🏢 Type:** {prop['property_type'].replace('_', ' ').title()}
                        """)
                    
                    with col2:
                        st.markdown(f"""
                        **🪑 Furnishing:** {prop['furnishing_status'].replace('_', ' ').title()}  
                        **📐 Area:** {prop['area_sqft']} sq ft  
                        **✅ Status:** {prop['status'].title()}  
                        **📅 Created:** {prop['created_at'][:10]}
                        """)
                    
                    with col3:
                        # Action buttons
                        if st.button("➕ Add Media", key=f"add_media_{prop['id']}", use_container_width=True, type="secondary"):
                            st.session_state[f"upload_mode_{prop['id']}"] = True
                            st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"del_{prop['id']}", use_container_width=True):
                            if st.session_state.get(f"confirm_del_{prop['id']}", False):
                                with st.spinner("Deleting..."):
                                    success, message = delete_property(prop['id'])
                                    if success:
                                        st.success(message)
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(message)
                            else:
                                st.session_state[f"confirm_del_{prop['id']}"] = True
                                st.warning("⚠️ Click again to confirm")
                                st.rerun()
                    
                    # Description and amenities
                    if prop.get('description'):
                        with st.expander("📄 Description"):
                            st.write(prop['description'])
                    
                    if prop.get('amenities'):
                        with st.expander("🎯 Amenities"):
                            st.write(prop['amenities'])
                    
                    # Upload media section (collapsible)
                    if st.session_state.get(f"upload_mode_{prop['id']}", False):
                        with st.expander("📸 Upload More Media", expanded=True):
                            new_files = st.file_uploader(
                                "Add images or videos",
                                type=['jpg', 'jpeg', 'png', 'mp4', 'mov', 'webp'],
                                accept_multiple_files=True,
                                key=f"upload_existing_{prop['id']}"
                            )
                            
                            col_up, col_cancel = st.columns([1, 1])
                            with col_up:
                                if new_files and st.button("📤 Upload", key=f"up_btn_{prop['id']}", type="primary", use_container_width=True):
                                    progress = st.progress(0)
                                    success_count = 0
                                    for idx, file in enumerate(new_files):
                                        success, result = upload_property_media(prop['id'], file)
                                        if success:
                                            success_count += 1
                                        progress.progress((idx + 1) / len(new_files))
                                    st.success(f"✅ Uploaded {success_count}/{len(new_files)} files!")
                                    time.sleep(0.5)
                                    st.session_state[f"upload_mode_{prop['id']}"] = False
                                    st.rerun()
                            
                            with col_cancel:
                                if st.button("❌ Cancel", key=f"cancel_up_{prop['id']}", use_container_width=True):
                                    st.session_state[f"upload_mode_{prop['id']}"] = False
                                    st.rerun()
                    
                    # Display existing media in a gallery
                    if prop.get('media') and len(prop['media']) > 0:
                        with st.expander(f"🖼️ Media Gallery ({len(prop['media'])} files)", expanded=True):
                            # Add CSS for consistent sizing - only affects gallery, not fullscreen
                            st.markdown("""
                            <style>
                                /* Only target images in columns, not fullscreen */
                                div[data-testid="column"] .stImage img:not(.fullscreen) {
                                    width: 100%;
                                    height: 250px;
                                    object-fit: cover;
                                    border-radius: 8px;
                                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                }
                                
                                /* Video in gallery */
                                div[data-testid="column"] video {
                                    width: 100%;
                                    height: 250px;
                                    object-fit: cover;
                                    border-radius: 8px;
                                }
                                
                                /* Ensure fullscreen works properly */
                                button[title="View fullscreen"] {
                                    z-index: 1000 !important;
                                }
                            </style>
                            """, unsafe_allow_html=True)
                            
                            # Create rows of 3 images with consistent sizing
                            media_list = prop['media']
                            for i in range(0, len(media_list), 3):
                                cols = st.columns(3, gap="medium")
                                for j in range(3):
                                    idx = i + j
                                    if idx < len(media_list):
                                        media = media_list[idx]
                                        with cols[j]:
                                            # Display media - use ORIGINAL URL for fullscreen clarity
                                            if media['media_type'] == 'image':
                                                # Pass original URL - CSS handles gallery size, fullscreen gets full quality
                                                st.image(media['cloudinary_url'], use_container_width=True)
                                            else:
                                                # For videos
                                                st.video(media['cloudinary_url'])
                                            
                                            # Delete button - full width to match image
                                            delete_key = f"del_media_{media['id']}"
                                            
                                            if st.session_state.get(f"confirm_{delete_key}", False):
                                                # Show confirmation message above buttons
                                                st.warning("⚠️ Confirm deletion?")
                                                # Show confirmation buttons side by side
                                                btn_col1, btn_col2 = st.columns(2, gap="small")
                                                with btn_col1:
                                                    if st.button("❌ Cancel", key=f"cancel_{delete_key}", use_container_width=True):
                                                        st.session_state.pop(f"confirm_{delete_key}", None)
                                                        st.rerun()
                                                with btn_col2:
                                                    if st.button("✅ Confirm", key=f"confirm_yes_{delete_key}", use_container_width=True, type="primary"):
                                                        with st.spinner("Deleting..."):
                                                            success, message = delete_media(media['id'])
                                                            if success:
                                                                st.success("✅ Deleted!")
                                                                time.sleep(0.3)
                                                                st.session_state.pop(f"confirm_{delete_key}", None)
                                                                st.rerun()
                                                            else:
                                                                st.error(f"❌ {message}")
                                            else:
                                                # Show delete button - full width matching image
                                                if st.button("🗑️ Delete", key=delete_key, use_container_width=True, help=f"Delete this {media['media_type']}"):
                                                    st.session_state[f"confirm_{delete_key}"] = True
                                                    st.rerun()
                    else:
                        st.info("📭 No media uploaded yet. Click 'Add Media' to upload.")
                    
                    st.divider()
