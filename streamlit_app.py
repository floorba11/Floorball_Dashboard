import requests
import streamlit as st
from datetime import datetime

# Team-ID
TEAM_ID = 429523
API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={TEAM_ID}"

st.set_page_config(page_title="Nächste Spiele", layout="centered")

st.title("🏑 Nächste 3 Spiele des Teams")

# API-Daten abrufen
response = requests.get(API_URL)
if response.status_code == 200:
    data = response.json()
    games = data.get("data", {}).get("calendar", {}).get("games", [])
    
    # Nur die nächsten 3 Spiele zeigen
    count = 0
    for game in games:
        if count >= 3:
            break
        # Datum & Zeit
        date_str = game.get("game_date")
        time_str = game.get("game_time")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")

        # Gegner & Ort
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        venue = game.get("venue")

        st.subheader(f"{formatted_date} – {time_str}")
        st.write(f"🏠 {home_team} vs. {away_team}")
        st.write(f"📍 Ort: {venue}")
        st.markdown("---")
        count += 1
else:
    st.error("Fehler beim Abrufen der Spieldaten 😢")

