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
        API_URL = f"https://api-v2.swissunihockey.ch/api/game-detail?game_id={game_id}"
        response = requests.get(API_URL, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching game details: {str(e)}")
        return None

def extract_game_id(url):
    """Extract game ID from URL"""
    # Example URL format: https://www.swissunihockey.ch/game-center/game/1073714/
    if not url:
        return None
    parts = url.rstrip('/').split('/')
    return parts[-1] if parts else None

def get_team_games(team_id):
    try:
        API_URL = f"https://neuer-api-endpoint.ch/api/team-games?team_id={team_id}"
        response = requests.get(API_URL, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Authorization": "Bearer YOUR_API_KEY"  # Falls benötigt
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching team games: {str(e)}")
        return None


def format_game_data(game_data, team_id):
    """Format game data from API response"""
    if not game_data:
        return None
        
    attributes = game_data.get('game', {})
    home_team = attributes.get('homeTeam', {})
    away_team = attributes.get('awayTeam', {})
    
    # Determine if our team won (for past games)
    is_home = home_team.get('teamId') == team_id
    home_score = attributes.get('homeScore')
    away_score = attributes.get('awayScore')
    
    result = None
    if home_score is not None and away_score is not None:
        won = (is_home and home_score > away_score) or (not is_home and away_score > home_score)
        result = f"{'W' if won else 'L'} {home_score}-{away_score}"
    
    return {
        'game_id': attributes.get('gameId'),
        'date': attributes.get('startTime'),
        'home_team': home_team.get('teamName', 'Unbekannt'),
        'away_team': away_team.get('teamName', 'Unbekannt'),
        'home_logo': home_team.get('logoUrl'),
        'away_logo': away_team.get('logoUrl'),
        'location': attributes.get('venueName'),
        'result': result,
        'spectators': attributes.get('spectators'),
        'period_scores': attributes.get('periodScores'),
        'url': f"https://www.swissunihockey.ch/game-center/game/{attributes.get('gameId')}/"
    }

def display_game(game, team_name, is_past=False):
    """Display a game (past or future)"""
    if not game:
        st.warning("Keine Spieldaten verfügbar")
        return
    
    # Format date and time
    try:
        game_date = datetime.fromisoformat(game['date']).strftime("%d.%m.%Y")
        game_time = datetime.fromisoformat(game['date']).strftime("%H:%M")
    except:
        game_date = "Unbekannt"
        game_time = "Unbekannt"
    
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
                        [f"{p['periodNumber']}: {p['homeScore']}-{p['awayScore']}" 
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
            # Get all games for team
            games_data = get_team_games(team_id)
            if not games_data:
                st.error("Keine Spieldaten erhalten")
                return
                
            now = datetime.now(timezone.utc)
            
            # Separate past and future games
            past_games = []
            future_games = []
            
            for game in games_data.get('games', []):
                try:
                    game_time = datetime.fromisoformat(game.get('startTime'))
                    if game_time < now:
                        past_games.append(game)
                    else:
                        future_games.append(game)
                except:
                    continue
            
            # Display last game
            st.subheader("Letztes Spiel")
            if past_games:
                last_game = sorted(past_games, key=lambda x: x.get('startTime'), reverse=True)[0]
                formatted_game = format_game_data({'game': last_game}, team_id)
                display_game(formatted_game, team_name, is_past=True)
            else:
                st.info("Keine vergangenen Spiele gefunden")
            
            # Display next games
            st.subheader("Kommende Spiele")
            if future_games:
                for game in sorted(future_games, key=lambda x: x.get('startTime'))[:3]:
                    formatted_game = format_game_data({'game': game}, team_id)
                    display_game(formatted_game, team_name, is_past=False)
            else:
                st.info("Keine kommenden Spiele gefunden")
                
        except Exception as e:
            st.error(f"Fehler: {str(e)}")

# Main app
st.title("🏒 Floorball Spielplan")

# Display schedule for each team
for team_name, team_id in teams.items():
    st.header(f"🔷 {team_name}")
    fetch_team_schedule(team_name, team_id)
    st.write("")  # Add space between teams
