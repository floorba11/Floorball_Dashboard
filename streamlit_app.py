import requests
import streamlit as st

TEAM_ID = 429523
API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={TEAM_ID}"
headers = {
    "User-Agent": "Mozilla/5.0"
}

st.title("🧪 API Test")

response = requests.get(API_URL, headers=headers)

st.subheader(f"Status Code: {response.status_code}")

# Rohdaten anzeigen
st.code(response.text[:1000], language="html")  # zeige max. 1000 Zeichen
