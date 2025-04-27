import os
import requests
import time
from datetime import datetime, timedelta, timezone
from ics import Calendar
import streamlit as st

# Configure page
st.set_page_config(page_title="Team Schedule & Live Ticker", page_icon="🏒", layout="wide")

# List of teams: name + team_id
TEAMS = {
    "Tigers Langnau LUPL": 429523,
    "Herren Frutigen": 429611,
    "Jets Scheisse": 431166,
}

def get_team_logo(team_name):
    """Get team logo path or return default if not found"""
    logo_path = f"logos/{team_name.lower()}.png"
    return logo_path if os.path.exists(logo_path) else "logos/default.png"

def fetch_game_events(game_id):
    """Fetch live events for a specific game"""
    url = f"https://api-v2.swissunihockey.ch/api/game/{game_id}/events/"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Fehler beim Abrufen der Spielevents: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Fehler bei der API-Anfrage: {str(e)}")
        return None

def display_live_events(events):
    """Display live game events in Streamlit"""
    if not events or "events" not in events:
        return
    
    event_container = st.container()
    
    for event in events["events"]:
        event_type = event.get("type")
        event_time = event.get("time", "")
        team = event.get("team", {}).get("name", "Unbekannt")
        player = event.get("player", {}).get("name", "Unbekannt")
        
        with event_container:
            if event_type == "GOAL":
                st.success(f"⚽ {team}: Tor durch {player} ({event_time})")
            elif event_type == "PENALTY":
                penalty_time = event.get("penaltyTime", "2")
                st.warning(f"⚠️ {team}: Strafe gegen {player} ({penalty_time} Min)")
            elif event_type == "PERIOD_START":
                period = event.get("period", "1")
                st.info(f"🔄 {period}. Spielabschnitt gestartet")
            elif event_type == "PERIOD_END":
                period = event.get("period", "1")
                st.info(f"⏹️ {period}. Spielabschnitt beendet")

def display_future_game_event(event, team_name):
    """Display a single future game event in Streamlit"""
    name = event.name or "Unbenanntes Spiel"
    date = event.begin.strftime("%d.%m.%Y") if hasattr(event.begin, 'strftime') else event.begin
    time_str = event.begin.strftime("%H:%M") if hasattr(event.begin, 'strftime') else ""
    location = event.location or "nicht angegeben"
    url = event.url or "#"

    teams_in_game = name.split(" - ")
    home = teams_in_game[0].strip()
    away = teams_in_game[1].strip() if len(teams_in_game) > 1 else "Unbekannt"
    
    game_id = url.split("/")[-1] if url else None
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 5, 1])
    with col1:
        st.image(get_team_logo(home), width=200)
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center'>
                <h4>{name}</h4>
                <p>📅 {date} | 🕒 {time_str} | 📍 {location}</p>
                <a href="{url}" target="_blank">🔗 Zur Spielseite</a>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.image(get_team_logo(away), width=200)
    
    # Check if game is live (started but not finished)
    game_time = event.begin.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    
    if game_time <= now <= game_time + timedelta(hours=3) and game_id:
        st.subheader("🔴 Live Ticker")
        live_placeholder = st.empty()
        
        # Simple polling mechanism for live updates
        last_events_count = 0
        while True:
            events_data = fetch_game_events(game_id)
            if events_data and "events" in events_data:
                current_events = events_data["events"]
                if len(current_events) > last_events_count:
                    new_events = {"events": current_events[last_events_count:]}
                    with live_placeholder.container():
                        display_live_events(new_events)
                    last_events_count = len(current_events)
            
            # Check if game is likely finished (3 hours after start)
            if now > game_time + timedelta(hours=3):
                st.info("Spiel beendet")
                break
                
            time.sleep(10)  # Refresh every 10 seconds
    
    st.markdown("---")
    return game_id

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
            )
            
            if not future_events:
                st.info(f"Keine zukünftigen Spiele für {team_name} gefunden.")
                return
            
            # Show next game in a special section
            st.subheader(f"🔷 Nächstes Spiel")
            next_game = future_events[0]
            display_future_game_event(next_game, team_name)
            
            # Show other future games if there are any
            if len(future_events) > 1:
                st.subheader(f"🔷 Weitere zukünftige Spiele")
                for event in future_events[1:3]:  # Show max 2 additional games
                    display_future_game_event(event, team_name)
                
        except requests.exceptions.RequestException as e:
            st.error(f"Fehler beim Abrufen der zukünftigen Spiele für {team_name}: {str(e)}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

def fetch_past_games(team_name, team_id):
    """Fetch and display past games for a team"""
    with st.spinner(f"Lade letzte Spiele für {team_name}..."):
        try:
            API_URL = f"https://api-v2.swissunihockey.ch/api/v3/games"
            
            params = {
                'team': team_id,
                'result': 'true',
                'limit': 5,
                'sort': '-date'
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
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")

# Main app
st.title("🏒 Swiss Unihockey Team Übersicht mit Live Ticker")

# Display schedule for each team
for team_name, team_id in TEAMS.items():
    st.header(f"{team_name}")
    
    # First show past games
    fetch_past_games(team_name, team_id)
    
    # Then show future games (includes live ticker for next game if live)
    fetch_future_games(team_name, team_id)
    
    st.write("")  # Add some space between teams
