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

def extract_game_id(url):
    """Extract game ID from URL"""
    parts = url.split('/')
    return parts[-1] if parts else None

def get_last_game(team_id):
    """Find the last played game for a team"""
    try:
        # Get team's calendar to find recent games
        API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
        response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        
        calendar = Calendar(response.text)
        now = datetime.now(timezone.utc)
        
        # Get all past games sorted by date (newest first)
        past_events = sorted(
            [e for e in calendar.events if e.begin < now and e.url],
            key=lambda e: e.begin,
            reverse=True
        )
        
        if past_events:
            game_id = extract_game_id(past_events[0].url)
            return get_game_details(game_id) if game_id else None
        return None
    except Exception as e:
        st.error(f"Error finding last game: {str(e)}")
        return None

def format_game_data(game_data, team_id):
    """Format game data from API response"""
    if not game_data or not game_data.get('data'):
        return None
        
    attributes = game_data['data']['attributes']
    home_team = attributes.get('home_team', {})
    away_team = attributes.get('away_team', {})
    
    # Determine if our team won (for past games)
    is_home = home_team.get('id') == team_id
    home_score = attributes.get('home_team_score')
    away_score = attributes.get('away_team_score')
    
    result = None
    if home_score is not None and away_score is not None:
        won = (is_home and home_score > away_score) or (not is_home and away_score > home_score)
        result = f"{'W' if won else 'L'} {home_score}-{away_score}"
    
    return {
        'game_id': game_data['data']['id'],
        'date': attributes.get('start_time'),
        'home_team': home_team.get('name', 'Unbekannt'),
        'away_team': away_team.get('name', 'Unbekannt'),
        'home_logo': home_team.get('logo_url'),
        'away_logo': away_team.get('logo_url'),
        'location': attributes.get('location'),
        'result': result,
        'spectators': attributes.get('spectators'),
        'period_scores': attributes.get('period_scores'),
        'url': attributes.get('gamecenter_url')
    }

def display_game(game, team_name, is_past=False):
    """Display a game (past or future)"""
    if not game:
        st.warning("Keine Spieldaten verfügbar")
        return
    
    # Format date and time
    game_date = datetime.fromisoformat(game['date']).strftime("%d.%m.%Y")
    game_time = datetime.fromisoformat(game['date']).strftime("%H:%M")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        
        # Home team column
        with col1:
            if game.get('home_logo'):
                st.image(game['home_logo'], width=60)
        
        # Game info column
        with col2:
            st.subheader(f"{game['home_team']} vs {game['away_team']}")
            st.caption(f"📅 {game_date} | 🕒 {game_time}")
            
            if game.get('location'):
                st.caption(f"📍 {game['location']}")
            
            if is_past and game.get('result'):
                st.markdown(f"## {game['result']}")
                
                if game.get('period_scores'):
                    periods = " | ".join(
                        [f"{p['period']}: {p['home_score']}-{p['away_score']}" 
                        for p in game['period_scores']]
                    )
                    st.caption(f"Perioden: {periods}")
                
                if game.get('spectators'):
                    st.caption(f"👥 Zuschauer: {game['spectators']}")
            else:
                if game.get('url'):
                    st.markdown(f"[🔗 Zum Spielcenter]({game['url']})")
        
        # Away team column
        with col3:
            if game.get('away_logo'):
                st.image(game['away_logo'], width=60)
        
        st.markdown("---")

def fetch_team_schedule(team_name, team_id):
    """Fetch and display schedule for a single team"""
    with st.spinner(f"Lade Spiele für {team_name}..."):
        try:
            # Get last played game
            st.subheader("Letztes Spiel")
            last_game_raw = get_last_game(team_id)
            last_game = format_game_data(last_game_raw, team_id)
            display_game(last_game, team_name, is_past=True)
            
            # Get upcoming games
            API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
            response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            calendar = Calendar(response.text)
            now = datetime.now(timezone.utc)
            
            # Get future games with API details
            future_events = sorted(
                [e for e in calendar.events if e.begin >= now and e.url],
                key=lambda e: e.begin
            )[:3]
            
            if future_events:
                st.subheader("Kommende Spiele")
                for event in future_events:
                    game_id = extract_game_id(event.url)
                    if game_id:
                        game_data = get_game_details(game_id)
                        formatted_game = format_game_data(game_data, team_id)
                        display_game(formatted_game, team_name, is_past=False)
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
