import os
import requests
import time
from datetime import datetime, timedelta, timezone
from ics import Calendar
import streamlit as st
import re

# Configure page
st.set_page_config(page_title="Team Schedule & Live Ticker", page_icon="🏒", layout="wide")

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

def fetch_game_events(game_id):
    """Fetch live events for a specific game"""
    url = f"https://api-v2.swissunihockey.ch/api/game/{game_id}/events/"
    try:
        response = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {response.text[:200]}...")
            return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

def display_live_events(game_id):
    """Display and continuously update live game events"""
    if not game_id:
        return
    
    placeholder = st.empty()
    last_events_count = 0
    
    while True:
        events_data = fetch_game_events(game_id)
        
        with placeholder.container():
            if events_data and "events" in events_data:
                current_events = events_data["events"]
                
                # Display all events
                st.subheader("🔴 Live Spielereignisse")
                for event in current_events:
                    event_type = event.get("type")
                    event_time = event.get("time", "")
                    team = event.get("team", {}).get("name", "Unbekannt")
                    player = event.get("player", {}).get("name", "Unbekannt")
                    
                    if event_type == "GOAL":
                        st.success(f"⚽ {team}: Tor durch {player} ({event_time}')")
                    elif event_type == "PENALTY":
                        penalty_time = event.get("penaltyTime", "2")
                        st.warning(f"⚠️ {team}: Strafe gegen {player} ({penalty_time} Min)")
                    elif event_type == "PERIOD_START":
                        period = event.get("period", "1")
                        st.info(f"🔄 {period}. Drittel gestartet")
                    elif event_type == "PERIOD_END":
                        period = event.get("period", "1")
                        st.info(f"⏹️ {period}. Drittel beendet")
                
                last_events_count = len(current_events)
            else:
                st.warning("Warte auf Live-Daten...")
        
        time.sleep(10)  # Update every 10 seconds

def extract_game_id(url):
    """Extract game ID from Swiss Unihockey URL"""
    if not url:
        return None
    
    # Try to extract from /game/ format
    match = re.search(r'/game/(\d+)', url)
    if match:
        return match.group(1)
    
    # Try to extract from /gamecenter/ format
    match = re.search(r'/gamecenter/(\d+)', url)
    if match:
        return match.group(1)
    
    return None

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
        
        # Game is considered live if it started in the last 3 hours
        if game_id and game_time <= now <= game_time + timedelta(hours=3):
            display_live_events(game_id)
    
    st.markdown("---")

def fetch_future_games(team_name, team_id):
    """Fetch and display future games for a team"""
    with st.spinner(f"Lade Spiele für {team_name}..."):
        try:
            response = requests.get(
                f"https://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()
            
            calendar = Calendar(response.text)
            now = datetime.now(timezone.utc)
            
            future_events = sorted(
                [e for e in calendar.events if e.begin > now],
                key=lambda e: e.begin
            )
            
            if not future_events:
                st.info(f"Keine kommenden Spiele für {team_name}")
                return
            
            st.subheader("⏭️ Nächstes Spiel")
            display_game_event(future_events[0], team_name)
            
            if len(future_events) > 1:
                st.subheader("📅 Weitere Spiele")
                for event in future_events[1:3]:
                    display_game_event(event, team_name)
                    
        except Exception as e:
            st.error(f"Fehler beim Laden der Spiele: {str(e)}")

def fetch_past_games(team_name, team_id):
    """Fetch and display past games for a team"""
    with st.spinner(f"Lade vergangene Spiele für {team_name}..."):
        try:
            response = requests.get(
                "https://api-v2.swissunihockey.ch/api/v3/games",
                params={
                    'team': team_id,
                    'result': 'true',
                    'limit': 5,
                    'sort': '-date'
                },
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            
            games = response.json().get('data', [])
            
            if not games:
                st.info(f"Keine vergangenen Spiele für {team_name}")
                return
            
            st.subheader("⏮️ Letzte Spiele")
            for game in games:
                cols = st.columns([1, 3])
                with cols[0]:
                    st.write(f"**{game.get('date', 'N/A')}**")
                    st.write(game.get('time', 'N/A'))
                with cols[1]:
                    home = game.get('home_team', {}).get('name', 'N/A')
                    away = game.get('away_team', {}).get('name', 'N/A')
                    st.write(f"**{home} vs {away}**")
                    
                    if game.get('status') == 'finished':
                        st.write(f"🏒 {game.get('home_goals', 'N/A')} - {game.get('away_goals', 'N/A')}")
                    else:
                        st.write(f"Status: {game.get('status', 'N/A')}")
                    
                    st.write(f"📍 {game.get('venue', {}).get('name', 'N/A')}")
                
                st.divider()
                
        except Exception as e:
            st.error(f"Fehler beim Laden der Spiele: {str(e)}")

# Main app
st.title("🏒 Swiss Unihockey Dashboard")

for team_name, team_id in TEAMS.items():
    st.header(team_name)
    fetch_past_games(team_name, team_id)
    fetch_future_games(team_name, team_id)
    st.write("")
