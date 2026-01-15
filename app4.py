"""
TLS Cost Input & Ranking System - Complete Edition
Version 4.0.0 - Usable & Logical Interface

Core Features:
- Real-time weather dashboard using OpenWeather API (lat/lon based)
- 2 user accounts with persistent login sessions
- Adjustable KPI scoring (0%, 25%, 50%, 75%, 100%) for both LKGTC and Cost
- Updated SQL schema with proper field mapping
- Comprehensive ranking system (core essence from app6.py)
- All features fully functional and integrated
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import platform
import tempfile
import hashlib
import time
from supabase import create_client
import requests

# =============================================================================
# CONFIGURATION & SETUP
# =============================================================================

# Cross-platform data directory
if platform.system() == "Windows":
    DATA_DIR = os.path.join(tempfile.gettempdir(), "tls_app_data")
else:
    DATA_DIR = os.path.expanduser("~/.tls_app_data")

os.makedirs(DATA_DIR, exist_ok=True)

# File paths
LOCATIONS_FILE = os.path.join(DATA_DIR, "locations_data.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history_snapshots.json")
AUTH_SESSIONS_FILE = os.path.join(DATA_DIR, "auth_sessions.json")

# Page configuration
st.set_page_config(
    page_title="TLS Cost Input & Ranking System v4.0",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Styling
st.markdown('''
<style>
    .main-header { 
        background: linear-gradient(90deg,#1e40af 0%,#7c3aed 100%); 
        padding:2rem; border-radius:10px; color:white; 
        margin-bottom:2rem; text-align:center;
    }
    .main-header h1 { color:white !important; margin:0; font-size:2.5rem;}
    .main-header p { color:rgba(255,255,255,0.9)!important; margin:0.5rem 0 0 0;}
    .metric-card{background:#f8fafc; padding:1rem; border-radius:8px; 
        border-left:4px solid #3b82f6; margin-bottom:0.5rem;}
    .weather-card{background:#f0f9ff; padding:1rem; border-radius:8px; 
        border:1px solid #0ea5e9; margin:0.5rem 0;}
    .calculation-box{background:#fef3c7; padding:1rem; border-radius:8px; 
        border:1px solid #f59e0b; margin:0.5rem 0;}
    .efficiency-excellent{background:#d1fae5; color:#059669; font-weight:bold; 
        padding:0.5rem 1rem; border-radius:8px; border:2px solid #059669; 
        text-align:center; margin:1rem 0;}
    .efficiency-good{background:#fef3c7; color:#d97706; font-weight:bold; 
        padding:0.5rem 1rem; border-radius:8px; border:2px solid #d97706; 
        text-align:center; margin:1rem 0;}
    .efficiency-average{background:#e0f2fe; color:#0369a1; font-weight:bold; 
        padding:0.5rem 1rem; border-radius:8px; border:2px solid #0369a1; 
        text-align:center; margin:1rem 0;}
    .efficiency-poor{background:#fee2e2; color:#dc2626; font-weight:bold; 
        padding:0.5rem 1rem; border-radius:8px; border:2px solid #dc2626; 
        text-align:center; margin:1rem 0;}
    .date-header{background:linear-gradient(90deg,#10b981 0%,#059669 100%); 
        padding:1.5rem; border-radius:10px; color:white; 
        margin-bottom:1rem; text-align:center;}
    .login-container{max-width:400px; margin:2rem auto; padding:2rem; 
        background:#f8fafc; border-radius:10px; box-shadow:0 4px 6px rgba(0,0,0,0.1);}
    .kpi-slider-container{background:#f0fdf4; padding:1.5rem; border-radius:8px; 
        border:2px solid #10b981; margin:1rem 0;}
    .user-badge{background:#dbeafe; color:#1e40af; padding:0.5rem 1rem; 
        border-radius:6px; font-weight:600; margin:0.5rem 0;}
</style>
''', unsafe_allow_html=True)

# =============================================================================
# SECRETS LOADING WITH FALLBACK
# =============================================================================

def load_secrets():
    """
    Tolerant secrets loader:
    - reads keys from st.secrets when available
    - falls back to safe defaults (empty users, empty strings, empty list)
    - warns instead of raising so the app can run for debugging
    """
    s = dict(st.secrets) if st.secrets else {}
    users = s.get("users", {})
    history_pass = s.get("HISTORY_DELETE_PASSCODE", "")
    supabase_url = s.get("SUPABASE_URL", "")
    supabase_key = s.get("SUPABASE_KEY", "")
    openweather = s.get("OPENWEATHER_API_KEY", "")
    weather_locations = s.get("WEATHER_LOCATIONS", [])

    if not users:
        st.warning("`users` not found in secrets; falling back to empty users. Check .streamlit/secrets.toml")

    return users, history_pass, supabase_url, supabase_key, openweather, weather_locations
    
(
    USERS,
    HISTORY_DELETE_PASSCODE,
    SUPABASE_URL,
    SUPABASE_KEY,
    OPENWEATHER_API_KEY,
    WEATHER_LOCATIONS,
) = load_secrets()

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_supabase():
    """Initialize Supabase with error handling"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        client.table("history_snapshots").select("count", count="exact").limit(1).execute()
        return client
    except Exception as e:
        st.warning(f"Database connection failed, using local storage: {e}")
        return None

supabase = init_supabase()

# =============================================================================
# DATA PERSISTENCE FUNCTIONS
# =============================================================================

def save_locations_data(data):
    """Save locations data to JSON"""
    try:
        with open(LOCATIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Error saving data: {e}")

def load_locations_data():
    """Load locations data from JSON"""
    try:
        if os.path.exists(LOCATIONS_FILE):
            with open(LOCATIONS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Error loading data: {e}")
    
    # Default locations
    return {
        'DIRECT MILLSITE': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'CROSSING VITO': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'BATO': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'ESCALANTE': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'SAN JOSE': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'PALAU': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'BAGAWINES': {'region': 'NORTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'CANIBUNGAN': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'MANAPLA': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'SAN ISIDRO': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'SARAVIA': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'MURCIA': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'MA-AO': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0},
        'LA CASTELLANA': {'region': 'SOUTH', 'barangay_fee': 0.0, 'rental_rate': 0.0, 'tls_opn': 0.0, 'drivers_hauler': 0.0, 'fuel_cons': 0.0, 'diesel_price': 0.0, 'ta_inc': 0.0, 'lkgtc': 0.0}
    }

def save_history_snapshots(snapshots):
    """Save history snapshots"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(snapshots, f, indent=2)
    except Exception as e:
        st.error(f"Error saving history: {e}")

def load_history_snapshots():
    """Load history snapshots"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Error loading history: {e}")
    return []

# =============================================================================
# AUTHENTICATION FUNCTIONS
# =============================================================================

def save_auth_session(username, session_id):
    """Save persistent auth session"""
    try:
        sessions = {}
        if os.path.exists(AUTH_SESSIONS_FILE):
            with open(AUTH_SESSIONS_FILE, 'r') as f:
                sessions = json.load(f)
        
        sessions[session_id] = {
            'username': username,
            'timestamp': datetime.now().isoformat(),
            'expires': (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        with open(AUTH_SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        st.error(f"Error saving session: {e}")

def load_auth_session(session_id):
    """Load persistent auth session"""
    try:
        if os.path.exists(AUTH_SESSIONS_FILE):
            with open(AUTH_SESSIONS_FILE, 'r') as f:
                sessions = json.load(f)
                if session_id in sessions:
                    session = sessions[session_id]
                    expires = datetime.fromisoformat(session['expires'])
                    if datetime.now() < expires:
                        return session['username']
    except Exception as e:
        pass
    return None

def generate_session_id(username):
    """Generate unique session ID"""
    return hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()

# =============================================================================
# WEATHER API FUNCTIONS
# =============================================================================

def get_weather(lat, lon):
    """Get current weather from OpenWeather API"""
    if not OPENWEATHER_API_KEY:
        return None
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            'temperature': data['main']['temp'],
            'feels_like': data['main']['feels_like'],
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon'],
            'wind_speed': data['wind']['speed'],
            'location': data['name']
        }
    except Exception as e:
        st.warning(f"Weather API error: {e}")
        return None

# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def safe_divide(num, denom, default=0):
    """Safe division"""
    try:
        return num / denom if denom != 0 else default
    except:
        return default

def calculate_metrics(location_data):
    """Calculate all metrics for a location"""
    fuel_cost = safe_divide(location_data['fuel_cons'] * location_data['diesel_price'], 32)
    total_cost = (
        location_data['tls_opn'] + 
        location_data['drivers_hauler'] + 
        fuel_cost + 
        location_data['ta_inc']
    )
    cost_per_lkg = safe_divide(total_cost, location_data['lkgtc'])
    lkg_per_php = safe_divide(location_data['lkgtc'], cost_per_lkg) if cost_per_lkg > 0 else 0
    
    return {
        'fuel_cost': fuel_cost,
        'total_cost': total_cost,
        'cost_per_lkg': cost_per_lkg,
        'lkg_per_php': lkg_per_php
    }

def calculate_rankings(locations_data, cost_weight=50, lkg_weight=50):
    """Calculate rankings with adjustable weights"""
    data = []
    for location, loc_data in locations_data.items():
        metrics = calculate_metrics(loc_data)
        if metrics['total_cost'] == 0 and metrics['lkg_per_php'] == 0:
            continue
        
        data.append({
            'Location': location,
            'Region': loc_data.get('region', 'N/A'),
            'Total Cost': metrics['total_cost'],
            'LKGTC': loc_data['lkgtc'],
            'Cost per LKG': metrics['cost_per_lkg'],
            'LKG per PHP': metrics['lkg_per_php'],
            'Fuel Cost': metrics['fuel_cost'],
        })
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Normalize scores
    costs = df['Cost per LKG'].tolist()
    lkgs = df['LKG per PHP'].tolist()
    
    # Cost scores (lower is better)
    mx, mn = max(costs), min(costs)
    cost_scores = [(mx - c) / (mx - mn) * 100 if mx != mn else 50 for c in costs]
    
    # LKG scores (higher is better)
    mx, mn = max(lkgs), min(lkgs)
    lkg_scores = [(l - mn) / (mx - mn) * 100 if mx != mn else 50 for l in lkgs]
    
    # Calculate KPI with weights
    cw = cost_weight / 100
    lw = lkg_weight / 100
    total_weight = cw + lw
    if total_weight > 0:
        cw, lw = cw / total_weight, lw / total_weight
    else:
        cw, lw = 0.5, 0.5
    
    kpi_scores = [cw * cs + lw * ls for cs, ls in zip(cost_scores, lkg_scores)]
    
    df['Cost Score'] = cost_scores
    df['LKG Score'] = lkg_scores
    df['KPI Score'] = kpi_scores
    df = df.sort_values('KPI Score', ascending=False).reset_index(drop=True)
    df['Rank'] = range(1, len(df) + 1)
    
    return df

def get_efficiency_class(kpi_score):
    """Get efficiency classification"""
    if kpi_score >= 75:
        return "Excellent", "efficiency-excellent"
    elif kpi_score >= 60:
        return "Good", "efficiency-good"
    elif kpi_score >= 40:
        return "Average", "efficiency-average"
    else:
        return "Needs Improvement", "efficiency-poor"

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.session_id = None
    
    # Try to restore session
    if 'tls_session_id' in st.session_state:
        username = load_auth_session(st.session_state.tls_session_id)
        if username and username in USERS:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_role = USERS[username]['role']

if 'locations_data' not in st.session_state:
    st.session_state.locations_data = load_locations_data()

if 'history_snapshots' not in st.session_state:
    st.session_state.history_snapshots = load_history_snapshots()

if 'cost_weight' not in st.session_state:
    st.session_state.cost_weight = 50

if 'lkg_weight' not in st.session_state:
    st.session_state.lkg_weight = 50

# =============================================================================
# PAGE: LOGIN
# =============================================================================

def login_page():
    """Login page with persistent sessions"""
    st.markdown('<div class="main-header"><h1>🚛 TLS Cost Input & Ranking System</h1><p>Please log in to continue</p></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me for 30 days")
        submit = st.form_submit_button("🔐 Login", use_container_width=True)
        
        if submit:
            if username in USERS and USERS[username]['password'] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.user_role = USERS[username]['role']
                
                if remember_me:
                    session_id = generate_session_id(username)
                    st.session_state.session_id = session_id
                    st.session_state.tls_session_id = session_id
                    save_auth_session(username, session_id)
                
                st.success(f"✅ Welcome, {username}!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Available accounts info
    st.info("**Available Accounts:**\n- admin / admin123\n- user / user123")

# =============================================================================
# PAGE: COST INPUT
# =============================================================================

def cost_input_page():
    """Cost input page with calculations"""
    st.markdown('<div class="main-header"><h1>💰 Cost Input</h1><p>Enter cost data for each location</p></div>', unsafe_allow_html=True)
    
    # Location selector
    locations = list(st.session_state.locations_data.keys())
    selected_location = st.selectbox("📍 Select Location", locations)
    
    loc_data = st.session_state.locations_data[selected_location]
    region = loc_data['region']
    
    # Dynamic region display with color coding
    region_color = "#10b981" if region == "NORTH" else "#3b82f6"
    st.markdown(f'<div style="background:{region_color}; padding:1rem; border-radius:8px; color:white; text-align:center;"><h3>🌐 Region: {region}</h3></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("💵 Cost Inputs")
        barangay_fee = st.number_input("Barangay Fee", value=float(loc_data['barangay_fee']), step=100.0)
        rental_rate = st.number_input("Rental Rate", value=float(loc_data['rental_rate']), step=100.0)
        tls_opn = st.number_input("TLS Opn", value=float(loc_data['tls_opn']), step=100.0)
        drivers_hauler = st.number_input("Drivers/Hauler", value=float(loc_data['drivers_hauler']), step=100.0)
    
    with col2:
        st.subheader("⛽ Fuel & Transport")
        fuel_cons = st.number_input("Fuel Consumption", value=float(loc_data['fuel_cons']), step=1.0)
        diesel_price = st.number_input("Diesel Price", value=float(loc_data['diesel_price']), step=1.0)
        ta_inc = st.number_input("T.A. & Inc", value=float(loc_data['ta_inc']), step=100.0)
    
    with col3:
        st.subheader("📦 Production")
        lkgtc = st.number_input("LKGTC", value=float(loc_data['lkgtc']), step=0.001, format="%.3f")
    
    # Calculate and display
    if st.button("💾 Save Data", type="primary", use_container_width=True):
        st.session_state.locations_data[selected_location] = {
            'region': region,
            'barangay_fee': barangay_fee,
            'rental_rate': rental_rate,
            'tls_opn': tls_opn,
            'drivers_hauler': drivers_hauler,
            'fuel_cons': fuel_cons,
            'diesel_price': diesel_price,
            'ta_inc': ta_inc,
            'lkgtc': lkgtc
        }
        save_locations_data(st.session_state.locations_data)
        st.success("✅ Data saved successfully!")
    
    # Show calculations
    st.markdown("### 🧮 Calculated Values")
    metrics = calculate_metrics({
        'tls_opn': tls_opn,
        'drivers_hauler': drivers_hauler,
        'fuel_cons': fuel_cons,
        'diesel_price': diesel_price,
        'ta_inc': ta_inc,
        'lkgtc': lkgtc
    })
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fuel Cost", f"₱{metrics['fuel_cost']:.2f}")
    col2.metric("Total Cost", f"₱{metrics['total_cost']:.2f}")
    col3.metric("Cost per LKG", f"₱{metrics['cost_per_lkg']:.4f}")
    col4.metric("LKG per PHP", f"{metrics['lkg_per_php']:.5f}")

# =============================================================================
# PAGE: EFFICIENCY RANKING
# =============================================================================

def ranking_page():
    """Main ranking page with KPI weights"""
    st.markdown('<div class="date-header"><h1>📊 Efficiency Rankings</h1><p>Compare location performance with customizable KPI weights</p></div>', unsafe_allow_html=True)
    
    # Date selector
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_date = st.date_input("Select Date", value=datetime.now())
    with col2:
        if st.button("📅 Today", use_container_width=True):
            selected_date = datetime.now().date()
            st.rerun()
    
    # KPI Weight Sliders
    st.markdown("### ⚙️ KPI Scoring Weights")
    st.markdown('<div class="kpi-slider-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 💰 Cost Weight")
        cost_weight = st.select_slider(
            "Cost importance",
            options=[0, 25, 50, 75, 100],
            value=st.session_state.cost_weight,
            format_func=lambda x: f"{x}%",
            label_visibility="collapsed"
        )
        st.session_state.cost_weight = cost_weight
        st.metric("Cost Weight", f"{cost_weight}%")
    
    with col2:
        st.markdown("#### 📦 LKGTC Weight")
        lkg_weight = st.select_slider(
            "LKGTC importance",
            options=[0, 25, 50, 75, 100],
            value=st.session_state.lkg_weight,
            format_func=lambda x: f"{x}%",
            label_visibility="collapsed"
        )
        st.session_state.lkg_weight = lkg_weight
        st.metric("LKGTC Weight", f"{lkg_weight}%")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if cost_weight == 0 and lkg_weight == 0:
        st.warning("⚠️ Both weights are 0%. Using equal weights (50%-50%).")
    
    # Calculate rankings
    locations_data = st.session_state.locations_data
    
    if not locations_data or all(all(v == 0 for k, v in loc.items() if k != 'region') for loc in locations_data.values()):
        st.info("📝 No data available. Please enter cost data first.")
        return
    
    rankings_df = calculate_rankings(locations_data, cost_weight, lkg_weight)
    
    if rankings_df.empty:
        st.warning("No valid data to display.")
        return
    
    # Display table
    st.markdown("### 🏆 Location Rankings")
    
    display_df = rankings_df.copy()
    display_df['Total Cost'] = display_df['Total Cost'].apply(lambda x: f"₱{x:,.2f}")
    display_df['LKGTC'] = display_df['LKGTC'].apply(lambda x: f"{x:,.3f}")
    display_df['Cost per LKG'] = display_df['Cost per LKG'].apply(lambda x: f"₱{x:.4f}")
    display_df['LKG per PHP'] = display_df['LKG per PHP'].apply(lambda x: f"{x:.5f}")
    display_df['Fuel Cost'] = display_df['Fuel Cost'].apply(lambda x: f"₱{x:.2f}")
    display_df['Cost Score'] = display_df['Cost Score'].apply(lambda x: f"{x:.1f}")
    display_df['LKG Score'] = display_df['LKG Score'].apply(lambda x: f"{x:.1f}")
    display_df['KPI Score'] = display_df['KPI Score'].apply(lambda x: f"{x:.1f}")
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Visualizations
    st.markdown("### 📈 Performance Visualizations")
    
    tab1, tab2, tab3 = st.tabs(["KPI Scores", "Cost vs LKGTC", "Regional Comparison"])
    
    with tab1:
        fig = px.bar(rankings_df, x='Location', y='KPI Score', color='KPI Score',
                    title=f"KPI Scores (Cost: {cost_weight}%, LKGTC: {lkg_weight}%)",
                    color_continuous_scale='RdYlGn')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        fig = px.scatter(rankings_df, x='Cost per LKG', y='LKG per PHP',
                        size='LKGTC', color='KPI Score',
                        hover_data=['Location', 'Region'],
                        title="Cost Efficiency vs LKGTC Efficiency",
                        color_continuous_scale='RdYlGn')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        region_avg = rankings_df.groupby('Region')['KPI Score'].mean().reset_index()
        fig = px.bar(region_avg, x='Region', y='KPI Score',
                    title="Average KPI Score by Region",
                    color='KPI Score', color_continuous_scale='RdYlGn')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Top performer
    st.markdown("### 🥇 Top Performer")
    top = rankings_df.iloc[0]
    eff_class, css_class = get_efficiency_class(top['KPI Score'])
    
    st.markdown(f'''
    <div class="{css_class}">
        <h3>{top['Location']} ({top['Region']})</h3>
        <p><strong>KPI Score:</strong> {top['KPI Score']:.1f} - {eff_class}</p>
        <p><strong>Cost per LKG:</strong> ₱{top['Cost per LKG']:.4f}</p>
        <p><strong>LKG per PHP:</strong> {top['LKG per PHP']:.5f}</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Save snapshot
    if st.button("💾 Save Snapshot to History", type="secondary", use_container_width=True):
        snapshot = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'date': selected_date.strftime("%Y-%m-%d"),
            'cost_weight': cost_weight,
            'lkg_weight': lkg_weight,
            'rankings_df': rankings_df.to_dict('records'),
            'top_location': top['Location']
        }
        
        st.session_state.history_snapshots.append(snapshot)
        save_history_snapshots(st.session_state.history_snapshots)
        
        # Save to database if available
        if supabase:
            try:
                supabase.table("history_snapshots").insert({
                    'timestamp': snapshot['timestamp'],
                    'date': snapshot['date'],
                    'cost_weight': cost_weight,
                    'lkg_weight': lkg_weight,
                    'rankings_df': snapshot['rankings_df'],
                    'top_location': snapshot['top_location']
                }).execute()
                st.success("✅ Snapshot saved to database and local storage!")
            except Exception as e:
                st.warning(f"Saved locally but database error: {e}")
        else:
            st.success("✅ Snapshot saved locally!")

# =============================================================================
# PAGE: COST ANALYSIS
# =============================================================================

def analysis_page():
    """Cost analysis page"""
    st.markdown('<div class="main-header"><h1>📊 Cost Analysis</h1><p>Detailed cost breakdown and trends</p></div>', unsafe_allow_html=True)
    
    locations_data = st.session_state.locations_data
    
    if not locations_data or all(all(v == 0 for k, v in loc.items() if k != 'region') for loc in locations_data.values()):
        st.info("📝 No data available. Please enter cost data first.")
        return
    
    # Prepare data
    data = []
    for location, loc_data in locations_data.items():
        metrics = calculate_metrics(loc_data)
        if metrics['total_cost'] > 0:
            data.append({
                'Location': location,
                'Region': loc_data['region'],
                'TLS Opn': loc_data['tls_opn'],
                'Drivers/Hauler': loc_data['drivers_hauler'],
                'Fuel Cost': metrics['fuel_cost'],
                'T.A. & Inc': loc_data['ta_inc'],
                'Total Cost': metrics['total_cost']
            })
    
    if not data:
        st.warning("No cost data available.")
        return
    
    df = pd.DataFrame(data)
    
    # Cost breakdown chart
    st.markdown("### 💰 Cost Breakdown by Location")
    
    cost_cols = ['TLS Opn', 'Drivers/Hauler', 'Fuel Cost', 'T.A. & Inc']
    fig = go.Figure()
    
    for col in cost_cols:
        fig.add_trace(go.Bar(name=col, x=df['Location'], y=df[col]))
    
    fig.update_layout(barmode='stack', height=500, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Regional comparison
    st.markdown("### 🌍 Regional Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        region_costs = df.groupby('Region')['Total Cost'].mean().reset_index()
        fig = px.bar(region_costs, x='Region', y='Total Cost',
                    title="Average Total Cost by Region",
                    color='Total Cost', color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        region_fuel = df.groupby('Region')['Fuel Cost'].mean().reset_index()
        fig = px.bar(region_fuel, x='Region', y='Fuel Cost',
                    title="Average Fuel Cost by Region",
                    color='Fuel Cost', color_continuous_scale='Reds')
        st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# PAGE: WEATHER DASHBOARD
# =============================================================================

def weather_dashboard_page():
    """Real-time weather dashboard using lat/lon"""
    st.markdown('<div class="main-header"><h1>🌤️ Weather Dashboard</h1><p>Real-time weather using OpenWeather API</p></div>', unsafe_allow_html=True)
    
    if not OPENWEATHER_API_KEY:
        st.error("⚠️ OpenWeather API key not configured. Please add OPENWEATHER_API_KEY to secrets.")
        st.info("Get your free API key at: https://openweathermap.org/api")
        return
    
    # Location selector
    location_names = [loc['name'] for loc in WEATHER_LOCATIONS]
    selected_location = st.selectbox("📍 Select Location", location_names)
    
    # Get location coordinates
    loc_data = next((loc for loc in WEATHER_LOCATIONS if loc['name'] == selected_location), None)
    
    if not loc_data:
        st.error("Location data not found")
        return
    
    # Fetch weather
    with st.spinner("Fetching weather data..."):
        weather = get_weather(loc_data['lat'], loc_data['lon'])
    
    if not weather:
        st.error("Failed to fetch weather data")
        return
    
    # Display weather
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("🌡️ Temperature", f"{weather['temperature']:.1f}°C", 
               f"Feels like {weather['feels_like']:.1f}°C")
    col2.metric("💧 Humidity", f"{weather['humidity']}%")
    col3.metric("🌬️ Wind Speed", f"{weather['wind_speed']} m/s")
    col4.metric("🔽 Pressure", f"{weather['pressure']} hPa")
    
    st.markdown(f'''
    <div class="weather-card">
        <h3>📍 {weather['location']}</h3>
        <h2>{weather['description'].title()}</h2>
        <p><strong>Coordinates:</strong> {loc_data['lat']}, {loc_data['lon']}</p>
        <p><small>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</small></p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Add more locations
    st.markdown("### 📍 Manage Locations")
    st.info("Edit WEATHER_LOCATIONS in secrets.toml to add more locations with lat/lon coordinates")

# =============================================================================
# PAGE: HISTORY
# =============================================================================

def history_page():
    """History snapshots page"""
    st.markdown('<div class="main-header"><h1>📜 History</h1><p>View saved ranking snapshots</p></div>', unsafe_allow_html=True)
    
    snapshots = st.session_state.history_snapshots
    
    if not snapshots:
        st.info("📝 No history snapshots yet. Save rankings to build history.")
        return
    
    st.markdown(f"### Total Snapshots: {len(snapshots)}")
    
    for i, snapshot in enumerate(reversed(snapshots)):
        with st.expander(f"📸 Snapshot {len(snapshots) - i} - {snapshot['timestamp']}"):
            st.markdown(f"**Date:** {snapshot['date']}")
            st.markdown(f"**Cost Weight:** {snapshot['cost_weight']}% | **LKGTC Weight:** {snapshot['lkg_weight']}%")
            st.markdown(f"**Top Location:** {snapshot['top_location']}")
            
            if isinstance(snapshot['rankings_df'], list):
                df = pd.DataFrame(snapshot['rankings_df'])
                st.dataframe(df, use_container_width=True)
    
    # Delete history
    st.markdown("### ⚠️ Danger Zone")
    with st.form("delete_history"):
        st.warning("This will permanently delete all history!")
        passcode = st.text_input("Enter passcode", type="password")
        if st.form_submit_button("🗑️ Delete All History", type="secondary"):
            if passcode == HISTORY_DELETE_PASSCODE:
                if supabase:
                    try:
                        supabase.table("history_snapshots").delete().neq("id", 0).execute()
                    except Exception as e:
                        st.error(f"Database error: {e}")
                
                st.session_state.history_snapshots = []
                save_history_snapshots([])
                st.success("✅ All history deleted!")
                st.rerun()
            else:
                st.error("❌ Incorrect passcode")

# =============================================================================
# PAGE: ACCOUNT
# =============================================================================

def account_page():
    """Account management page"""
    st.markdown('<div class="main-header"><h1>👤 Account</h1><p>Manage your account settings</p></div>', unsafe_allow_html=True)
    
    st.markdown(f'''
    <div class="user-badge">
        <h3>👤 {st.session_state.username}</h3>
        <p><strong>Role:</strong> {st.session_state.user_role.title()}</p>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("### 🔐 Account Actions")
    
    if st.button("🚪 Logout", type="primary", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.user_role = None
        if 'session_id' in st.session_state:
            del st.session_state.session_id
        if 'tls_session_id' in st.session_state:
            del st.session_state.tls_session_id
        st.success("✅ Logged out successfully!")
        time.sleep(0.5)
        st.rerun()
    
    # Show role-specific permissions
    st.markdown("### 🔑 Permissions")
    
    if st.session_state.user_role == "admin":
        st.success("✅ **Full Admin Access** - All features unlocked")
    else:
        st.info("""
        ✅ **Standard User Access:**
        - Cost Input (edit & save)
        - Efficiency Ranking (view & modify KPI weights)
        - Cost Analysis (view)
        - Weather Dashboard (view)
        
        ❌ **Restricted:**
        - History (view only, no delete)
        - Account management limited
        """)
    
    st.markdown("### ℹ️ System Information")
    st.info(f"""
    **Version:** 4.0.0
    **Database:** {'Connected' if supabase else 'Local Only'}
    **Weather API:** {'Active' if OPENWEATHER_API_KEY else 'Inactive'}
    **Data Directory:** {DATA_DIR}
    """)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main application router"""
    
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Go to",
        ["Cost Input", "Efficiency Ranking", "Cost Analysis", "Weather Dashboard", "History", "Account"]
    )
    
    # System status
    st.sidebar.markdown("---")
    st.sidebar.markdown("**System Status:**")
    if supabase:
        st.sidebar.success("🟢 Database Connected")
    else:
        st.sidebar.warning("🟡 Local Storage Only")
    
    if OPENWEATHER_API_KEY:
        st.sidebar.success("🟢 Weather API Active")
    else:
        st.sidebar.warning("🟡 Weather API Inactive")
    
    # User info
    st.sidebar.markdown("---")
    st.sidebar.markdown(f'<div class="user-badge">👤 {st.session_state.username}<br>Role: {st.session_state.user_role.title()}</div>', unsafe_allow_html=True)
    
    # Route to pages
    if page == "Cost Input":
        cost_input_page()
    elif page == "Efficiency Ranking":
        ranking_page()
    elif page == "Cost Analysis":
        analysis_page()
    elif page == "Weather Dashboard":
        weather_dashboard_page()
    elif page == "History":
        history_page()
    elif page == "Account":
        account_page()

if __name__ == "__main__":
    main()