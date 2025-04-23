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

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    logo_path = f"logos/{team_name.lower().replace(' ', '_')}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def get_game_result(team_id):
    """Fetch last game result from Swiss Unihockey API"""
    try:
        API_URL = f"https://api-v2.swissunihockey.ch/api/v3/teams/{team_id}/relationships/last_game"
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('data'):
            game_data = data['data']['attributes']
            home_score = game_data['home_team_score']
            away_score = game_data['away_team_score']
            
            # Determine if our team won
            our_team = team_id
            is_home = game_data['home_team_id'] == our_team
            won = (is_home and home_score > away_score) or (not is_home and away_score > home_score)
            
            return {
                'score': f"{home_score}-{away_score}",
                'result': "W" if won else "L",
                'date': game_data['start_time'],
                'home_team': game_data['home_team_name'],
                'away_team': game_data['away_team_name']
            }
        return None
    except Exception as e:
        st.error(f"Error fetching result: {str(e)}")
        return None

def display_past_game(result_data, team_name):
    """Display a past game with result"""
    if not result_data:
        st.warning("Keine Ergebnisse verfügbar")
        return
    
    # Format date
    game_date = datetime.fromisoformat(result_data['date']).strftime("%d.%m.%Y")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            st.image(get_team_logo(result_data['home_team']), width=60)
        with col2:
            st.subheader(f"{result_data['home_team']} vs {result_data['away_team']}")
            st.caption(f"📅 {game_date}")
            st.markdown(f"**Ergebnis: {result_data['result']} {result_data['score']}**")
        with col3:
            st.image(get_team_logo(result_data['away_team']), width=60)
        st.markdown("---")

def display_future_game(event, team_name):
    """Display an upcoming game"""
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.format("DD.MM.YYYY")
    time = event.begin.format("HH:mm")
    location = event.location or "nicht angegeben"
    url = event.url or "#"

    teams_in_game = name.split(" - ")
    home = teams_in_game[0].strip()
    away = teams_in_game[1].strip() if len(teams_in_game) > 1 else "Unbekannt"

    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            st.image(get_team_logo(home), width=60)
        with col2:
            st.subheader(name)
            st.caption(f"📅 {date} | 🕒 {time} | 📍 {location}")
            st.markdown(f"[🔗 Zur Spielseite]({url})")
        with col3:
            st.image(get_team_logo(away), width=60)
        st.markdown("---")

def fetch_team_schedule(team_name, team_id):
    """Fetch and display schedule for a single team"""
    with st.spinner(f"Lade Spiele für {team_name}..."):
        try:
            # Get last game result
            st.subheader("Letztes Spiel")
            last_game_result = get_game_result(team_id)
            display_past_game(last_game_result, team_name)
            
            # Get upcoming games from calendar
            API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
            response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            calendar = Calendar(response.text)
            now = datetime.now(timezone.utc)
            
            # Find upcoming games
            future_events = sorted(
                [e for e in calendar.events if e.begin >= now],
                key=lambda e: e.begin
            )[:3]
            
            if future_events:
                st.subheader("Kommende Spiele")
                for event in future_events:
                    display_future_game(event, team_name)
            else:
                st.info("Keine kommenden Spiele geplant.")
                
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
    st.write("")  # Add space between teams
