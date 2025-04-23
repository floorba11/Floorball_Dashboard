# Liste von Teams: name + team_id
teams = {
    "Tigers Langnau": 429523,
    "Floorball Köniz Bern": 429524,
    "Floorball Thurgau": 429525  # Beispiel-IDs
}

def get_team_logo(name):
    path = f"logos/{name.lower()}.png"
    return path if os.path.exists(path) else "logos/default.png"

# Über alle Teams iterieren
for team_name, team_id in teams.items():
    st.header(f"🔷 {team_name}")
    API_URL = f"http://api-v2.swissunihockey.ch/api/calendars?team_id={team_id}"
    response = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})

    if response.status_code != 200:
        st.error(f"Fehler bei {team_name}")
        continue

    try:
        calendar = Calendar(response.text)
        events = sorted(calendar.events, key=lambda e: e.begin)

        now = datetime.now(timezone.utc)
        count = 0

        for event in events:
            if count >= 3:
                break
            if event.begin <= now:
                continue

            # Spielinfos
            name = event.name or "Unbenanntes Spiel"
            date = event.begin.format("DD.MM.YYYY")
            time = event.begin.format("HH:mm")
            location = event.location or "nicht angegeben"
            url = event.url or "#"

            # Teamnamen & Logos
            teams_in_game = name.split(" - ")
            home = teams_in_game[0].lower().strip()
            away = teams_in_game[1].lower().strip() if len(teams_in_game) > 1 else "unbekannt"

            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                st.image(get_team_logo(home), width=60)
            with col2:
                st.subheader(name)
            with col3:
                st.image(get_team_logo(away), width=60)

            st.write(f"📅 Datum: {date}")
            st.write(f"🕒 Uhrzeit: {time}")
            st.write(f"📍 Ort: {location}")
            st.markdown(f"🔗 [Zur Spielseite]({url})")
            st.markdown("---")

            count += 1

        if count == 0:
            st.info(f"Keine zukünftigen Spiele für {team_name} gefunden.")

    except Exception as e:
        st.error(f"Fehler bei {team_name}: {e}")
