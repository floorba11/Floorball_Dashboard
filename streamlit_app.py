# swiss_unihockey_dashboard.py
# -*- coding: utf-8 -*-
"""
Streamlit Dashboard für Swiss Unihockey API v2
- Zeigt nächste Spiele für definierte Teams (mit Logos)
- Zeigt Tabellenstand der Liga (Auto-Detect per Team -> bekannte/letzte Liga)
- Zeigt Liveticker, wenn ein Spiel live ist
- Auto-Refresh alle 30 Sekunden

Voraussetzungen:
    pip install streamlit requests streamlit-autorefresh

Starten:
    streamlit run swiss_unihockey_dashboard.py
"""

from __future__ import annotations
import os
import time
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
import pandas as pd
import streamlit as st

# ----------------------- Konfiguration -----------------------
BASE_URL = "https://api-v2.swissunihockey.ch/api/"
TIMEOUT = 15  # Sekunden
VERIFY_SSL = True

# Deine Teams (ID: Anzeigename)
MY_TEAMS: Dict[int, str] = {
    429523: "Tigers Langnau",
    429611: "Frutigen",
    432553: "URE"
}

REFRESH_MS = 30 * 1000  # 30 Sekunden

# ----------------------- Utils -----------------------

def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET Request gegen Swiss Unihockey API v2 mit Fehlertoleranz."""
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    try:
        r = requests.get(url, params=params or {}, timeout=TIMEOUT, verify=VERIFY_SSL,
                         headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"HTTP Fehler {r.status_code if 'r' in locals() else ''} für {url}: {e}")
    except requests.RequestException as e:
        st.error(f"Netzwerkfehler für {url}: {e}")
    except json.JSONDecodeError:
        st.error(f"Antwort ist kein JSON: {url}")
    return {}

def safe_get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

# ----------------------- API Wrapper -----------------------

def get_games_for_team(team_id: int, limit: int = 5) -> Dict[str, Any]:
    # Häufig verwendeter Endpoint (Beispiel): /games?team_id=...
    return api_get("games", {"team_id": team_id, "limit": limit})

def get_ticker_for_game(game_uuid: str) -> Dict[str, Any]:
    return api_get(f"games/{game_uuid}/ticker")

def get_team_info(team_id: int) -> Dict[str, Any]:
    """Versucht Team-Infos zu holen. Endpunkt kann variieren; wir testen mehrere Patterns."""
    # Pattern 1: /teams/{id}
    data = api_get(f"teams/{team_id}")
    if data:
        return data
    # Pattern 2: /team?id=
    data = api_get("team", {"id": team_id})
    if data:
        return data
    # Fallback: aus Spieleliste ableiten
    games = get_games_for_team(team_id, limit=10)
    return {"derived_from_games": games}

def infer_league_id_from_team(team_id: int) -> Optional[int]:
    """Versucht die League-ID eines Teams zu ermitteln.
    Strategie:
      1) Team-Info lesen und 'league' oder 'league_id' extrahieren
      2) Ansonsten aus Games die erste verfügbare 'league' herauslesen
    """
    info = get_team_info(team_id)
    # Direkte Felder
    for key in ["league_id", "leagueId", "leagueID"]:
        if isinstance(info, dict) and key in info:
            try:
                return int(info[key])
            except Exception:
                pass

    # Verschachtelt
    maybe = safe_get(info, ["team", "league", "id"])
    if isinstance(maybe, int):
        return maybe

    # Fallback über Games
    games = info.get("derived_from_games") if "derived_from_games" in info else get_games_for_team(team_id, limit=5)
    entries = games.get("entries", [])
    for ent in entries:
        # Versuche übliche Strukturen
        cand = safe_get(ent, ["game", "league", "id"])
        if isinstance(cand, int):
            return cand
        cand2 = safe_get(ent, ["league", "id"])
        if isinstance(cand2, int):
            return cand2
    return None

def get_standings_for_league(league_id: int) -> Dict[str, Any]:
    # Beispiel: /standings?league_id=...
    return api_get("standings", {"league_id": league_id})

# ----------------------- Parsing -----------------------

def parse_games_to_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for entry in data.get("entries", []) or []:
        g = entry.get("game", {})
        rows.append({
            "date": g.get("date") or safe_get(entry, ["date"], ""),
            "time": g.get("time") or "",
            "home_name": safe_get(g, ["home_team", "name"], ""),
            "home_logo": safe_get(g, ["home_team", "logo", "url"], None),
            "away_name": safe_get(g, ["away_team", "name"], ""),
            "away_logo": safe_get(g, ["away_team", "logo", "url"], None),
            "result": g.get("result", "-"),
            "status_text": safe_get(g, ["status", "text"], ""),
            "status_id": safe_get(g, ["status", "id"], None),
            "uuid": g.get("uuid") or safe_get(entry, ["uuid"], None),
        })
    return rows

def parse_standings(data: Dict[str, Any]) -> pd.DataFrame:
    """Versucht eine generische Standings-Struktur in ein DataFrame zu bringen."""
    # Häufige Struktur: {"entries":[{"rank":1,"team":{"name":...,"logo":{"url":...}},"points":...,"goals_for":...,"goals_against":...}, ...]}
    rows: List[Dict[str, Any]] = []
    entries = data.get("entries") or data.get("data") or []
    for e in entries:
        team_name = safe_get(e, ["team", "name"], e.get("team_name", ""))
        rows.append({
            "Platz": e.get("rank") or e.get("position"),
            "Team": team_name,
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
    # Sortiere, falls 'Platz' vorhanden
    if "Platz" in df.columns:
        try:
            df["Platz"] = pd.to_numeric(df["Platz"], errors="coerce")
            df = df.sort_values("Platz", na_position="last")
        except Exception:
            pass
    return df

# ----------------------- UI -----------------------

st.set_page_config(page_title="Swiss Unihockey Dashboard", layout="wide")
st.title("🏑 Swiss Unihockey Dashboard")

# Auto-Refresh: bevorzugt streamlit-autorefresh (st_autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, key="auto_refresh_key")
except Exception:
    # Fallback: Nutzerhinweis – manuell neu laden oder Paket installieren
    st.info("Installiere optional 'streamlit-autorefresh' für automatisches Aktualisieren alle 30s: "
            "`pip install streamlit-autorefresh`")

tab_spiele, tab_tabelle, tab_ticker = st.tabs(["📅 Spiele", "📊 Tabelle", "🎥 Liveticker"])

with tab_spiele:
    st.header("Nächste Spiele")
    for team_id, team_name in MY_TEAMS.items():
        st.subheader(team_name)
        data = get_games_for_team(team_id, limit=5)
        rows = parse_games_to_rows(data)
        if not rows:
            st.info("Keine Spiele gefunden.")
            continue

        # Zeilen mit Logos/Infos hübsch rendern
        for r in rows:
            c = st.container()
            cols = c.columns([1, 5, 1, 5, 3, 2])
            if r["home_logo"]:
                cols[0].image(r["home_logo"], width=40)
            cols[1].markdown(f"**{r['home_name']}**")
            if r["away_logo"]:
                cols[2].image(r["away_logo"], width=40)
            cols[3].markdown(f"**{r['away_name']}**")
            cols[4].markdown(f"{r['date']} {r['time']}")
            cols[5].markdown(f"{r['result']}  \n_{r['status_text']}_")

with tab_tabelle:
    st.header("Tabellen")
    # Wir zeigen je Team die (vermutete) Liga-Tabelle
    for team_id, team_name in MY_TEAMS.items():
        st.subheader(f"{team_name} – Liga")
        league_id = infer_league_id_from_team(team_id)
        if league_id is None:
            st.warning("Konnte Liga-ID nicht automatisch ermitteln.")
            continue
        st.caption(f"Ermittelte Liga-ID: **{league_id}**")
        standings_raw = get_standings_for_league(league_id)
        if not standings_raw:
            st.info("Keine Tabellendaten gefunden.")
            continue
        df = parse_standings(standings_raw)
        if df.empty:
            st.info("Tabellenstruktur unbekannt – Rohdaten:")
            st.json(standings_raw)
        else:
            st.dataframe(df, use_container_width=True)

with tab_ticker:
    st.header("Liveticker")
    any_live = False
    for team_id, team_name in MY_TEAMS.items():
        latest = get_games_for_team(team_id, limit=1)
        rows = parse_games_to_rows(latest)
        if not rows:
            continue
        g = rows[0]
        # Heuristik: status_id==2 (oft 'live') oder Text enthält 'live'
        is_live = (g["status_id"] == 2) or (isinstance(g["status_text"], str) and "live" in g["status_text"].lower())
        if is_live and g["uuid"]:
            any_live = True
            st.success(f"Live: {g['home_name']} – {g['away_name']}  |  {g['result']}")
            ticker = get_ticker_for_game(g["uuid"])
            entries = ticker.get("entries", [])
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

# Footer
st.markdown("---")
st.caption("Quelle: Swiss Unihockey API v2 | Aktualisierung alle 30s")


if __name__ == "__main__":
    # Streamlit startet die App über 'streamlit run', daher keine CLI-Logik nötig.
    pass
