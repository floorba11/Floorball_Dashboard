# swiss_unihockey_dashboard_stable.py
# -*- coding: utf-8 -*-
"""
Stabiles Streamlit-Dashboard für Swiss Unihockey API v2
- Ruhigere Fehlerausgabe (gesammelt & zusammengefasst)
- Caching (TTL) + Retries mit Backoff
- Einmal abrufen, in allen Tabs wiederverwenden
- Saison wählbar, Auto-Refresh 30s

Start:
    pip install streamlit requests streamlit-autorefresh
    streamlit run swiss_unihockey_dashboard_stable.py
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import json
import time
import datetime as dt
import hashlib

import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api-v2.swissunihockey.ch/api/"
TIMEOUT = 12
VERIFY_SSL = True

# ---------- Teams anpassen ----------
MY_TEAMS: Dict[int, str] = {
    429523: "Tigers Langnau",
    429611: "Frutigen",
    432553: "URE",  # z.B. neu
}

REFRESH_MS = 30 * 1000  # 30 Sekunden
CACHE_TTL = 20          # Sekunden

# ---------- Fehler-Sammeln ----------
if "error_log" not in st.session_state:
    st.session_state["error_log"] = []

def log_error(msg: str):
    # Max 5 Einträge behalten
    st.session_state["error_log"].append({"t": dt.datetime.now().strftime("%H:%M:%S"), "msg": msg})
    st.session_state["error_log"] = st.session_state["error_log"][-5:]

# ---------- Utils ----------

def current_season_guess() -> int:
    today = dt.date.today()
    return today.year if today.month >= 7 else today.year - 1

def _cache_key(path: str, params: Optional[Dict[str, Any]]) -> str:
    raw = path + "|" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cached_get(path: str, params: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    return _api_get_uncached(path, params)

def _api_get_uncached(path: str, params: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    """GET mit 3 Retries, exponentiellem Backoff und sanfter Fehlerausgabe."""
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    headers = {"Accept": "application/json", "User-Agent": "SU-Streamlit/1.2"}
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, params=params or {}, timeout=TIMEOUT, verify=VERIFY_SSL, headers=headers)
            if r.status_code >= 400:
                # Zeige nur zusammengefasste Fehlermeldung
                snippet = ""
                try:
                    snippet = r.json()
                except Exception:
                    snippet = r.text[:200]
                last_err = f"HTTP {r.status_code} {url} params={params} details={snippet}"
                # 4xx retryt meist nicht viel, aber 429/408/409 ggf. kurz warten
                if r.status_code in (408, 409, 429, 500, 502, 503, 504):
                    time.sleep(0.6 * attempt)
                    continue
                break
            return r.json()
        except requests.RequestException as e:
            last_err = f"Netzwerkfehler bei {url}: {e}"
            time.sleep(0.5 * attempt)
    if last_err:
        log_error(last_err)
    return {}

def api_get(path: str, params: Optional[Dict[str, Any]]=None, use_cache: bool=True) -> Dict[str, Any]:
    if use_cache:
        return cached_get(path, params)
    return _api_get_uncached(path, params)

def safe_get(d: Any, path: List[Any], default: Any=None) -> Any:
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

# ---------- API Wrapper ----------

def get_team(team_id: int) -> Dict[str, Any]:
    return api_get(f"teams/{team_id}")


def get_games_team(team_id: int, season: int, per_page: int=20, view: str="short") -> Dict[str, Any]:
    """
    Team-Spiele abrufen mit strengen Parametern:
      1) mode=team (+ team_id, season, per_page, view) und – falls vorhanden – group/league/game_class
      2) Fallback: mode=club (+ club_id) wenn Team keinem group zugeordnet ist
      3) Fallback: mode=list (+ league/game_class/group) – breiter Abruf
    """
    # Versuche context zu ermitteln
    info = get_team(team_id)
    league = safe_get(info, ["league", "id"])
    game_class = safe_get(info, ["game_class", "id"])
    group = safe_get(info, ["group", "name"])
    club_id = safe_get(info, ["club", "id"])

    # 1) mode=team mit Kontext
    params_team = {
        "mode": "team",
        "team_id": team_id,
        "season": season,
        "per_page": per_page,
        "view": view,
    }
    # Nur setzen, wenn vorhanden – einige Gateways erwarten 'group'
    if group: params_team["group"] = group
    if league: params_team["league"] = league
    if game_class: params_team["game_class"] = game_class

    data = api_get("games", params_team)
    if data.get("entries"):
        data["_used_params"] = params_team
        return data

    # 2) Fallback: club
    if club_id:
        params_club = {
            "mode": "club",
            "club_id": club_id,
            "season": season,
            "per_page": per_page,
            "view": view,
        }
        data = api_get("games", params_club)
        if data.get("entries"):
            data["_used_params"] = params_club
            return data

    # 3) Fallback: list
    if league and game_class:
        params_list = {
            "mode": "list",
            "season": season,
            "league": league,
            "game_class": game_class,
            "view": "full",
        }
        if group: params_list["group"] = group
        data = api_get("games", params_list)
        if data.get("entries"):
            data["_used_params"] = params_list
            return data

    # nichts gefunden
    out = {"entries": []}
    out["_used_params"] = params_team
    return out


def get_game_events(game_id: int) -> Dict[str, Any]:
    return api_get(f"game_events/{game_id}")

def get_rankings(season: int, league: Optional[int]=None, game_class: Optional[int]=None, group: Optional[str]=None) -> Dict[str, Any]:
    params: Dict[str, Any] = {"season": season}
    if league is not None: params["league"] = league
    if game_class is not None: params["game_class"] = game_class
    if group is not None: params["group"] = group
    return api_get("rankings", params)

# ---------- Ableitungen/Parsing ----------

def extract_team_context(team_id: int, season:int) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    info = get_team(team_id)
    league = safe_get(info, ["league", "id"])
    game_class = safe_get(info, ["game_class", "id"])
    group = safe_get(info, ["group", "name"])

    if not league or not game_class or not group:
        games = get_games_team(team_id, season=season, per_page=5, view="short")
        for ent in games.get("entries", []) or []:
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
        gid = g.get("id") or g.get("game_id") or ent.get("id")
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

# ---------- Streamlit UI ----------

st.set_page_config(page_title="Swiss Unihockey Dashboard – Stable", layout="wide")
st.title("🏑 Swiss Unihockey Dashboard – Stable")

# Sidebar
with st.sidebar:
    st.header("⚙️ Einstellungen")
    season = st.number_input("Saison (Startjahr)", min_value=2015, max_value=2030,
                             value=2025, step=1, help="Startjahr der Saison (z. B. 2025 für Saison 2025/26)")
    quiet_errors = st.checkbox("Fehlermeldungen komprimieren (empfohlen)", value=True)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=REFRESH_MS, key="refresh_key")
        st.caption("🔁 Auto-Refresh aktiv (30 s)")
    except Exception:
        st.info("Optional: `pip install streamlit-autorefresh` für Auto-Refresh.")

st.caption(f"Aktive Saison: **{season}**")

# ---- EINMAL abrufen & für Tabs wiederverwenden ----
games_cache: Dict[int, Dict[str, Any]] = {}
team_meta: Dict[int, Dict[str, Any]] = {}

for tid in MY_TEAMS.keys():
    team_meta[tid] = get_team(tid)
    games_cache[tid] = get_games_team(tid, season=season, per_page=30, view="short")

tab_spiele, tab_tabelle, tab_ticker, tab_logs = st.tabs(["📅 Spiele", "📊 Tabelle", "🎥 Liveticker", "🧾 Logs"])

with tab_spiele:
    st.header("Nächste Spiele (Teams)")
    for team_id, team_name in MY_TEAMS.items():
        st.subheader(team_name)
        data = games_cache.get(team_id, {}) or {}
        rows = parse_games_rows(data)
        if not rows:
            st.warning("Keine Spiele gefunden.")
            if team_meta.get(team_id):
                st.caption(f"Team-Check: Name **{safe_get(team_meta[team_id], ['name'], '—')}**, "
                           f"Liga {safe_get(team_meta[team_id], ['league','id'])}, "
                           f"Klasse {safe_get(team_meta[team_id], ['game_class','id'])}, "
                           f"Gruppe {safe_get(team_meta[team_id], ['group','name'])}")
            if data.get("_used_params"):
                st.caption(f"Verwendete Params: `{json.dumps(data['_used_params'])}`")
            continue
        for r in rows[:8]:
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
        league = safe_get(team_meta[team_id], ["league", "id"])
        game_class = safe_get(team_meta[team_id], ["game_class", "id"])
        group = safe_get(team_meta[team_id], ["group", "name"])

        if not (league and game_class and group):
            league, game_class, group = extract_team_context(team_id, season=season)

        if not (league and game_class and group):
            st.warning("Konnte Liga-Parameter nicht vollständig ermitteln.")
            continue

        st.caption(f"Liga-Parameter: league={league}, game_class={game_class}, group={group}")
        ranking_raw = get_rankings(season, league=league, game_class=game_class, group=group)
        df = parse_rankings_df(ranking_raw)
        if df.empty:
            st.info("Keine Rankings gefunden oder unbekannte Struktur.")
        else:
            st.dataframe(df, use_container_width=True)

with tab_ticker:
    st.header("Liveticker")
    any_live = False
    for team_id, team_name in MY_TEAMS.items():
        rows = parse_games_rows(games_cache.get(team_id, {}))
        if not rows:
            continue
        g = rows[0]
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

with tab_logs:
    st.header("Zusammengefasste Fehler/Diagnose")
    if st.session_state["error_log"]:
        if quiet_errors:
            # komprimiert: nur letzte Meldung
            last = st.session_state["error_log"][-1]
            st.warning(f"Letzte Fehlermeldung ({last['t']}): {last['msg']}")
            with st.expander("Alle Meldungen anzeigen"):
                for item in st.session_state["error_log"]:
                    st.text(f"{item['t']}  {item['msg']}")
        else:
            for item in st.session_state["error_log"]:
                st.warning(f"{item['t']}  {item['msg']}")
    else:
        st.success("Keine Fehler protokolliert.")

st.markdown("---")
st.caption("Quelle: api-v2.swissunihockey.ch • Caching TTL 20s • Auto-Refresh 30s")
