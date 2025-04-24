import os
import requests
from datetime import datetime, timezone
from ics import Calendar
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule", page_icon="🏒", layout="wide")

# List of teams: name + team_id
teams = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    logo_path = f"logos/{team_name.lower()}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def display_game_event(event, team_name):
    """Display a single game event in Streamlit"""
    # Game info
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.format("DD.MM.YYYY")
    time = event.begin.format("HH:mm")
    location = event.location or "nicht angegeben"
    url = event.url or "#"

    # Split team names
    teams_in_game = name.split(" - ")
    home = teams_in_game[0].strip()
    away = teams_in_game[1].strip() if len(teams_in_game) > 1 else "Unbekannt"
  
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 5, 1])
    with col1:
        st.image(get_team_logo(home), width=200)
    with col2:
        st.subheader(f'<div style="text-align:center>name</div>',unsafe_allow_html=True,)
        st.caption(f"📅 {date} | 🕒 {time} | 📍 {location}")
        st.markdown(f"[🔗 Zur Spielseite]({url})")
    with col3:
        st.image(get_team_logo(away), width=200)
    st.markdown("---")

def fetch_team_schedule(team_name, team_id):
    """Fetch and display schedule for a single team"""
    with st.spinner(f"Lade Spiele für {team_name}..."):
        try:
            API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
            response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            calendar = Calendar(response.text)
            now = datetime.now(timezone.utc)
            
            # Get future events sorted by date
            future_events = sorted(
                [e for e in calendar.events if e.begin > now],
                key=lambda e: e.begin
            )[:3]  # Limit to 3 next games
            
            if not future_events:
                st.info(f"Keine zukünftigen Spiele für {team_name} gefunden.")
                return
            
            for event in future_events:
                display_game_event(event, team_name)
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der Daten für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

# Main app
st.title("🏒 Spielplan")

# Display schedule for each team
for team_name, team_id in teams.items():
    st.header(f"🔷 {team_name}")
    fetch_team_schedule(team_name, team_id)
    st.write("")  # Add some space between teams
