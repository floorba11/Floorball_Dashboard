import os
import requests
from datetime import datetime, timedelta, timezone
from ics import Calendar
from urllib.parse import urlparse, parse_qs
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule", page_icon="🏒", layout="wide")

# List of teams: name + team_id
TEAMS = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    logo_path = f"logos/{team_name.lower().replace(' ', '_')}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def display_future_game_event(event, team_name):
    """Display a single future game event in Streamlit"""
    # Game info
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.strftime("%d.%m.%Y") if hasattr(event.begin, 'strftime') else event.begin
    time = event.begin.strftime("%H:%M") if hasattr(event.begin, 'strftime') else ""
    location = event.location or "nicht angegeben"
    url = event.url or "#"

    # Split team names
    teams_in_game = name.split(" - ")
    home = teams_in_game[0].strip()
    away = teams_in_game[1].strip() if len(teams_in_game) > 1 else "Unbekannt"
  
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 5, 1])
    with col1:
        st.image(get_team_logo(home), width=100)
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center'>
                <h4>{name}</h4>
                <p>📅 {date} | 🕒 {time} | 📍 {location}</p>
                <a href="{url}" target="_blank">🔗 Zur Spielseite</a>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.image(get_team_logo(away), width=100)
    st.markdown("---")

def fetch_future_games(team_name, team_id):
    """Fetch and display future games for a single team"""
    with st.spinner(f"Lade zukünftige Spiele für {team_name}..."):
        try:
            API_URL = f"https://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
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
            
            st.subheader(f"🔷 Zukünftige Spiele")
            for event in future_events:
                display_future_game_event(event, team_name)
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der zukünftigen Spiele für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

def fetch_past_games(team_name, team_id):
    """Fetch and display past games for a team"""
    with st.spinner(f"Lade letzte Spiele für {team_name}..."):
        try:
            # Neue API-Endpoint für Spielresultate
            API_URL = f"https://api-v2.swissunihockey.ch/api/games?team_id={team_id}&season=2024&page=1"
            response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            data = response.json()
            games = data.get('data', [])
            
            if not games:
                st.info(f"Keine Spiele in den letzten 14 Tagen für {team_name}.")
                return
                
            st.subheader(f"🔷 Letzte Resultate")
            
            # Filter für die letzten 14 Tage
            cutoff_date = datetime.now() - timedelta(days=14)
            past_games = []
            
            for game in games:
                game_date = datetime.strptime(game['date'], "%Y-%m-%d")
                if game_date >= cutoff_date and game['status'] == 'finished':
                    past_games.append(game)
            
            if not past_games:
                st.info(f"Keine abgeschlossenen Spiele in den letzten 14 Tagen für {team_name}.")
                return
                
            # Sort by date (newest first)
            past_games = sorted(past_games, key=lambda x: x['date'], reverse=True)[:5]  # Limit to 5 games
            
            for game in past_games:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"**{game.get('date', 'N/A')}**")
                    st.write(f"{game.get('time', 'N/A')}")
                with col2:
                    st.write(f"**{game.get('home_team', {}).get('name', 'N/A')} vs {game.get('away_team', {}).get('name', 'N/A')}**")
                    st.write(f"Resultat: {game.get('home_goals', 'N/A')} - {game.get('away_goals', 'N/A')}")
                    st.write(f"Ort: {game.get('venue', {}).get('name', 'N/A')}")
                
                st.divider()
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der letzten Spiele für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

# Main app
st.title("🏒 Team Übersicht")

# Display schedule for each team
for team_name, team_id in TEAMS.items():
    st.header(f"{team_name}")
    
    # First show past games
    fetch_past_games(team_name, team_id)
    
    # Then show future games
    fetch_future_games(team_name, team_id)
    
    st.write("")  # Add some space between teams
