import requests
from ics import Calendar
import streamlit as st
from datetime import datetime, timezone
import os

# Einstellungen
TEAM_ID = 429523
API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={TEAM_ID}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Streamlit Setup
st.set_page_config(page_title="Nächste Spiele", layout="centered")
st.title("🏑 Nächste 3 Spiele des Teams")

# Daten abrufen
response = requests.get(API_URL, headers=HEADERS)

if response.status_code == 200:
    try:
        calendar = Calendar(response.text)
        events = sorted(calendar.events, key=lambda e: e.begin)

        now = datetime.now(timezone.utc)
        count = 0

        for event in events:
            if count >= 3:
                break
            if event.begin <= now:
                continue  # überspringe vergangene Spiele

            # Spielinformationen
            name = event.name or "Unbenanntes Spiel"
            date = event.begin.format("DD.MM.YYYY")
            time = event.begin.format("HH:mm")
            location = event.location or "nicht angegeben"
            url = event.url or "#"

            # Teamlogos extrahieren
            teams = name.split(" - ")
            home = teams[0].lower().strip()
            away = teams[1].lower().strip() if len(teams) > 1 else "unbekannt"

            def logo_path(team):
                file = f"logos/{team}.png"
                return file if os.path.exists(file) else "logos/default.png"

            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                st.image(logo_path(home), width=60)
            with col2:
                st.subheader(name)
            with col3:
                st.image(logo_path(away), width=60)

            # Infos
            st.write(f"📅 Datum: {date}")
            st.write(f"🕒 Uhrzeit: {time}")
            st.write(f"📍 Ort: {location}")
            st.markdown(f"🔗 [Zur Spielseite]({url})")
            st.markdown("---")

            count += 1

        if count == 0:
            st.info("Es gibt momentan keine zukünftigen Spiele.")

    except Exception as e:
        st.error(f"Fehler beim Verarbeiten des Kalenders: {e}")

else:
    st.error(f"Fehler beim Abrufen der API (Status: {response.status_code})")
