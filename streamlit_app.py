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

def get_game_details(game_id):
    """Fetch detailed game information from API"""
    try:
        API_URL = f"https://api-v2.swissunihockey.ch/api/games/{game_id}"
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching game details: {str(e)}")
        return None

def get_last_game_result(team_id):
    """Fetch last game result from Swiss Unihockey API"""
    try:
        # First get basic info from relationships endpoint
        API_URL = f"https://api-v2.swissunihockey.ch/api/v3/teams/{team_id}/relationships/last_game"
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data'):
            return None
            
        basic_info = data['data']['attributes']
        game_id = data['data']['id']
        
        # Now get detailed info from games endpoint
        details = get_game_details(game_id)
        if not details:
            return None
            
        detailed_info = details['data']['attributes']
        
        # Determine if our team won
        our_team = team_id
        is_home = basic_info['home_team_id'] == our_team
        won = (is_home and basic_info['home_team_score'] > basic_info['away_team_score']) or \
              (not is_home and basic_info['away_team_score'] > basic_info['home_team_score'])
        
        return {
            'game_id': game_id,
            'score': f"{basic_info['home_team_score']}-{basic_info['away_team_score']}",
            'result': "W" if won else "L",
            'date': basic_info['start_time'],
            'home_team': basic_info['home_team_name'],
            'away_team': basic_info['away_team_name'],
            'attendance': detailed_info.get('spectators'),
            'period_scores': detailed_info.get('period_scores'),
            'home_logo': detailed_info.get('home_team', {}).get('logo_url'),
            'away_logo': detailed_info.get('away_team', {}).get('logo_url')
        }
    except Exception as e:
        st.error(f"Error fetching result: {str(e)}")
        return None

def display_past_game(result_data, team_name):
    """Display a past game with detailed result"""
    if not result_data:
        st.warning("Keine Ergebnisse verfügbar")
        return
    
    # Format date
    game_date = datetime.fromisoformat(result_data['date']).strftime("%d.%m.%Y")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        
        # Home team column
        with col1:
            if result_data.get('home_logo'):
                st.image(result_data['home_logo'], width=60)
            else:
                st.image(get_team_logo(result_data['home_team']), width=60)
        
        # Game info column
        with col2:
            st.subheader(f"{result_data['home_team']} vs {result_data['away_team']}")
            st.caption(f"📅 {game_date}")
            
            # Main score
            st.markdown(f"## {result_data['result']} {result_data['score']}")
            
            # Period scores if available
            if result_data.get('period_scores'):
                periods = " | ".join([f"{p['period']}: {p['home_score']}-{p['away_score']}" 
                              for p in result_data['period_scores']])
                st.caption(f"Perioden: {periods}")
            
            # Attendance if available
            if result_data.get('attendance'):
                st.caption(f"👥 Zuschauer: {result_data['attendance']}")
        
        # Away team column
        with col3:
            if result_data.get('away_logo'):
                st.image(result_data['away_logo'], width=60)
            else:
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
            # Get last game with detailed results
            st.subheader("Letztes Spiel")
            last_game_result = get_last_game_result(team_id)
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
