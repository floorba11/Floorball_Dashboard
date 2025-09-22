# swiss_unihockey_dashboard_list_fallback.py
# -*- coding: utf-8 -*-
"""
Streamlit Dashboard (stabil) mit Fallback nach CSV-Methode (mode=list)
- Primär: /api/games?mode=team&team_id=...&season=...
- Fallback: /api/games?mode=list&season=...&league=...&game_class=...&group=...  (Parsing regions/rows/cells)
- Tabellen via /api/rankings
- Liveticker via /api/game_events/{game_id}
- Season auswählbar, Auto-Refresh 30s, Caching + Retries, Debug/Logs

Start:
    pip install streamlit requests streamlit-autorefresh
    streamlit run swiss_unihockey_dashboard_list_fallback.py
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import json
import time
import datetime as dt

import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api-v2.swissunihockey.ch/api/"
TIMEOUT = 14
VERIFY_SSL = True
REFRESH_MS = 30 * 1000
CACHE_TTL = 20

# ---- Teams: ID -> Anzeigename ----
MY_TEAMS: Dict[int, str] = {
    429523: "Tigers Langnau",
    429611: "Frutigen",
    432553: "URE",
}

# ---------------- Fehlerlog ----------------
if "error_log" not in st.session_state:
    st.session_state["error_log"] = []

def log_error(msg: str):
    st.session_state["error_log"].append({"t": dt.datetime.now().strftime("%H:%M:%S"), "msg": msg})
    st.session_state["error_log"] = st.session_state["error_log"][-8:]

# ---------------- Utils ----------------
def safe_get(d: Any, path: List[Any], default: Any=None) -> Any:
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def current_season_guess() -> int:
    today = dt.date.today()
    return today.year if today.month >= 7 else today.year - 1

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def api_get(path: str, params: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    headers = {"Accept": "application/json", "User-Agent": "SU-Streamlit/1.3"}
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, params=params or {}, timeout=TIMEOUT, verify=VERIFY_SSL, headers=headers)
            if r.status_code >= 400:
                try:
                    snippet = r.json()
                except Exception:
                    snippet = r.text[:200]
                last_err = f"HTTP {r.status_code} {url} params={params} details={snippet}"
                # leichte Backoffs für 429/5xx
                if r.status_code in (408, 409, 429, 500, 502, 503, 504):
                    time.sleep(0.6 * attempt)
                    continue
                break
            return r.json()
        except requests.RequestException as e:
            last_err = f"Netzwerkfehler {url}: {e}"
            time.sleep(0.5 * attempt)
    if last_err:
        log_error(last_err)
    return {}

# ---------------- API Wrapper ----------------
def get_team(team_id: int) -> Dict[str, Any]:
    return api_get(f"teams/{team_id}")

def get_games_team_mode(team_id: int, season: int, per_page: int=20, view: str="short") -> Dict[str, Any]:
    # verschiedene Varianten probieren
    variants = [
        {"mode": "team", "team_id": team_id, "season": season, "games_per_page": per_page, "view": view},
        {"team_id": team_id, "season": season, "games_per_page": per_page, "view": view},
        {"mode": "team", "team_id": team_id, "season": season, "per_page": per_page, "view": view},
        {"team_id": team_id, "season": season, "per_page": per_page, "view": view},
        {"mode": "team", "team_id": team_id, "season": season, "per_page": per_page, "view": "extended"},
    ]
    for params in variants:
        data = api_get("games", params)
        if data.get("entries"):
            data["_used_params"] = params
            return data
    out = {"entries": []}
    out["_used_params"] = variants[0]
    return out

# ---- CSV-Methode: mode=list Parsing ----
def http_get_raw(url: str, params: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    # un-cached, für sequentielle Listenwanderung
    headers = {"Accept": "application/json", "User-Agent": "SU-Streamlit/1.3"}
    for attempt in range(1, 3):
        try:
            r = requests.get(url, params=params or {}, timeout=TIMEOUT, verify=VERIFY_SSL, headers=headers)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log_error(f"GET fail {url} params={params}: {e}")
            time.sleep(0.5 * attempt)
    return {}

def parse_list_row_min(row: Dict[str, Any]) -> Tuple[Optional[int], Dict[str, Any]]:
    cells = row.get("cells", [])
    gid = None
    info = {"date_time":"", "hall":"", "home":"", "away":"", "result":""}
    if len(cells) > 0:
        txt = cells[0].get("text", [])
        if txt: info["date_time"] = txt[0]
        ln = cells[0].get("link", {})
        if isinstance(ln, dict) and ln.get("page") == "game_detail":
            ids = ln.get("ids") or []
            if ids: gid = ids[0]
    if len(cells) > 1:
        txt = cells[1].get("text", []);  info["hall"] = txt[0] if txt else info["hall"]
    if len(cells) > 2:
        txt = cells[2].get("text", []);  info["home"] = txt[0] if txt else info["home"]
    if len(cells) > 6:
        txt = cells[6].get("text", []);  info["away"] = txt[0] if txt else info["away"]
    if len(cells) > 7:
        txt = cells[7].get("text", []);  info["result"] = " ".join(txt) if txt else info["result"]

    if gid is None:
        for c in cells:
            ln = c.get("link")
            if isinstance(ln, dict) and ln.get("page") == "game_detail":
                ids = ln.get("ids") or []
                if ids: gid = ids[0]; break
    return gid, info

def extract_ids_rows_from_list(payload: Dict[str, Any]) -> Tuple[List[int], Dict[int, Dict[str, Any]]]:
    ids: List[int] = []
    rows_info: Dict[int, Dict[str, Any]] = {}
    data = payload.get("data", {})
    for region in data.get("regions", []):
        for row in region.get("rows", []):
            gid, info = parse_list_row_min(row)
            if gid:
                ids.append(gid)
                rows_info.setdefault(gid, info)
    return ids, rows_info

def get_prev_round(payload: Dict[str, Any]) -> Optional[int]:
    slider = payload.get("data", {}).get("slider", {})
    prev = slider.get("prev")
    if isinstance(prev, dict):
        ctx = prev.get("set_in_context") or {}
        rnd = ctx.get("round")
        if isinstance(rnd, int): return rnd
    return None

def list_mode_iterate(league: str, game_class: str, season: int, group: Optional[str], max_rounds: int=80, sleep_s: float=0.3) -> Tuple[List[int], Dict[int, Dict[str, Any]]]:
    # orientiert an Zuschauer_V4.py
    params = {"mode": "list", "season": season, "league": league, "game_class": game_class, "view": "full"}
    if group: params["group"] = group
    url = BASE_URL + "games"

    all_ids: List[int] = []
    rows_map: Dict[int, Dict[str, Any]] = {}
    seen_rounds = set()
    rounds_walked = 0

    payload = http_get_raw(url, params=params)
    ids, rows = extract_ids_rows_from_list(payload)
    all_ids += ids
    rows_map.update(rows)
    prev_round = get_prev_round(payload)

    while prev_round and rounds_walked < max_rounds and prev_round not in seen_rounds:
        seen_rounds.add(prev_round)
        par2 = dict(params); par2["round"] = prev_round
        payload = http_get_raw(url, params=par2)
        ids, rows = extract_ids_rows_from_list(payload)
        for gid in ids:
            if gid not in all_ids:
                all_ids.append(gid)
        for gid, info in rows.items():
            rows_map.setdefault(gid, info)
        prev_round = get_prev_round(payload)
        rounds_walked += 1
        time.sleep(sleep_s)
    return all_ids, rows_map

def get_rankings(season: int, league: Optional[int]=None, game_class: Optional[int]=None, group: Optional[str]=None) -> Dict[str, Any]:
    params: Dict[str, Any] = {"season": season}
    if league is not None: params["league"] = league
    if game_class is not None: params["game_class"] = game_class
    if group is not None: params["group"] = group
    return api_get("rankings", params)

def get_game_events(game_id: int) -> Dict[str, Any]:
    return api_get(f"game_events/{game_id}")

# --------- Ableitungen ---------
def derive_context_from_team(team_id: int, season: int) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
    """liefert (league, game_class, group, team_name)"""
    info = get_team(team_id)
    league = safe_get(info, ["league", "id"])
    game_class = safe_get(info, ["game_class", "id"])
    group = safe_get(info, ["group", "name"])
    tname = safe_get(info, ["name"])
    return league, game_class, group, tname

def find_upcoming_for_team(team_id: int, team_name: str, season: int) -> List[Dict[str, Any]]:
    """Versucht zuerst mode=team. Wenn leer, benutzt mode=list und filtert nach Teamname."""
    out: List[Dict[str, Any]] = []
    prim = get_games_team_mode(team_id, season=season, per_page=30, view="short")
    if prim.get("entries"):
        # normaler Weg
        for ent in prim["entries"]:
            g = ent.get("game", {})
            gid = g.get("id") or g.get("game_id") or ent.get("id")
            out.append({
                "game_id": gid,
                "date_time": f"{g.get('date', '')} {g.get('time','')}",
                "home": safe_get(g, ["home_team", "name"], ""),
                "away": safe_get(g, ["away_team", "name"], ""),
                "result": g.get("result", "-"),
                "status": safe_get(g, ["status", "text"], ""),
            })
        return out[:8]

    # Fallback: list mode
    league, gclass, group, tname = derive_context_from_team(team_id, season)
    name = team_name or tname or ""
    if not (league and gclass):
        return out  # nichts möglich

    ids, rows_map = list_mode_iterate(str(league), str(gclass), season, group, max_rounds=60, sleep_s=0.25)
    # Filter: nur Spiele mit dem Teamname als Heim oder Gast
    for gid in ids:
        info = rows_map.get(gid, {})
        h = (info.get("home") or "").lower()
        a = (info.get("away") or "").lower()
        if name and (name.lower() in h or name.lower() in a):
            out.append({
                "game_id": gid,
                "date_time": info.get("date_time", ""),
                "home": info.get("home",""),
                "away": info.get("away",""),
                "result": info.get("result",""),
                "status": "",  # list-mode hat keinen Status-Text
            })
    return out[:8]

def rankings_df_for_team(team_id: int, season: int) -> pd.DataFrame:
    league, gclass, group, _ = derive_context_from_team(team_id, season)
    if not (league and gclass):
        return pd.DataFrame()
    raw = get_rankings(season, league=league, game_class=gclass, group=group)
    rows: List[Dict[str, Any]] = []
    for e in raw.get("entries", []) or []:
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

# ---------------- UI ----------------
st.set_page_config(page_title="Swiss Unihockey Dashboard – List-Fallback", layout="wide")
st.title("🏑 Swiss Unihockey Dashboard – List-Fallback")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    season = st.number_input("Saison (Startjahr)", min_value=2015, max_value=2030, value=2025, step=1)
    show_debug = st.checkbox("Debug anzeigen", value=False)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=REFRESH_MS, key="refresh_key")
        st.caption("🔁 Auto-Refresh aktiv (30 s)")
    except Exception:
        st.info("Optional: `pip install streamlit-autorefresh` für Auto-Refresh.")

st.caption(f"Aktive Saison: **{season}**")

# Vorab: Team-Metadaten (für Logos, Liga-Params)
team_meta: Dict[int, Dict[str, Any]] = {}
for tid in MY_TEAMS:
    team_meta[tid] = get_team(tid)

tab_spiele, tab_tabelle, tab_ticker, tab_logs = st.tabs(["📅 Spiele", "📊 Tabelle", "🎥 Liveticker", "🧾 Logs"])

with tab_spiele:
    st.header("Nächste Spiele (mit Fallback)")
    for tid, name in MY_TEAMS.items():
        st.subheader(name)
        rows = find_upcoming_for_team(tid, name, season)
        if not rows:
            st.warning("Keine Spiele gefunden (Team-Mode leer, List-Fallback ergab keine Treffer).")
            meta = team_meta.get(tid, {})
            st.caption(f"Team-Check: **{safe_get(meta, ['name'],'—')}** | league={safe_get(meta,['league','id'])}, class={safe_get(meta,['game_class','id'])}, group={safe_get(meta,['group','name'])}")
            continue
        for r in rows:
            # Logos über Team-Meta (Heim/Auswärts-Namen matchen)
            home_logo = safe_get(meta := team_meta.get(tid, {}), ["logo","url"], None)
            # wir können nicht sicher beide Logos holen; zeigen nur bekannte an
            cols = st.columns([1,5,1,5,4,2])
            if home_logo and (r["home"].lower() in (safe_get(meta, ["name"], "").lower())):
                cols[0].image(home_logo, width=40)
            cols[1].markdown(f"**{r['home']}**")
            cols[2].write("vs")
            cols[3].markdown(f"**{r['away']}**")
            cols[4].markdown(r["date_time"])
            cols[5].markdown(r["result"] if r["result"] else "-")

with tab_tabelle:
    st.header("Tabellen")
    for tid, name in MY_TEAMS.items():
        st.subheader(name)
        df = rankings_df_for_team(tid, season)
        if df.empty:
            st.info("Keine Rankings gefunden oder Team-Kontext unvollständig.")
        else:
            st.dataframe(df, use_container_width=True)

with tab_ticker:
    st.header("Liveticker")
    any_live = False
    for tid, name in MY_TEAMS.items():
        rows = find_upcoming_for_team(tid, name, season)
        if not rows:
            continue
        g = rows[0]
        # Kein Status im list-fallback; versuche Game-Events direkt
        gid = g.get("game_id")
        if not gid:
            continue
        events = get_game_events(int(gid))
        entries = events.get("entries", [])
        if entries:
            any_live = True
            st.success(f"Live(?) {g['home']} – {g['away']} | {g['result'] or ''}")
            for e in entries:
                minute = e.get("minute") or e.get("time") or ""
                text = e.get("text") or e.get("message") or ""
                st.write(f"**{minute}** – {text}")
        else:
            st.info(f"Aktuell kein Ticker für {name}.")
    if not any_live:
        st.caption("Kein aktiver Liveticker gefunden.")

with tab_logs:
    st.header("🧾 Fehlermeldungen / Debug")
    if st.session_state["error_log"]:
        for it in st.session_state["error_log"]:
            st.warning(f"{it['t']}  {it['msg']}")
    else:
        st.success("Keine Fehler protokolliert.")
    if st.checkbox("Zuletzt verwendete Parameter anzeigen"):
        st.json({"teams": list(MY_TEAMS.keys()), "season": season})
