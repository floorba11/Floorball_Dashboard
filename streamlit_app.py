def fetch_past_games(team_name, team_id):
    """Fetch and display past games for a team"""
    with st.spinner(f"Lade letzte Spiele für {team_name}..."):
        try:
            # Using API v2 endpoint for games
            API_URL = f"https://api-v2.swissunihockey.ch/api/games"
            
            # Calculate date 14 days ago for filtering
            date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
            
            params = {
                'mode': 'team',  # Required parameter
                'team': team_id,
                'played': 'true',  # Only played games
                'from': date_14_days_ago,
                'limit': 5,       # Last 5 games
                'sort': 'date',   # Sort by date
                'order': 'desc'   # Newest first
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
            if response:
                st.error(f"API Response: {response.text}")  # Debug-Ausgabe
        except Exception as e:
            st.error(f"Unerwarteter Fehler für {team_name}: {str(e)}")
