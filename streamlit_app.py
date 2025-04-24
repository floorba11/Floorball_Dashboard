import os
import requests
from datetime import datetime, timezone
from ics import Calendar
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule", page_icon="🏒", layout="wide")

# List of teams: name + team_id
teams = {
    "Tigers LUPL": 429523,
    "Herren Frutigen": 429611,
}

def get_team_logo_from_api(team_name, game_id):
    """Get team logo from API"""
    try:
        API_URL = f"https://api-v2.swissunihockey.ch/api/games/{game_id}"
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        
        data = response.json()
        
        # Determine if the team is home or away
        if team_name == data.get('home_name'):
            return data.get('home_logo')
        elif team_name == data.get('away_name'):
            return data.get('away_logo')
        
    except Exception as e:
        st.error(f"Fehler beim Abrufen des Logos für {team_name}: {str(e)}")
    
    return "logos/default.png"

def display_game_event(event, team_name, is_last_game=False):
    """Display a single game event in Streamlit"""
    # Game info
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.format("DD.MM.YYYY")
    time = event.begin.format("HH:mm")
    location = event.location or "nicht angegeben"
    url = event.url or "#"
    game_id = url.split('/')[-1] if url else None

    # Split team names
    teams_in_game = name.split(" - ")
    home = teams_in_game[0].strip()
    away = teams_in_game[1].strip() if len(teams_in_game) > 1 else "Unbekannt"

    # Display game info
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        home_logo = get_team_logo_from_api(home, game_id) if game_id and is_last_game else f"logos/{home.lower().replace(' ', '_')}.png"
        st.image(home_logo if os.path.exists(home_logo.replace("logos/", "")) else "logos/default.png", width=60)
    with col2:
        st.subheader(name)
        
        if is_last_game and game_id:
            try:
                # Fetch game details
                API_URL = f"https://api-v2.swissunihockey.ch/api/games/{game_id}"
                response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                
                game_data = response.json()
                result = game_data.get('result', 'Kein Ergebnis verfügbar')
                spectators = game_data.get('spectators', 'Keine Zuschauerinformation')
                
                st.markdown(f"**Ergebnis:** {result} | **Zuschauer:** {spectators}")
            except Exception as e:
                st.error(f"Fehler beim Abrufen der Spielstatistiken: {str(e)}")
        
        st.caption(f"📅 {date} | 🕒 {time} | 📍 {location}")
        st.markdown(f"[🔗 Zur Spielseite]({url})")
    with col3:
        away_logo = get_team_logo_from_api(away, game_id) if game_id and is_last_game else f"logos/{away.lower().replace(' ', '_')}.png"
        st.image(away_logo if os.path.exists(away_logo.replace("logos/", "")) else "logos/default.png", width=60)
    
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
            
            # Get all events sorted by date
            all_events = sorted(
                [e for e in calendar.events],
                key=lambda e: e.begin
            )
            
            # Separate past and future events
            past_events = [e for e in all_events if e.begin <= now]
            future_events = [e for e in all_events if e.begin > now]
            
            # Display last game if available
            if past_events:
                st.subheader("Letztes Spiel")
                display_game_event(past_events[-1], team_name, is_last_game=True)
            
            # Display next games (max 3)
            if future_events:
                st.subheader("Nächste Spiele")
                for event in future_events[:3]:
                    display_game_event(event, team_name)
            else:
                st.info(f"Keine zukünftigen Spiele für {team_name} gefunden.")
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der Daten für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

# Main app
st.title("🏒 Floorball Spielplan")

# Display schedule for each team
for team_name, team_id in teams.items():
    st.header(f"🔷 {team_name}")
    fetch_team_schedule(team_name, team_id)
    st.write("")  # Add some space between teams
