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




# Main app
st.title("🏒 Resultate")
import requests
from icalendar import Calendar, Event
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

def get_team_calendar(team_id):
    """Holt den Kalender für ein Team im iCal-Format und gibt die Events zurück"""
    url = f"https://api-v2.swissunihockey.ch/api/calendars/team/{team_id}/games"
    response = requests.get(url)
    response.raise_for_status()
    return Calendar.from_ical(response.text)

def extract_game_id_from_url(url):
    """Extrahiert die Game ID aus einer Swiss Unihockey URL"""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return query.get('game', [None])[0]

def get_last_team_games(team_ids, days_back=30):
    """
    Findet die letzten Spiele für eine Liste von Teams
    
    :param team_ids: Dictionary mit Teamnamen als Schlüssel und Team-IDs als Werte
    :param days_back: Wie viele Tage in der Vergangenheit nach Spielen suchen
    :return: Dictionary mit Teamnamen als Schlüssel und game_id als Wert
    """
    last_games = {}
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    for team_name, team_id in team_ids.items():
        try:
            cal = get_team_calendar(team_id)
            last_game = None
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get('dtstart').dt
                    if isinstance(dtstart, datetime) and dtstart < datetime.now():
                        url = component.get('url')
                        game_id = extract_game_id_from_url(url)
                        
                        if game_id and (last_game is None or dtstart > last_game[0]):
                            last_game = (dtstart, game_id)
            
            if last_game:
                last_games[team_name] = last_game[1]
                print(f"Letztes Spiel für {team_name} am {last_game[0].strftime('%Y-%m-%d')} (ID: {last_game[1]})")
            else:
                print(f"Keine Spiele gefunden für {team_name} in den letzten {days_back} Tagen")
                
        except Exception as e:
            print(f"Fehler beim Verarbeiten von {team_name}: {str(e)}")
    
    return last_games

def get_game_details(game_id):
    """Holt die Details für ein spezifisches Spiel"""
    url = f"https://api-v2.swissunihockey.ch/api/games/{game_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def display_last_game_results(team_ids):
    """Hauptfunktion: Zeigt die letzten Spielresultate für eine Liste von Teams"""
    print("Suche nach letzten Spielen...")
    last_games = get_last_team_games(team_ids)
    
    print("\nSpielresultate:")
    for team_name, game_id in last_games.items():
        try:
            game = get_game_details(game_id)
            print(f"\n{team_name}:")
            print(f"{game['home_name']} vs {game['away_name']}")
            print(f"Datum: {game['date']} {game['time']}")
            print(f"Resultat: {game['result']}")
            print(f"Ort: {game.get('location', {}).get('address', 'N/A')}")
            print(f"Zuschauer: {game.get('spectators', 'N/A')}")
        except Exception as e:
            print(f"\nFehler beim Abrufen der Details für {team_name}: {str(e)}")

# Beispielverwendung
if __name__ == "__main__":
    # Dictionary mit Teamnamen und ihren Team-IDs
    # Diese IDs findest du in den URLs auf der Swiss Unihockey Website
    example_teams = {
"Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
    }
    
    # Führe den Abruf durch
    display_last_game_results(example_teams)

