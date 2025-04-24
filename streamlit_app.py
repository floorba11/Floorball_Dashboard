import os
import requests
from datetime import datetime, timedelta, timezone
from ics import Calendar
from icalendar import Calendar as ICalendar
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
    logo_path = f"logos/{team_name.lower()}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def display_future_game_event(event, team_name):
    """Display a single future game event in Streamlit"""
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
        st.markdown(
            f"""
            <div style='text-align: center'>
                <h4>{name}</h4>
                <p>📅 {date} | 🕒 {time} | 📍 {location}</p>
                <a href="{url}">🔗 Zur Spielseite</a>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.image(get_team_logo(away), width=200)
    st.markdown("---")

def fetch_future_games(team_name, team_id):
    """Fetch and display future games for a single team"""
    with st.spinner(f"Lade zukünftige Spiele für {team_name}..."):
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
            
            st.subheader(f"🔷 Zukünftige Spiele")
            for event in future_events:
                display_future_game_event(event, team_name)
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der zukünftigen Spiele für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

def get_team_calendar(team_id):
    """Holt den Kalender für ein Team im iCal-Format"""
    url = f"https://api-v2.swissunihockey.ch/api/calendars/team/{team_id}/games"
    response = requests.get(url)
    response.raise_for_status()
    return ICalendar.from_ical(response.text)

def extract_game_id(url):
    """Extrahiert die Game ID aus der URL"""
    parsed = urlparse(url)
    return parse_qs(parsed.query).get('game', [None])[0]

def get_game_details(game_id):
    """Holt die Spiel-Details"""
    url = f"https://api-v2.swissunihockey.ch/api/games/{game_id}"
    response = requests.get(url)
    return response.json()

def display_past_games(team_name, team_id):
    """Display past games for a team"""
    with st.spinner(f"Lade letzte Spiele für {team_name}..."):
        try:
            cutoff_date = datetime.now() - timedelta(days=14)
            cal = get_team_calendar(team_id)
            games = []
            
            for event in cal.walk('vevent'):
                start = event.get('dtstart').dt
                if isinstance(start, datetime) and cutoff_date <= start <= datetime.now():
                    game_id = extract_game_id(str(event.get('url')))
                    if game_id:
                        games.append({
                            'date': start,
                            'game_id': game_id
                        })
            
            if not games:
                st.info(f"Keine Spiele in den letzten 14 Tagen für {team_name}.")
                return
                
            st.subheader(f"🔷 Letzte Resultate")
            for game in sorted(games, key=lambda x: x['date'], reverse=True):
                details = get_game_details(game['game_id'])
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"**{details.get('date', 'N/A')}**")
                    st.write(f"{details.get('time', 'N/A')}")
                with col2:
                    st.write(f"**{details.get('home_name', 'N/A')} vs {details.get('away_name', 'N/A')}**")
                    st.write(f"Resultat: {details.get('result', 'N/A')}")
                    st.write(f"Ort: {details.get('location', {}).get('address', 'N/A')}")
                
                st.divider()
                
        except Exception as e:
            st.error(f"Fehler bei {team_name}: {str(e)}")

# Main app
st.title("🏒 Team Übersicht")

# Display schedule for each team
for team_name, team_id in TEAMS.items():
    st.header(f"{team_name}")
    
    # First show past games
    display_past_games(team_name, team_id)
    
    # Then show future games
    fetch_future_games(team_name, team_id)
    
    st.write("")  # Add some space between teams
