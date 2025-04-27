import os
import requests
import time
from datetime import datetime, timedelta, timezone
from ics import Calendar
import streamlit as st
import re

# Configure page
st.set_page_config(page_title="Team Schedule & Live Ticker", page_icon="🏒", layout="wide")

# Debug Mode
DEBUG = st.sidebar.checkbox("Debug-Modus aktivieren", value=True)

# List of teams: name + team_id
TEAMS = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
    "Jets Scheisse": 431166,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    normalized_name = team_name.lower()
    logo_path = f"logos/{normalized_name}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def extract_game_id(url):
    """Extrahiert die Game-ID aus der Swiss Unihockey URL"""
    if not url:
        return None
    
    # Teste verschiedene URL-Formate
    patterns = [
        r'game_id=(\d+)',         # https://www.swissunihockey.ch/de/game-detail?game_id=1073794
        r'/game/(\d+)',           # /game/1073794/
        r'/gamecenter/(\d+)'      # /gamecenter/1073794/
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            if DEBUG:
                st.sidebar.success(f"Game ID {match.group(1)} aus URL extrahiert (Pattern: {pattern})")
            return match.group(1)
    
    if DEBUG:
        st.sidebar.error(f"Keine Game ID in URL gefunden: {url}")
    return None

def fetch_game_events(game_id):
    """Fetch live events for a specific game"""
    if DEBUG:
        st.sidebar.write(f"📡 API-Aufruf für Game ID: {game_id}")
    
    try:
        url = f"https://api.swissunihockey.ch/api/game/{game_id}/events/"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.swissunihockey.ch/"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if DEBUG:
            st.sidebar.write(f"API Status: {response.status_code}")
            if response.status_code == 200:
                st.sidebar.json(response.json())
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {response.text[:200]}...")
            return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

def display_single_event(event):
    """Zeigt ein einzelnes Spielereignis an"""
    event_type = event.get("type")
    event_time = event.get("time", "")
    team = event.get("team", {}).get("name", "Unbekannt")
    player = event.get("player", {}).get("name", "")
    
    if event_type == "GOAL":
        st.success(f"⚽ {event_time}' - {team}: Tor durch {player}")
    elif event_type == "PENALTY":
        penalty_time = event.get("penaltyTime", "2")
        st.warning(f"⚠️ {event_time}' - {team}: Strafe gegen {player} ({penalty_time} Min)")
    elif event_type == "PERIOD_START":
        st.info(f"🔄 {event_time}' - {event.get('period', '1')}. Drittel beginnt")
    elif event_type == "PERIOD_END":
        st.info(f"⏹️ {event_time}' - {event.get('period', '1')}. Drittel endet")
    else:
        st.write(f"{event_time}' - {event_type}: {team} - {player}")

def display_live_ticker(game_id):
    """Display and continuously update live game events"""
    if not game_id:
        if DEBUG:
            st.sidebar.warning("Keine Game ID für Live-Ticker")
        return
    
    placeholder = st.empty()
    last_event_count = 0
    
    if DEBUG:
        debug_expander = st.expander("Live-Ticker Debug Info")
    
    while True:
        start_time = time.time()
        data = fetch_game_events(game_id)
        
        with placeholder.container():
            if not data:
                st.warning("Warte auf Live-Daten...")
                time.sleep(10)
                continue
            
            events = data.get("events", [])
            game_info = data.get("game", {})
            
            # Spielstand anzeigen
            home_team = game_info.get("home_team", {}).get("name", "Heim")
            away_team = game_info.get("away_team", {}).get("name", "Gast")
            home_score = game_info.get("home_goals", 0)
            away_score = game_info.get("away_goals", 0)
            period = game_info.get("period", 1)
            
            st.markdown(f"""
                <div style="background-color:#f0f2f6;padding:10px;border-radius:10px;margin-bottom:15px">
                    <h3 style="text-align:center">
                        {home_team} {home_score} - {away_score} {away_team}
                    </h3>
                    <p style="text-align:center">{period}. Drittel</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Neue Events anzeigen
            if len(events) > last_event_count:
                new_events = events[last_event_count:]
                for event in new_events:
                    display_single_event(event)
                last_event_count = len(events)
            
            if DEBUG:
                with debug_expander:
                    st.write(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
                    st.write(f"Verarbeitete Events: {last_event_count}")
                    st.write(f"API-Antwortzeit: {round(time.time() - start_time, 2)}s")
        
        time.sleep(10)

def display_game_event(event, team_name):
    """Display a game event with live ticker if active"""
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.strftime("%d.%m.%Y") if hasattr(event.begin, 'strftime') else "N/A"
    time_str = event.begin.strftime("%H:%M") if hasattr(event.begin, 'strftime') else "N/A"
    location = event.location or "nicht angegeben"
    url = event.url or "#"
    
    teams = name.split(" - ")
    home = teams[0].strip()
    away = teams[1].strip() if len(teams) > 1 else "Unbekannt"
    
    game_id = extract_game_id(url)
    
    if DEBUG:
        st.sidebar.write(f"🔍 Analyse für: {name}")
        st.sidebar.write(f"URL: {url}")
        st.sidebar.write(f"Extrahiert Game ID: {game_id}")
    
    st.markdown("---")
    cols = st.columns([1, 5, 1])
    with cols[0]:
        st.image(get_team_logo(home), width=120)
    with cols[1]:
        st.markdown(f"""
            <div style='text-align: center'>
                <h4>{name}</h4>
                <p>📅 {date} | 🕒 {time_str} | 📍 {location}</p>
                <a href="{url}" target="_blank">🔗 Spielbericht</a>
            </div>
        """, unsafe_allow_html=True)
    with cols[2]:
        st.image(get_team_logo(away), width=120)
    
    # Check if game is live
    if hasattr(event.begin, 'replace'):
        game_time = event.begin.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        
        if DEBUG:
            st.sidebar.write(f"Spielzeit: {game_time}")
            st.sidebar.write(f"Aktuelle Zeit: {now}")
            st.sidebar.write(f"Live-Fenster: {game_time} bis {game_time + timedelta(hours=3)}")
        
        # Erweitertes Live-Fenster (30 Minuten vor/nach Spiel)
        if game_id and (game_time - timedelta(minutes=30)) <= now <= (game_time + timedelta(hours=3)):
            display_live_ticker(game_id)
    
    st.markdown("---")

# Rest der Funktionen (fetch_future_games, fetch_past_games) bleiben unverändert...

# Main app
st.title("🏒 Swiss Unihockey Dashboard")

if DEBUG:
    st.sidebar.header("Debug Tools")
    test_url = st.sidebar.text_input("Test-URL", "https://www.swissunihockey.ch/de/game-detail?game_id=1073794")
    if st.sidebar.button("Test Game ID Extraction"):
        test_id = extract_game_id(test_url)
        st.sidebar.write(f"Extrahiert: {test_id}")

for team_name, team_id in TEAMS.items():
    st.header(team_name)
    fetch_past_games(team_name, team_id)
    fetch_future_games(team_name, team_id)
    st.write("")
