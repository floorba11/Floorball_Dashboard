import os
import requests
from datetime import datetime, timezone
from ics import Calendar
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule & Results", page_icon="🏒", layout="wide")

# List of teams: name + team_id
TEAMS = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
    "Regio Entlebuch": 432526,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    normalized_name = team_name.lower()
    logo_path = f"logos/{normalized_name}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def display_game_event(event, team_name):
    """Display a game event"""
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.strftime("%d.%m.%Y") if hasattr(event.begin, 'strftime') else "N/A"
    time_str = event.begin.strftime("%H:%M") if hasattr(event.begin, 'strftime') else "N/A"
    location = event.location or "nicht angegeben"
    url = event.url or "#"
    
    teams = name.split(" - ")
    home = teams[0].strip()
    away = teams[1].strip() if len(teams) > 1 else "Unbekannt"
    
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
    st.markdown("---")

def fetch_future_games(team_name, team_id):
    """Fetch and display future games for a team using the calendar API"""
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
    """Fetch and display past games for a team using the games API"""
    with st.spinner(f"Lade vergangene Spiele für {team_name}..."):
        try:
            # Using the basic games endpoint instead of v3
            response = requests.get(
                f"https://api-v2.swissunihockey.ch/api/games",
                params={
                    'team': team_id,
                    'result': 'true',
                    'limit': 5
                },
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            
            games = response.json().get('games', [])
            
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
