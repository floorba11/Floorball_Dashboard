import os
import requests
from datetime import datetime, timedelta, timezone
from icalendar import Calendar as ICalendar
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
            
            future_events = sorted(
                [e for e in calendar.events if e.begin > now],
                key=lambda e: e.begin
            )[:3]
            
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
    """Fetch and display past games for a team using iCal"""
    with st.spinner(f"Lade letzte Spiele für {team_name}..."):
        try:
            # iCal Endpoint für vergangene Spiele
            API_URL = f"https://api-v2.swissunihockey.ch/api/calendars/team/{team_id}/games"
            response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            cal = ICalendar.from_ical(response.text)
            cutoff_date = datetime.now() - timedelta(days=14)
            past_games = []
            
            for event in cal.walk('vevent'):
                start = event.get('dtstart').dt
                if isinstance(start, datetime) and start <= datetime.now():
                    game_url = str(event.get('url', ''))
                    game_id = parse_qs(urlparse(game_url).query.get('game', [''])[0]
                    
                    if game_id:
                        past_games.append({
                            'date': start,
                            'game_id': game_id,
                            'summary': str(event.get('summary', ''))
                        })
            
            if not past_games:
                st.info(f"Keine Spiele in den letzten 14 Tagen für {team_name}.")
                return
                
            st.subheader(f"🔷 Letzte Resultate")
            
            # Sort by date (newest first) and limit to 5
            for game in sorted(past_games, key=lambda x: x['date'], reverse=True)[:5]:
                # Try to extract teams from summary (format: "Home - Away")
                teams = game['summary'].split(' - ') if ' - ' in game['summary'] else ['Unbekannt', 'Unbekannt']
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"**{game['date'].strftime('%d.%m.%Y')}**")
                with col2:
                    st.write(f"**{teams[0]} vs {teams[1]}**")
                    st.write(f"Spiel-ID: {game['game_id']}")
                    st.markdown(f"[🔗 Zum Spielbericht](https://www.swissunihockey.ch/game/{game['game_id']})", unsafe_allow_html=True)
                
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
