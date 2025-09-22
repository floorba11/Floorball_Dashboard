# swiss_unihockey_dashboard.py
# -*- coding: utf-8 -*-
"""
Streamlit Dashboard für Swiss Unihockey API v2 (über dokumentierte/observierte Endpunkte)
- Nächste Spiele für definierte Teams (mit Logos)
- Liga-Tabelle (aus /api/rankings; Parameter werden aus Teaminfos versucht zu ermitteln)
- Liveticker via /api/game_events/{game_id}
- Auto-Refresh alle 30 Sekunden

Voraussetzungen:
    pip install streamlit requests streamlit-autorefresh

Starten:
    streamlit run swiss_unihockey_dashboard.py
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import datetime as dt
import json

import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api-v2.swissunihockey.ch/api/"
TIMEOUT = 15
VERIFY_SSL = True

# ----------------------- Konfiguration -----------------------
# Team-IDs -> Anzeigename
MY_TEAMS: Dict[int, str] = {
    429523: "Tigers Langnau",
    429611: "Frutigen",
    432553: "URE"
}

REFRESH_MS = 30 * 1000  # 30 Sekunden

# ----------------------- Hilfsfunktionen -----------------------

def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """HTTP GET mit robuster Fehlerbehandlung."""
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    try:
        r = requests.get(
            url,
            params=params or {},
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
            headers={
                "Accept": "application/json",
                "User-Agent": "SwissUnihockey-Dashboard/1.0 (+streamlit)",
            },
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"HTTP {r.status_code if 'r' in locals() else ''} bei {url} – {e}")
    except requests.RequestException as e:
        st.error(f"Netzwerkfehler bei {url} – {e}")
    except json.JSONDecodeError:
        st.error(f"Antwort kein JSON: {url}")
    return {}

def safe_get(d: Any, path: List[Any], default: Any=None) -> Any:
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def current_season_guess() -> int:
    """Grober Heuristik-Guess der Saison (Jahr), wie sie in API-Param 'season' verwendet wird.
    SwissUnihockey-Saisons starten typischerweise im August/September.
    """
    today = dt.date.today()
    if today.month >= 7:  # ab Juli neue Saison
        return today.year
    return today.year - 1

# ----------------------- API Wrapper v2 (beobachtete Endpunkte) -----------------------

def get_team(team_id: int) -> Dict[str, Any]:
    # Beobachtet: /api/teams/{id}
    return api_get(f"teams/{team_id}")

def get_games_team(team_id: int, season: Optional[int]=None, games_per_page: int=20, view: str="short") -> Dict[str, Any]:
    """Spiele eines Teams (beobachteter Endpunkt)."""
    if season is None:
        season = current_season_guess()
    params = {
        "mode": "team",
        "team_id": team_id,
        "season": season,
        "games_per_page": games_per_page,
        "view": view,
    }
    return api_get("games", params)

def get_game(game_id: int) -> Dict[str, Any]:
    return api_get(f"games/{game_id}")

def get_game_events(game_id: int) -> Dict[str, Any]:
    # Beobachtet: /api/game_events/{game_id}
    return api_get(f"game_events/{game_id}")

def get_rankings(season: int, league: Optional[int]=None, game_class: Optional[int]=None, group: Optional[str]=None) -> Dict[str, Any]:
    params: Dict[str, Any] = {"season": season}
    if league is not None:
        params["league"] = league
    if game_class is not None:
        params["game_class"] = game_class
    if group is not None:
        params["group"] = group
    return api_get("rankings", params)

# ----------------------- Ableitungen -----------------------

def extract_team_context(team_id: int) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Versucht league, game_class, group für ein Team abzuleiten.
    Quelle: /teams/{id} (falls vorhanden) oder aus einem Spiel-Eintrag.
    """
    info = get_team(team_id)
    league = safe_get(info, ["league", "id"])
    game_class = safe_get(info, ["game_class", "id"])
    group = safe_get(info, ["group", "name"])

    if not league or not game_class or not group:
        games = get_games_team(team_id, games_per_page=5, view="short")
        for ent in games.get("entries", []):
            g = ent.get("game", {})
            league = league or safe_get(g, ["league", "id"])
            game_class = game_class or safe_get(g, ["game_class", "id"])
            group = group or safe_get(g, ["group", "name"])
            if league and game_class and group:
                break

    return league, game_class, group

def parse_games_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ent in data.get("entries", []) or []:
        g = ent.get("game", {})
        # Manche Listen liefern zusätzlich "id" statt "uuid"
        gid = g.get("id") or g.get("game_id") or ent.get("id")
        # Logos: teils unter team.logo.url, teils club_logo in anderen Responses
        rows.append({
            "game_id": gid,
            "date": g.get("date") or ent.get("date", ""),
            "time": g.get("time", ""),
            "home": safe_get(g, ["home_team", "name"], ""),
            "home_logo": safe_get(g, ["home_team", "logo", "url"], None) or safe_get(g, ["home_team", "club_logo"], None),
            "away": safe_get(g, ["away_team", "name"], ""),
            "away_logo": safe_get(g, ["away_team", "logo", "url"], None) or safe_get(g, ["away_team", "club_logo"], None),
            "result": g.get("result", "-"),
            "status_text": safe_get(g, ["status", "text"], ""),
            "status_id": safe_get(g, ["status", "id"], None),
        })
    return rows

def parse_rankings_df(data: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for e in data.get("entries", []) or []:
        rows.append({
            "Platz": e.get("rank"),
            "Team": safe_get(e, ["team", "name"], e.get("team_name", "")),
            "Spiele": e.get("games") or e.get("played"),
            "Siege": e.get("wins"),
            "Unentschieden": e.get("draws"),
            "Niederlagen": e.get("losses"),
            "Tore": e.get("goals_for"),
            "Gegentore": e.get("goals_against"),
            "Tordiff": e.get("goal_diff"),
            "Punkte": e.get("points") or e.get("pts"),
        })
    df = pd.DataFrame(rows)
    if not df.empty and "Platz" in df.columns:
        df["Platz"] = pd.to_numeric(df["Platz"], errors="coerce")
        df = df.sort_values("Platz", na_position="last")
    return df

# ----------------------- Streamlit UI -----------------------

st.set_page_config(page_title="Swiss Unihockey Dashboard", layout="wide")
st.title("🏑 Swiss Unihockey Dashboard (API v2)")

# Auto-Refresh alle 30s
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, key="refresh_key")
except Exception:
    st.info("Für Autorefresh: `pip install streamlit-autorefresh` (ansonsten manuell neu laden).")

season_guess = current_season_guess()
st.caption(f"Saison-Parameter: **{season_guess}** (heuristisch)")

tab_spiele, tab_tabelle, tab_ticker = st.tabs(["📅 Spiele", "📊 Tabelle", "🎥 Liveticker"])

with tab_spiele:
    st.header("Nächste Spiele (Teams)")
    for team_id, team_name in MY_TEAMS.items():
        st.subheader(team_name)
        data = get_games_team(team_id, season=season_guess, games_per_page=10, view="short")
        rows = parse_games_rows(data)
        if not rows:
            st.info("Keine Spiele gefunden oder falsche Team-ID/Saison.")
            continue
        for r in rows[:5]:
            cols = st.columns([1, 5, 1, 5, 3, 2])
            if r["home_logo"]:
                cols[0].image(r["home_logo"], width=40)
            cols[1].markdown(f"**{r['home']}**")
            if r["away_logo"]:
                cols[2].image(r["away_logo"], width=40)
            cols[3].markdown(f"**{r['away']}**")
            cols[4].markdown(f"{r['date']} {r['time']}")
            cols[5].markdown(f"{r['result']}  \n_{r['status_text']}_")

with tab_tabelle:
    st.header("Tabellen (Liga je Team)")
    for team_id, team_name in MY_TEAMS.items():
        st.subheader(team_name)
        league, game_class, group = extract_team_context(team_id)
        if not (league and game_class and group):
            st.warning("Konnte Liga-Parameter nicht vollständig ermitteln.")
            continue
        st.caption(f"Liga-Parameter: league={league}, game_class={game_class}, group={group}")
        ranking_raw = get_rankings(season_guess, league=league, game_class=game_class, group=group)
        if not ranking_raw:
            st.info("Keine Rankings gefunden.")
            continue
        df = parse_rankings_df(ranking_raw)
        if df.empty:
            st.json(ranking_raw)  # Fallback, falls Struktur anders ist
        else:
            st.dataframe(df, use_container_width=True)

with tab_ticker:
    st.header("Liveticker")
    any_live = False
    for team_id, team_name in MY_TEAMS.items():
        games = get_games_team(team_id, season=season_guess, games_per_page=1, view="short")
        rows = parse_games_rows(games)
        if not rows:
            continue
        g = rows[0]
        # Heuristik für "live"
        is_live = (g["status_id"] == 2) or (isinstance(g["status_text"], str) and "live" in g["status_text"].lower())
        if is_live and g["game_id"]:
            any_live = True
            st.success(f"Live: {g['home']} – {g['away']} | {g['result']}")
            events = get_game_events(int(g["game_id"]))
            entries = events.get("entries", [])
            if not entries:
                st.write("Noch keine Ticker-Ereignisse.")
            else:
                for e in entries:
                    minute = e.get("minute") or e.get("time") or ""
                    text = e.get("text") or e.get("message") or ""
                    st.write(f"**{minute}** – {text}")
        else:
            st.info(f"Aktuell kein Live-Spiel für {team_name}.")
    if not any_live:
        st.caption("Wenn ein Spiel live ist, erscheint hier automatisch der Ticker.")

st.markdown("---")
st.caption("Quelle: api-v2.swissunihockey.ch | Aktualisierung alle 30 Sek.")

if __name__ == "__main__":
    pass
