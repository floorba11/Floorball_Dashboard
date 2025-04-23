import requests
from ics import Calendar
import streamlit as st
from datetime import datetime

TEAM_ID = 429523
API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={TEAM_ID}"
headers = {"User-Agent": "Mozilla/5.0"}

st.set_page_config(page_title="Nächste Spiele", layout="centered")
st.title("🏑 Nächste 3 Spiele des Teams")

response = requests.get(API_URL, headers=headers)

if response.status_code == 200:
    try:
        calendar = Calendar(response.text)
        events = sorted(calendar.events, key=lambda e: e.begin)  # sortieren nach Datum

        count = 0
        for event in events:
            if count >= 3:
                break
            st.subheader(event.name or "Unbenanntes Spiel")
            st.write(f"📅 Datum: {event.begin.format('DD.MM.YYYY')}")
            st.write(f"🕒 Uhrzeit: {event.begin.format('HH:mm')}")
            st.write(f"📍 Ort: {event.location or 'nicht angegeben'}")
            st.write(f"🔗 [Zur Spielseite]({event.url})" if event.url else "")
            st.markdown("---")
            count += 1

        if count == 0:
            st.info("Keine Spiele gefunden.")
    except Exception as e:
        st.error(f"Fehler beim Verarbeiten des Kalenders: {e}")
else:
    st.error(f"Fehler beim Abrufen der Daten. Statuscode: {response.status_code}")
