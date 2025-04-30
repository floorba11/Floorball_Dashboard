import os
import requests
from datetime import datetime, timedelta, timezone
from ics import Calendar
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule", page_icon="🏒", layout="wide")

# List of teams: name + team_id
TEAMS = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
    "Regio Entlebuch": 432526,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    logo_path = f"logos/{team_name.lower()}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def display_future_game_event(event, team_name):
    """Display a single future game event in Streamlit"""
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.strftime("%d.%m.%Y") if hasattr(event.begin, 'strftime') else event.begin
    time = event.begin.strftime("%H:%M") if hasattr(event.begin, 'strftime') else ""
    location = event.location or "nicht angegeben"
    url = event.url or "#"

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
            
            # Get all future events and sort by date (closest first)
            future_events = sorted(
                [e for e in calendar.events if e.begin > now],
                key=lambda e: e.begin
            )[:3]  # Limit to next 3 games
            
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
            # Using API v2 endpoint for games
            API_URL = f"https://api-v2.swissunihockey.ch/api/games"
            
            # Calculate date 14 days ago for filtering
            date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
            
            params = {
                'team': team_id,
                'played': 'true',  # Only played games
                'from': date_14_days_ago,
                'limit': 5,         # Last 5 games
                'sort': 'date',    # Sort by date (descending)
                'order': 'desc'     # Newest first
            }
            
            response = requests.get(
                API_URL,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                },
                params=params
            )
            response.raise_for_status()
            
            games = response.json().get('data', [])
            
            if not games:
                st.info(f"Keine Spiele in den letzten 14 Tagen für {team_name}.")
                return
                
            st.subheader(f"🔷 Letzte Resultate")
            
            for game in games:
                game_date = datetime.strptime(game['date'], "%Y-%m-%d").date() if 'date' in game else None
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    if game_date:
                        st.write(f"**{game_date.strftime('%d.%m.%Y')}**")
                    st.write(f"{game.get('time', 'N/A')}")
                with col2:
                    home_team = game.get('home_team', {}).get('name', 'N/A')
                    away_team = game.get('away_team', {}).get('name', 'N/A')
                    st.write(f"**{home_team} vs {away_team}**")
                    
                    if game.get('status') == 'finished':
                        home_goals = game.get('home_goals', 'N/A')
                        away_goals = game.get('away_goals', 'N/A')
                        st.write(f"Resultat: {home_goals} - {away_goals}")
                    else:
                        st.write("Spielstatus: " + game.get('status', 'N/A'))
                    
                    st.write(f"Ort: {game.get('venue', {}).get('name', 'N/A')}")
                
                st.divider()
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der letzten Spiele für {team_name}: {str(e)}")
            st.error(f"API Response: {response.text}")  # Debug-Ausgabe
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
