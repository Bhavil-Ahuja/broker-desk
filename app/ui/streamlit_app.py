import streamlit as st
import streamlit.components.v1 as components
import requests
import time

# Configure page for wide layout
st.set_page_config(
    page_title="Real Estate Broker Chat",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

API_BASE_URL = 'http://localhost:5001'

# Custom CSS for better property panel display
st.markdown("""
<style>
    /* Make property detail panel sticky */
    [data-testid="column"]:last-child {
        position: sticky;
        top: 60px;
        max-height: calc(100vh - 80px);
        overflow-y: auto;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 10px;
    }
    
    /* Improve chat container */
    .stChatMessage {
        margin-bottom: 1rem;
    }
    
    /* Better spacing for property cards */
    .property-card {
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Polling-based updates (no WebSockets - works reliably with Streamlit)
def message_listener(lead_id, last_msg_count, session_token):
    """Poll /history every 1s; reload when new messages appear (broker reply or any new message)."""
    import json as _json
    token_js = _json.dumps(session_token or "")
    html_code = f"""
    <script>
        let lastMessageCount = {last_msg_count};
        const sessionToken = {token_js};
        if (sessionToken) {{
            setInterval(() => {{
                fetch('{API_BASE_URL}/history', {{ headers: {{ 'Authorization': sessionToken }} }})
                    .then(r => r.json())
                    .then(data => {{
                        if (data.history && data.history.length > lastMessageCount) {{
                            window.location.reload();
                        }}
                    }})
                    .catch(() => {{}});
            }}, 1000);
        }}
    </script>
    """
    return components.html(html_code, height=0)

# Initialize session state
if 'session_token' not in st.session_state:
    st.session_state.session_token = None
if 'user' not in st.session_state:
    st.session_state.user = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'waiting_for_response' not in st.session_state:
    st.session_state.waiting_for_response = False
if 'last_message_count' not in st.session_state:
    st.session_state.last_message_count = 0
if 'show_clear_confirm' not in st.session_state:
    st.session_state.show_clear_confirm = False
if 'show_delete_confirm' not in st.session_state:
    st.session_state.show_delete_confirm = False
if 'show_register' not in st.session_state:
    st.session_state.show_register = False
if 'selected_property' not in st.session_state:
    st.session_state.selected_property = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 'chat'

def load_history():
    """Load chat history from database"""
    try:
        if not st.session_state.session_token:
            print("⚠️ Cannot load history - no session token")
            return
            
        response = requests.get(
            f'{API_BASE_URL}/history',
            headers={'Authorization': st.session_state.session_token},
            timeout=5
        )
        print(f"📥 History response status: {response.status_code}")
        
        if response.status_code == 200:
            history = response.json().get('history', [])
            print(f"📥 Loaded {len(history)} messages from DB")
            st.session_state.messages = [
                {'role': msg['role'], 'content': msg['content']}
                for msg in history
            ]
            st.session_state.last_message_count = len(st.session_state.messages)
        else:
            print(f"❌ History load failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Could not load history: {e}")
        import traceback
        traceback.print_exc()

# Check for session token in query params (for persistence across refreshes)
query_params = st.query_params
if 'token' in query_params and not st.session_state.session_token:
    token = query_params['token']
    # Validate token by trying to fetch user data
    try:
        response = requests.get(
            f'{API_BASE_URL}/validate',
            headers={'Authorization': token},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.session_token = token
            st.session_state.user = data['user']
            # Load chat history after restoring session
            load_history()
            print(f"✅ Session restored from query params for user {data['user']['username']}")
    except Exception as e:
        # Invalid token, clear it
        print(f"❌ Failed to restore session: {e}")
        st.query_params.clear()

def set_session_token(token):
    """Set session token in both session state and query params"""
    st.session_state.session_token = token
    st.query_params['token'] = token

def clear_session_token():
    """Clear session token from both session state and query params"""
    st.session_state.session_token = None
    st.session_state.user = None
    st.query_params.clear()

def register(username, name, email, password):
    """Register a new user"""
    try:
        response = requests.post(
            f'{API_BASE_URL}/register',
            json={'username': username, 'name': name, 'email': email, 'password': password},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            set_session_token(data['session_token'])
            st.session_state.user = data['user']
            # Load chat history
            load_history()
            return True, "Registration successful!"
        else:
            return False, response.json().get('message', 'Registration failed')
    except Exception as e:
        return False, f"Error: {e}"

def login(username, password):
    """Login existing user"""
    try:
        response = requests.post(
            f'{API_BASE_URL}/login',
            json={'username': username, 'password': password},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            set_session_token(data['session_token'])
            st.session_state.user = data['user']
            # Load chat history
            load_history()
            return True, "Login successful!"
        else:
            return False, response.json().get('message', 'Login failed')
    except Exception as e:
        return False, f"Error: {e}"

def logout():
    """Logout user"""
    try:
        if st.session_state.session_token:
            requests.post(
                f'{API_BASE_URL}/logout',
                headers={'Authorization': st.session_state.session_token},
                timeout=5
            )
    except:
        pass
    
    clear_session_token()
    st.session_state.messages = []
    st.session_state.last_message_count = 0

def get_recommended_properties():
    """Fetch all recommended properties for the current user"""
    try:
        if not st.session_state.user or 'id' not in st.session_state.user:
            return []
        
        response = requests.get(
            f'{API_BASE_URL}/lead/properties/recommended',
            params={'lead_id': st.session_state.user['id']},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error fetching recommended properties: {e}")
        return []

def mark_property_viewed(property_id):
    """Mark a property as viewed"""
    try:
        if not st.session_state.user or 'id' not in st.session_state.user:
            return
        
        requests.post(
            f'{API_BASE_URL}/lead/property/{property_id}/view',
            json={'lead_id': st.session_state.user['id']},
            timeout=5
        )
    except Exception as e:
        print(f"Error marking property as viewed: {e}")

def wait_for_new_response_from_db():
    """Poll the database for new messages"""
    initial_count = st.session_state.last_message_count
    max_attempts = 30  # 30 seconds timeout
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f'{API_BASE_URL}/history',
                headers={'Authorization': st.session_state.session_token},
                timeout=5
            )
            if response.status_code == 200:
                history = response.json().get('history', [])
                
                # Check if we have new messages
                if len(history) > initial_count:
                    # Return only new messages
                    new_messages = [
                        {'role': msg['role'], 'content': msg['content']}
                        for msg in history[initial_count:]
                    ]
                    return new_messages
        except Exception as e:
            print(f"Error polling database: {e}")
        
        time.sleep(1)
    
    return None

# Login/Register Page
if not st.session_state.session_token:
    st.title("🏠 Real Estate Broker Chat")
    
    # Toggle between login and register
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Login", use_container_width=True, type="primary" if not st.session_state.show_register else "secondary"):
            st.session_state.show_register = False
            st.rerun()
    with col2:
        if st.button("📝 Register", use_container_width=True, type="primary" if st.session_state.show_register else "secondary"):
            st.session_state.show_register = True
            st.rerun()
    
    st.divider()
    
    if st.session_state.show_register:
        # Registration Form
        st.subheader("📝 Register New Account")
        
        with st.form("register_form"):
            username = st.text_input("Username", placeholder="Choose a unique username")
            name = st.text_input("Full Name", placeholder="Enter your full name")
            email = st.text_input("Email", placeholder="Enter your email address")
            password = st.text_input("Password", type="password", placeholder="Choose a strong password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
            submit = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit:
                if not username or not name or not email or not password:
                    st.error("All fields are required")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register(username, name, email, password)
                    if success:
                        st.success(message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)
    else:
        # Login Form
        st.subheader("🔑 Login to Your Account")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.error("Username and password are required")
                else:
                    success, message = login(username, password)
                    if success:
                        st.success(message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)

# Chat Interface (only shown when logged in)
else:
    # Inject WebSocket + polling listener for real-time updates
    if st.session_state.user and 'id' in st.session_state.user:
        message_listener(st.session_state.user['id'], len(st.session_state.messages), st.session_state.session_token)
    
    # Header with user info
    st.title("🏠 Real Estate Broker Chat")
    st.caption(f"👤 {st.session_state.user['name']} (@{st.session_state.user['username']})")
    
    # Navigation and action buttons in a cleaner layout
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("💬 Chat", use_container_width=True, type="primary" if st.session_state.current_tab == 'chat' else "secondary"):
            st.session_state.current_tab = 'chat'
            st.session_state.selected_property = None
            st.rerun()
    with col2:
        if st.button("🏠 Properties", use_container_width=True, type="primary" if st.session_state.current_tab == 'properties' else "secondary"):
            st.session_state.current_tab = 'properties'
            st.session_state.selected_property = None
            st.rerun()
    with col3:
        if st.button("🗑️ Clear Chat", type="secondary", use_container_width=True):
            st.session_state.show_clear_confirm = True
    with col4:
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    
    st.divider()

    # Clear chat confirmation dialog
    if st.session_state.show_clear_confirm:
        with st.container():
            st.warning("⚠️ This will delete all conversations and requirements. Are you sure?")
            col_yes, col_no, col_space = st.columns([1, 1, 3])
            
            with col_yes:
                if st.button("✅ Yes, Clear", type="primary", use_container_width=True):
                    try:
                        response = requests.delete(
                            f'{API_BASE_URL}/clear',
                            headers={'Authorization': st.session_state.session_token},
                            timeout=5
                        )
                        if response.status_code == 200:
                            st.session_state.messages = []
                            st.session_state.last_message_count = 0
                            st.session_state.show_clear_confirm = False
                            st.success("✅ Chat cleared successfully!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"Failed: {response.json().get('message', 'Unknown error')}")
                            st.session_state.show_clear_confirm = False
                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.session_state.show_clear_confirm = False
            
            with col_no:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.show_clear_confirm = False
                    st.rerun()

    # Delete user confirmation dialog
    if st.session_state.show_delete_confirm:
        with st.container():
            st.error("🚨 This will permanently delete your account and ALL data. This cannot be undone!")
            col_yes, col_no, col_space = st.columns([1, 1, 3])
            
            with col_yes:
                if st.button("⚠️ Yes, Delete User", type="primary", use_container_width=True):
                    try:
                        response = requests.delete(
                            f'{API_BASE_URL}/user',
                            headers={'Authorization': st.session_state.session_token},
                            timeout=5
                        )
                        if response.status_code == 200:
                            st.success("✅ User deleted successfully!")
                            time.sleep(1)
                            logout()
                            st.rerun()
                        else:
                            st.error(f"Failed: {response.json().get('message', 'Unknown error')}")
                            st.session_state.show_delete_confirm = False
                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.session_state.show_delete_confirm = False
            
            with col_no:
                if st.button("❌ Cancel Delete", use_container_width=True):
                    st.session_state.show_delete_confirm = False
                    st.rerun()

    # Tab-based content rendering
    if st.session_state.current_tab == 'chat':
        # Show indicator if property is selected
        if st.session_state.selected_property:
            st.info("📍 Property details are shown on the right panel →")
        
        # Chat Tab - Split layout if property is selected
        if st.session_state.selected_property:
            chat_col, property_col = st.columns([1.2, 1])
        else:
            chat_col = st.container()
            property_col = None
        
        with chat_col:
            # Display chat messages from database (no property cards in chat; see Properties tab)
            for idx, message in enumerate(st.session_state.messages):
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Property detail panel (only if property selected)
        if st.session_state.selected_property and property_col:
            with property_col:
                prop_data = st.session_state.selected_property
                prop = prop_data['property']
                
                # Header with close button
                col_title, col_close = st.columns([3, 1])
                with col_title:
                    st.markdown(f"## 🏠 {prop['title']}")
                with col_close:
                    if st.button("✕", use_container_width=True, type="secondary"):
                        st.session_state.selected_property = None
                        st.rerun()
                
                st.caption("👉 Property Details (scroll down for more)")
                
                # Property details
                st.markdown(f"**📍 Location:** {prop['locality']}")
                st.markdown(f"**🛏️ Configuration:** {prop['bhk']}BHK")
                st.markdown(f"**💰 Budget:** ₹{prop['budget']:,.0f}")
                st.markdown(f"**🪑 Furnishing:** {prop['furnishing_status'].replace('_', ' ').title()}")
                if prop['area_sqft']:
                    st.markdown(f"**📐 Area:** {prop['area_sqft']} sq ft")
                if prop['property_type']:
                    st.markdown(f"**🏗️ Type:** {prop['property_type'].replace('_', ' ').title()}")
                
                st.divider()
                
                # Description
                if prop.get('description'):
                    with st.expander("📝 Description", expanded=True):
                        st.markdown(prop['description'])
                
                # Amenities
                if prop.get('amenities'):
                    with st.expander("✨ Amenities", expanded=True):
                        st.markdown(prop['amenities'])
                
                # Media gallery
                if prop.get('media') and len(prop['media']) > 0:
                    st.divider()
                    st.markdown("### 📸 Media")
                    
                    for media in prop['media']:
                        if media['media_type'] == 'image':
                            st.image(media['cloudinary_url'], use_container_width=True)
                        elif media['media_type'] == 'video':
                            st.video(media['cloudinary_url'])
                        st.markdown("")  # Spacing

        # Check for responses if waiting
        if st.session_state.waiting_for_response:
            # Check if auto_send is enabled (this was refreshed right before sending)
            auto_send_enabled = st.session_state.user.get('auto_send', True)
            
            if auto_send_enabled:
                # Auto-send enabled: Show loading spinner
                with st.spinner("Generating response..."):
                    new_messages = wait_for_new_response_from_db()
                    if new_messages:
                        st.session_state.messages.extend(new_messages)
                        st.session_state.last_message_count = len(st.session_state.messages)
                        st.session_state.waiting_for_response = False
                        st.rerun()
                    else:
                        st.session_state.waiting_for_response = False
                        st.error("Response timeout. Please try again.")
                        st.rerun()
            else:
                # Manual approval required: Show static message (no spinner)
                st.info("💬 Your message has been received. Our broker will respond shortly!")
                st.session_state.waiting_for_response = False

        # Chat input (always show in chat tab)
        if prompt := st.chat_input("Ask about properties..."):
            # Add user message to UI immediately
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.last_message_count = len(st.session_state.messages)
            st.session_state.waiting_for_response = True
            
            # Refresh auto_send status before sending
            try:
                validate_response = requests.get(
                    f'{API_BASE_URL}/validate',
                    headers={'Authorization': st.session_state.session_token},
                    timeout=5
                )
                if validate_response.status_code == 200:
                    st.session_state.user = validate_response.json()['user']
            except:
                pass
            
            # Send to Flask API
            try:
                response = requests.post(
                    f'{API_BASE_URL}/send',
                    headers={'Authorization': st.session_state.session_token},
                    json={'message': prompt},
                    timeout=5
                )
                if response.status_code == 401:
                    st.error("Session expired. Please login again.")
                    logout()
                    st.rerun()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.waiting_for_response = False
    
    elif st.session_state.current_tab == 'properties':
        # Properties Tab - Show all recommended properties, sorted by recommended_at desc
        st.subheader("🏠 Recommended Properties")
        
        properties = get_recommended_properties()
        if properties:
            from datetime import datetime
            def _recommended_sort_key(r):
                ra = r.get('recommended_at') or ''
                return ra
            properties = sorted(properties, key=_recommended_sort_key, reverse=True)
        
        if not properties or len(properties) == 0:
            st.info("📭 No properties recommended yet. Keep chatting to let us understand your requirements!")
        else:
            st.caption(f"Showing {len(properties)} properties based on your requirements (newest first)")
            
            # Display properties in a grid
            for idx, rec in enumerate(properties):
                prop = rec['property']
                rec_at = rec.get('recommended_at')
                try:
                    date_display = datetime.fromisoformat(rec_at.replace('Z', '+00:00')[:10]).strftime('%d %b %Y') if rec_at else (rec_at[:10] if rec_at else '—')
                except Exception:
                    date_display = rec_at[:10] if rec_at else '—'
                
                with st.expander(f"🏠 {prop['title']}", expanded=(idx == 0)):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**📍 Location:** {prop['locality']}")
                        st.markdown(f"**🛏️ Configuration:** {prop['bhk']}BHK")
                        st.markdown(f"**💰 Budget:** ₹{prop['budget']:,.0f}")
                        st.markdown(f"**🪑 Furnishing:** {prop['furnishing_status'].replace('_', ' ').title()}")
                        if prop.get('area_sqft'):
                            st.markdown(f"**📐 Area:** {prop['area_sqft']} sq ft")
                        if prop.get('property_type'):
                            st.markdown(f"**🏗️ Type:** {prop['property_type'].replace('_', ' ').title()}")
                        st.markdown(f"**📅 Recommended:** {date_display}")
                        st.markdown(f"**✅ Status:** {prop['status'].title()}")
                    
                    with col2:
                        # Show first image if available
                        if prop.get('media') and len(prop['media']) > 0:
                            first_media = prop['media'][0]
                            if first_media['media_type'] == 'image':
                                st.image(first_media['cloudinary_url'], use_container_width=True)
                    
                    # Description
                    if prop.get('description'):
                        st.markdown("**📝 Description:**")
                        st.markdown(prop['description'])
                    
                    # Amenities
                    if prop.get('amenities'):
                        st.markdown("**✨ Amenities:**")
                        st.markdown(prop['amenities'])
                    
                    # View details button
                    if st.button(f"👁️ View Full Details", key=f"view_{prop['id']}", use_container_width=True):
                        st.session_state.selected_property = rec
                        st.session_state.current_tab = 'chat'
                        mark_property_viewed(prop['id'])
                        st.rerun()
                    
                    st.divider()
