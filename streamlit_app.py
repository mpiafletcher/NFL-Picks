# nfl_picks_full_fixed.py
import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta, date
import pytz
from dateutil import parser as dateparser
import uuid


# Inicializar session_state antes de usarlo para evitar errores
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.is_admin = False
    st.session_state.page = "login"
   
# CSS para login (fondo azul solo en login/registro)
if not st.session_state.authenticated and st.session_state.page in ["login", "register"]:
    st.markdown("""
    <style>
    .stApp {
        background: #003366 !important;
    }
    .stAppHeader {          
        background: #D50A0A !important;
        color: #ffffff !important;
        padding: 10px;
    }
    h1,h2,h3,h4,h5,h6, label, .stMarkdown {
        color: #ffffff !important;
    }
    .stTextInput input, .stNumberInput input,
    .stDateInput input, .stTextArea textarea {
        background-color: #ffffff !important;
        color: #003366 !important;
        -webkit-text-fill-color: #003366 !important;
    }
    .stButton > button {
        background: linear-gradient(90deg, #0055a5, #003366) !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
    }
    .stButton > button:hover {
        filter: brightness(1.08) !important;
        color: #ffffff !important;
    }
    /* ===== Header rojo visible en toda la app ===== */
    .stAppHeader, .nfl-header {
        background: #D50A0A !important;
        color: #ffffff !important;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    # Agrega el logo arriba del login
    st.markdown(
        """
        <div style='display: flex; justify-content: center; margin-bottom: 1.5rem;'>
            <img src="https://upload.wikimedia.org/wikipedia/en/a/a2/National_Football_League_logo.svg" alt="NFL Logo" height="80">
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    # CSS para el resto de la app (fondo claro), menú lateral azul, header rojo y botones correctos
    st.markdown("""
    <style>
    .stApp {
        background: #f5f7fa !important;
    }
    /* Sidebar azul con texto blanco */
    section[data-testid="stSidebar"] {
        background: #003366 !important;
        color: #fff !important;
    }
    section[data-testid="stSidebar"] * {
        color: #fff !important;
    }
    /* ===== Header rojo visible en toda la app ===== */
    .stAppHeader, .nfl-header {
        background: #D50A0A !important;
        color: #ffffff !important;
        padding: 10px;
    }
    .nfl-header img {
        height: 50px;
    }
    .nfl-header h1 {
        color: white;
        font-size: 1.8rem;
        margin: 0;
    }
    /* Botón de logout en sidebar: fondo blanco, texto azul, borde azul */
    section[data-testid="stSidebar"] button {
        background: #fff !important;
        color: #003366 !important;
        border: 2px solid #0055a5 !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        margin-top: 10px !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background: #e9f1ff !important;
        color: #003366 !important;
        border: 2px solid #003366 !important;
    }
    /* Botones generales: texto blanco siempre, incluso en hover */
    div.stButton > button {
        background: linear-gradient(90deg, #0055a5, #003366) !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        border: none !important;
        transition: filter 0.2s;
    }
    div.stButton > button:hover, div.stButton > button:focus, div.stButton > button:active {
        filter: brightness(1.08) !important;
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)
    # Agrega el logo y título en la cabecera de la app
    st.markdown(
        """
        <div class="nfl-header">
            <img src="https://upload.wikimedia.org/wikipedia/en/a/a2/National_Football_League_logo.svg" alt="NFL Logo">
            <h1>NFL Picks</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------- CONFIG ----------------
DB_FILE = "nfl_picks.db"
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
DUBLIN_TZ = pytz.timezone("Europe/Dublin")
UTC = pytz.UTC
MAX_PICKS_PER_WEEK = 5


# ---------------- DB helpers ----------------
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_pw(password: str) -> str:
    return hashlib.sha256((password or "").encode()).hexdigest()


def migrate_or_create_users_table(conn):
    """
    Ensure users table has username, password_hash, is_admin.
    If an old 'password' column exists, migrate to 'password_hash'.
    """
    c = conn.cursor()
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0,1))
            )
            """)
        conn.commit()
        return

    # table exists — ensure columns
    c.execute("PRAGMA table_info(users)")
    cols_info = c.fetchall()
    cols = [cinfo[1] for cinfo in cols_info]

    if "password_hash" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.commit()
        if "password" in cols:
            # migrate legacy plaintext password -> hashed column
            c.execute("SELECT username, password FROM users")
            for username, pw in c.fetchall():
                try:
                    c.execute(
                        "UPDATE users SET password_hash=? WHERE username=?",
                        (hash_pw(pw or ""), username))
                except Exception:
                    pass
            conn.commit()

    if "is_admin" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()


def init_db():
    conn = get_conn()
    migrate_or_create_users_table(conn)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS fixtures (
            id TEXT PRIMARY KEY,
            home TEXT,
            away TEXT,
            kickoff TEXT,
            spread_home REAL,
            spread_away REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS picks (
            username TEXT,
            fixture_id TEXT,
            pick_team TEXT,
            PRIMARY KEY (username, fixture_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            fixture_id TEXT PRIMARY KEY,
            score_home INTEGER,
            score_away INTEGER
        )
    """)
    # store published results week (year, week) - only last row matters
    c.execute("""
        CREATE TABLE IF NOT EXISTS results_week (
            year INTEGER,
            week INTEGER
        )
    """)
    conn.commit()
    conn.close()

    # ensure admin user exists
    create_default_admin()


def create_default_admin():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT username FROM users WHERE username=?", ("admin", ))
        if not c.fetchone():
            add_user("admin", "admin123", is_admin=True)
    except Exception:
        add_user("admin", "admin123", is_admin=True)
    finally:
        conn.close()


# ---------------- Users ----------------
def add_user(username: str, password: str, is_admin: bool = False):
    if not username or not password:
        return
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, hash_pw(password), 1 if is_admin else 0),
        )
    except sqlite3.IntegrityError:
        # user exists -> update password_hash if needed
        try:
            c.execute("UPDATE users SET password_hash=? WHERE username=?",
                      (hash_pw(password), username))
        except Exception:
            pass
    conn.commit()
    conn.close()


def validate_user(username: str, password: str):
    """Return (valid: bool, is_admin: bool)."""
    if not username or not password:
        return False, False
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT password_hash, is_admin FROM users WHERE username=?",
              (username, ))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, False
    return (row[0] == hash_pw(password)), bool(row[1])


def is_admin_user(username: str) -> bool:
    if not username:
        return False
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE username=?", (username, ))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


# ---------------- Fixtures (Odds API) ----------------
def fetch_fixtures_from_oddsapi(regions="us", markets="spreads"):
    """Return a list of fixtures tuples (id, home, away, kickoff, spread_home, spread_away)."""
    if not ODDS_API_KEY:
        st.warning("ODDS_API_KEY not configured — skipping Odds API fetch.")
        return []

    params = {
        "apiKey": st.secrets["ODDS_API_KEY"],
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
    }
    try:
        r = requests.get(ODDS_API_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        st.error(f"Failed to fetch from Odds API: {e}")
        return []

    fixtures = []
    for g in data:
        fid = g.get("id") or uuid.uuid4().hex
        home = g.get("home_team")
        away = g.get("away_team")
        kickoff = g.get("commence_time")
        spread_home = None
        spread_away = None
        try:
            for bm in g.get("bookmakers", []):
                for mk in bm.get("markets", []):
                    if mk.get("key") == "spreads":
                        for o in mk.get("outcomes", []):
                            name = o.get("name")
                            point = o.get("point")
                            if name == home:
                                spread_home = float(
                                    point) if point is not None else None
                            elif name == away:
                                spread_away = float(
                                    point) if point is not None else None
                        raise StopIteration
        except StopIteration:
            pass
        except Exception:
            pass

        if fid and home and away:
            fixtures.append(
                (fid, home, away, kickoff, spread_home, spread_away))
    return fixtures


def save_fixtures(fixtures):
    """Insert or update fixtures. Returns number saved (new or updated)."""
    if not fixtures:
        return 0
    conn = get_conn()
    c = conn.cursor()
    saved = 0
    for f in fixtures:
        fid, home, away, kickoff, sh, sa = f
        try:
            # upsert by id
            c.execute(
                """
                INSERT INTO fixtures (id, home, away, kickoff, spread_home, spread_away)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  home=excluded.home,
                  away=excluded.away,
                  kickoff=excluded.kickoff,
                  spread_home=excluded.spread_home,
                  spread_away=excluded.spread_away
            """, (fid, home, away, kickoff, sh, sa))
            saved += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return saved


def load_all_fixtures():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, home, away, kickoff, spread_home, spread_away FROM fixtures ORDER BY kickoff"
    )
    rows = c.fetchall()
    conn.close()
    return rows


def fixtures_to_dataframe(rows):
    out = []
    for r in rows:
        fid, home, away, kickoff_iso, sh, sa = r
        kickoff_str = None
        kickoff_dt = safe_parse(kickoff_iso)
        if kickoff_dt:
            kickoff_str = kickoff_dt.astimezone(DUBLIN_TZ).strftime(
                "%a %d %b %H:%M")
        out.append({
            "FixtureID": fid,
            "Home": home,
            "Away": away,
            "Kickoff (Dublin)": kickoff_str,
            "Spread Home": sh,
            "Spread Away": sa,
        })
    return pd.DataFrame(out)


# ---------------- Helpers ----------------
def safe_parse(iso_str):
    if not iso_str:
        return None
    try:
        dt = dateparser.isoparse(iso_str)
    except Exception:
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_spread(v):
    if v is None:
        return ""
    try:
        vv = float(v)
    except Exception:
        return ""
    return f"{vv:+.1f}"


def week_of_earliest_upcoming():
    now = datetime.now(UTC)
    rows = load_all_fixtures()
    next_dates = []
    for r in rows:
        kickoff = safe_parse(r[3])
        if kickoff and kickoff >= now:
            next_dates.append(kickoff.date())
    if not next_dates:
        return None
    earliest = min(next_dates)
    return earliest.isocalendar()[0], earliest.isocalendar()[1]


def previous_iso_week(year_week_tuple):
    """Return (year, week) of previous ISO week to the supplied (year, week)."""
    if not year_week_tuple:
        return None
    y, w = year_week_tuple
    try:
        # pick Monday of that week and subtract 7 days
        dt = date.fromisocalendar(y, w, 1) - timedelta(days=7)
        return dt.isocalendar()[0], dt.isocalendar()[1]
    except Exception:
        return None


def fixtures_for_week(year_week_tuple):
    if not year_week_tuple:
        return []
    y, w = year_week_tuple
    rows = load_all_fixtures()
    out = []
    for r in rows:
        kickoff = safe_parse(r[3])
        if kickoff:
            iy, iw, _ = kickoff.isocalendar()
            if iy == y and iw == w:
                out.append(r)
    return out


def fixtures_for_current_week():
    wk = week_of_earliest_upcoming()
    return fixtures_for_week(wk)


# ---------------- Picks ----------------
def get_user_picks(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT fixture_id, pick_team FROM picks WHERE username=?",
              (username, ))
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def save_user_picks_for_week(username, selections: dict):
    week_rows = fixtures_for_current_week()
    if not week_rows:
        return 0, "No fixtures for the current week."

    id_to_matchkey = {}
    matchkey_to_ids = {}
    fid_to_kickoff = {}
    for r in week_rows:
        fid, home, away, kickoff, sh, sa = r
        key = tuple(sorted([home.strip().lower(), away.strip().lower()]))
        id_to_matchkey[fid] = key
        matchkey_to_ids.setdefault(key, []).append(fid)
        fid_to_kickoff[fid] = safe_parse(kickoff) or datetime.max.replace(
            tzinfo=UTC)

    existing = get_user_picks(username)
    for fid in list(existing.keys()):
        if fid in id_to_matchkey:
            del existing[fid]

    match_selections = {}
    for fid, team in selections.items():
        if fid not in id_to_matchkey:
            continue
        key = id_to_matchkey[fid]
        candidate_ids = matchkey_to_ids.get(key, [fid])
        canonical = min(candidate_ids,
                        key=lambda i: fid_to_kickoff.get(
                            i, datetime.max.replace(tzinfo=UTC)))
        match_selections[key] = (canonical, team)

    if len(match_selections) + len(existing) > MAX_PICKS_PER_WEEK:
        return 0, f"Too many picks. You may only have up to {MAX_PICKS_PER_WEEK} picks combining existing and new selections."

    conn = get_conn()
    c = conn.cursor()
    week_ids = [r[0] for r in week_rows]
    if week_ids:
        placeholders = ",".join("?" * len(week_ids))
        c.execute(
            f"DELETE FROM picks WHERE username=? AND fixture_id IN ({placeholders})",
            tuple([username] + week_ids))
        conn.commit()

    saved_count = 0
    for key, (fid, team) in match_selections.items():
        c.execute(
            "INSERT OR REPLACE INTO picks (username, fixture_id, pick_team) VALUES (?, ?, ?)",
            (username, fid, team))
        saved_count += 1
    conn.commit()
    conn.close()
    return saved_count, None


# ---------------- Selections summary ----------------
def selections_summary_for_week():
    week_rows = fixtures_for_current_week()
    if not week_rows:
        return pd.DataFrame(columns=["Team", "Selections"])
    id_to_names = {r[0]: (r[1], r[2]) for r in week_rows}
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT fixture_id, pick_team FROM picks")
    rows = c.fetchall()
    conn.close()
    counts = {}
    for fid, team in rows:
        if fid not in id_to_names:
            continue
        counts[team] = counts.get(team, 0) + 1
    df = pd.DataFrame([{
        "Team": k,
        "Selections": v
    } for k, v in sorted(counts.items(), key=lambda x: -x[1])])
    return df


# ---------------- Results storage ----------------
def save_result(fixture_id, score_home, score_away):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO results (fixture_id, score_home, score_away) VALUES (?, ?, ?)",
        (fixture_id, int(score_home), int(score_away)))
    conn.commit()
    conn.close()


def load_results_map():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT fixture_id, score_home, score_away FROM results")
    rows = c.fetchall()
    conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


# ---------------- Published results week helpers ----------------
def get_published_week():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT year, week FROM results_week ORDER BY year DESC, week DESC LIMIT 1"
    )
    row = c.fetchone()
    conn.close()
    return (row[0], row[1]) if row else None


def set_published_week(year_week_tuple):
    if not year_week_tuple:
        return
    year, week = year_week_tuple
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM results_week")
    c.execute("INSERT INTO results_week (year, week) VALUES (?, ?)",
              (year, week))
    conn.commit()
    conn.close()


def results_exist_for_published_week():
    pub = get_published_week()
    if not pub:
        return False
    week_rows = fixtures_for_week(pub)
    if not week_rows:
        return False
    rm = load_results_map()
    return any(r[0] in rm for r in week_rows)


# ---------------- Fetch ESPN results (previous week) ----------------
def fetch_results_from_espn_for_week():
    """
    Fetch scoreboard from ESPN for the *current* week relative to earliest upcoming fixtures,
    attempt to match fixtures in DB (for that week) and save results.
    """
    wk = week_of_earliest_upcoming()
    if wk is None:
        return 0, "No upcoming week to compute current week from."
    year, weeknum = wk   # 👈 take current week, not previous

    saved = 0
    try:
        week_start = date.fromisocalendar(year, weeknum, 1)
    except Exception:
        return 0, "Error computing week dates."

    for d in [week_start + timedelta(days=i) for i in range(7)]:
        date_str = d.strftime("%Y%m%d")
        try:
            resp = requests.get(ESPN_SCOREBOARD_URL,
                                params={"dates": date_str},
                                timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        events = data.get("events", [])
        week_rows = fixtures_for_week((year, weeknum))
        for ev in events:
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home_comp or not away_comp:
                try:
                    home_comp, away_comp = competitors[1], competitors[0]
                except Exception:
                    continue

            home_name = home_comp.get("team", {}).get("displayName", "")
            away_name = away_comp.get("team", {}).get("displayName", "")
            score_home = int(home_comp.get("score") or 0)
            score_away = int(away_comp.get("score") or 0)

            for r in week_rows:
                fid, home, away, kickoff, sh, sa = r
                hn, an = home.lower(), away.lower()
                if (home_name.lower() in hn or hn in home_name.lower()) and (away_name.lower() in an or an in away_name.lower()):
                    save_result(fid, score_home, score_away)
                    saved += 1
                elif (home_name.lower() in an or an in home_name.lower()) and (away_name.lower() in hn or hn in home_name.lower()):
                    save_result(fid, score_away, score_home)
                    saved += 1
                else:
                    if any(w in home_name.lower() for w in home.lower().split()) and any(w in away_name.lower() for w in away.lower().split()):
                        save_result(fid, score_home, score_away)
                        saved += 1

    if saved > 0:
        set_published_week((year, weeknum))   # ✅ publish current week
        return saved, None
    return 0, "No results matched for that week."

# ---------------- Scoring / Leaderboard (cumulative) ----------------
def compute_leaderboard():
    """
    Cumulative leaderboard across the whole session.
    - 3 pts for win after applying spread
    - 1 pt for push (adjusted tie)
    - 0 pts for loss
    Only fixtures with results in the 'results' table count towards points.
    Returns a pandas DataFrame sorted by Points desc.
    """
    conn = get_conn()
    c = conn.cursor()

    # get non-admin players
    c.execute("SELECT username FROM users WHERE is_admin=0")
    players = [r[0] for r in c.fetchall()]

    # load fixtures (teams + spreads)
    c.execute("SELECT id, home, away, spread_home, spread_away FROM fixtures")
    fixtures_rows = c.fetchall()
    fixtures = {}
    for fid, home, away, sh, sa in fixtures_rows:
        fixtures[fid] = {"home": home, "away": away, "sh": sh, "sa": sa}

    # load results (source of truth for finished games)
    c.execute("SELECT fixture_id, score_home, score_away FROM results")
    results_rows = c.fetchall()
    results = {r[0]: (r[1], r[2]) for r in results_rows}

    conn.close()

    leaderboard = []
    for player in players:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT fixture_id, pick_team FROM picks WHERE username=?",
                  (player, ))
        picks = c.fetchall()
        conn.close()

        total_points = 0
        played_count = 0
        for fid, pick_team in picks:
            # pick must reference a known fixture and there must be a result saved
            if fid not in fixtures or fid not in results:
                continue

            f = fixtures[fid]
            score_home, score_away = results[fid]

            # get spreads, infer counterpart if missing
            sh, sa = f.get("sh"), f.get("sa")
            if sh is None and sa is not None:
                sh = -sa
            if sa is None and sh is not None:
                sa = -sh

            # compute adjusted scores using spread for the selected team
            if pick_team == f["home"]:
                adj_sel = (score_home or 0) + (sh or 0)
                adj_opp = (score_away or 0) + (sa or 0)
            else:
                adj_sel = (score_away or 0) + (sa or 0)
                adj_opp = (score_home or 0) + (sh or 0)

            if adj_sel > adj_opp:
                total_points += 3
            elif abs(adj_sel - adj_opp) < 1e-9:
                total_points += 1
            # else 0

            played_count += 1

        leaderboard.append({
            "Player": player,
            "Points": total_points,
            "Played": played_count
        })

    df = pd.DataFrame(leaderboard)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Points", "Played"])
    df = df.sort_values("Points", ascending=False).reset_index(drop=True)
    return df


# ---------------- Results view table ----------------
def build_results_table(for_admin: bool = False):
    """
    If for_admin True:
       - show current-week fixtures if no published_week exists (plain)
       - otherwise show published_week colored table
    If for_admin False:
       - show only published_week (colored) — otherwise return None
    Returns: display_df, styler_or_None
    """
    pub = get_published_week()
    if for_admin:
        week_rows = fixtures_for_week(
            pub) if pub else fixtures_for_current_week()
        color = bool(pub)
    else:
        if not pub:
            return None, None
        week_rows = fixtures_for_week(pub)
        color = True

    if not week_rows:
        return None, None

    # map fid -> metadata
    fid_map = {
        r[0]: (r[1], r[2], safe_parse(r[3]), r[4], r[5])
        for r in week_rows
    }
    results_map = load_results_map()

    # players (non-admin)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE is_admin=0")
    players = [r[0] for r in c.fetchall()]
    conn.close()

    rows = []
    now = datetime.now(UTC)

    for player in players:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT fixture_id, pick_team FROM picks WHERE username=?",
                  (player, ))
        raw = c.fetchall()
        conn.close()

        picks = [(fid, team, fid_map[fid][2]) for fid, team in raw
                 if fid in fid_map]
        picks_sorted = sorted(
            picks, key=lambda x: x[2] or datetime.max.replace(tzinfo=UTC))

        cells = []
        for i in range(MAX_PICKS_PER_WEEK):
            if i < len(picks_sorted):
                fid, team, kickoff = picks_sorted[i]
                if fid in results_map:
                    score_home, score_away = results_map[fid]
                    # if results exist but appear to be pre-game zeros and kickoff in future -> treat as not played
                    if (score_home == 0
                            and score_away == 0) and kickoff and kickoff > now:
                        cells.append((team, None))
                    else:
                        sh, sa = fid_map[fid][3], fid_map[fid][4]
                        if sh is None and sa is not None:
                            sh = -sa
                        if sa is None and sh is not None:
                            sa = -sh
                        if team == fid_map[fid][0]:
                            adj_sel = score_home + (sh or 0)
                            adj_opp = score_away + (sa or 0)
                        else:
                            adj_sel = score_away + (sa or 0)
                            adj_opp = score_home + (sh or 0)
                        if adj_sel > adj_opp:
                            outcome = 3
                        elif abs(adj_sel - adj_opp) < 1e-9:
                            outcome = 1
                        else:
                            outcome = 0
                        cells.append((team, outcome))
                else:
                    cells.append((team, None))
            else:
                cells.append(("", None))

        row = {"Player": player}
        for idx, (team, outcome) in enumerate(cells, start=1):
            row[f"Pick {idx}"] = team
            row[f"Outcome {idx}"] = outcome
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return None, None

    display_cols = [c for c in df.columns if not c.startswith("Outcome ")]
    display_df = df[display_cols].copy()

    if not color:
        # return plain dataframe (no styling)
        return display_df, None

    # build styler
    def outcome_color(val, outcome):
        if outcome == 3:
            return "background-color: #b7eb8f"
        elif outcome == 1:
            return "background-color: #fff59d"
        elif outcome == 0:
            return "background-color: #f7a8a8"
        else:
            return ""

    styler = display_df.style
    for idx in range(1, MAX_PICKS_PER_WEEK + 1):
        col = f"Pick {idx}"
        outcomes = df[f"Outcome {idx}"]
        # apply mapping column-wise
        styler = styler.apply(
            lambda s, outcomes=outcomes:
            [outcome_color(v, o) for v, o in zip(s, outcomes)],
            axis=0,
            subset=[col])

    return display_df, styler


# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="NFL Picks (Fixed)", layout="wide")


def results_exist_for_published_week():
    return results_exist_for_published_week  # keep signature but main uses build_results_table / get_published_week


def main():
    init_db()

    # session defaults
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.is_admin = False
        st.session_state.page = "login"

    # --- Login / Register ---
    if not st.session_state.authenticated and st.session_state.page == "login":
        st.title("NFL Picks — Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Login", key="login_btn", help="Sign in", use_container_width=True):
                valid, is_admin = validate_user(username, password)
                if valid:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.is_admin = is_admin
                    st.success(f"Welcome {username.upper()}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        with col2:
            if st.button("Register", key="register_btn", help="Create account", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()
        return

    if not st.session_state.authenticated and st.session_state.page == "register":
        st.title("NFL Picks — Register")
        new_user = st.text_input("Choose username", key="reg_user")
        new_pw = st.text_input("Choose password",
                               type="password",
                               key="reg_pw")
        if st.button("Register new account", key="register_account_btn", help="Sign up", use_container_width=True):
            if not new_user or not new_pw:
                st.error("Username and password required.")
            else:
                add_user(new_user, new_pw, is_admin=False)
                st.success("Registered and logged in.")
                st.session_state.authenticated = True
                st.session_state.username = new_user
                st.session_state.is_admin = False
                st.session_state.page = "app"
                st.rerun()
        if st.button("Back to Login", key="back_login_btn", help="Return to login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()
        return

    # --- Post-login app ---
    if not st.session_state.authenticated:
        # fallback to login
        st.session_state.page = "login"
        st.rerun()
        return
    
    username = st.session_state.username
    admin_flag = is_admin_user(username)

    # side menu
    st.sidebar.title("Menu")
    if admin_flag:
        page = st.sidebar.radio(
            "Navigation",
            ["Fixtures", "Selections Summary", "Leaderboard", "Results"])
    else:
        page = st.sidebar.radio("Navigation", [
            "Fixtures", "My Picks", "Selections Summary", "Leaderboard",
            "Results"
        ])

    st.sidebar.write(
        f"Logged in as: **{username}** {'(admin)' if admin_flag else ''}")
    if st.sidebar.button("Logout"):
        for k in ["authenticated", "username", "is_admin", "page"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
        return

    # --- Admin: Fixtures ---
    if admin_flag and page == "Fixtures":
        st.header("Admin — Fixtures")
        if st.button("Fetch Fixtures from Odds API"):
            fixtures = fetch_fixtures_from_oddsapi()
            saved = save_fixtures(fixtures)
            st.success(
                f"Fetched {len(fixtures)} fixtures, saved/updated {saved} fixtures (duplicates overwritten)."
            )
        all_rows = load_all_fixtures()
        if all_rows:
            df_all = fixtures_to_dataframe(all_rows)
            st.subheader("All Fixtures in DB")
            st.dataframe(df_all, use_container_width=True)
        else:
            st.info("No fixtures in DB yet. Click 'Fetch Fixtures'.")

    # --- Admin: Selections Summary ---
    if admin_flag and page == "Selections Summary":
        st.header("Admin — Selections Summary (this week)")
        df_sum = selections_summary_for_week()
        if df_sum.empty:
            st.info("No selections for this week yet.")
        else:
            st.dataframe(df_sum, use_container_width=True)

    # --- Admin: Leaderboard ---
    if admin_flag and page == "Leaderboard":
        st.header("Admin — Leaderboard (cumulative)")
        df_lb = compute_leaderboard()
        if df_lb.empty:
            st.info("No leaderboard data yet (no results or picks).")
        else:
            # show Points and Played for admin
            st.dataframe(df_lb[["Player", "Points", "Played"]],
                         use_container_width=True)

    # --- Player: Fixtures ---
    if (not admin_flag) and page == "Fixtures":
        st.header("Fixtures (this week)")
        week_rows = fixtures_for_current_week()
        if not week_rows:
            st.info(
                "No fixtures loaded for this week. Ask an admin to fetch fixtures."
            )
        else:
            df = fixtures_to_dataframe(week_rows)
            st.dataframe(df[[
                "Home", "Away", "Kickoff (Dublin)", "Spread Home",
                "Spread Away"
            ]],
                         use_container_width=True)
            st.markdown(
                "Note: Matches that start in less than 1 hour are locked and cannot be picked."
            )

    # --- Player: My Picks ---
    if (not admin_flag) and page == "My Picks":
        st.header("My Picks — select up to 5 for the week")
        week_rows = fixtures_for_current_week()
        if not week_rows:
            st.info("No fixtures for the current week yet.")
        else:
            fid_to_row = {r[0]: r for r in week_rows}
            existing = get_user_picks(username)

            st.subheader("Existing saved picks (this week)")
            if existing:
                rows = []
                for fid, team in existing.items():
                    r = fid_to_row.get(fid)
                    if not r:
                        continue
                    home, away, kickoff, sh, sa = r[1], r[2], r[3], r[4], r[5]
                    spread_val = sh if team == home else sa
                    rows.append({
                        "Fixture": f"{home} vs {away}",
                        "Team": team,
                        "Spread": format_spread(spread_val)
                    })
                st.table(pd.DataFrame(rows))
            else:
                st.info("You have no saved picks for this week.")

            st.subheader("Select / change picks (not yet confirmed)")
            if "pending_selections" not in st.session_state:
                st.session_state.pending_selections = {}
            for fid, team in existing.items():
                if fid not in st.session_state.pending_selections:
                    st.session_state.pending_selections[fid] = team

            now_utc = datetime.now(UTC)

            # build matchkey maps
            id_to_matchkey = {}
            matchkey_to_ids = {}
            fid_to_kickoff = {}
            for r in week_rows:
                fid, home, away, kickoff, sh, sa = r
                key = tuple(
                    sorted([home.strip().lower(),
                            away.strip().lower()]))
                id_to_matchkey[fid] = key
                matchkey_to_ids.setdefault(key, []).append(fid)
                fid_to_kickoff[fid] = safe_parse(
                    kickoff) or datetime.max.replace(tzinfo=UTC)

            selected_matchkeys = set()
            for fid, team in st.session_state.pending_selections.items():
                mk = id_to_matchkey.get(fid)
                if mk:
                    selected_matchkeys.add(mk)

            for r in week_rows:
                fid, home, away, kickoff_iso, sh, sa = r
                kickoff_dt = safe_parse(kickoff_iso)
                locked = False
                if kickoff_dt and (kickoff_dt - now_utc < timedelta(hours=1)):
                    locked = True

                mk = id_to_matchkey.get(fid)
                already_selected_same_match = mk in selected_matchkeys and fid not in st.session_state.pending_selections

                col1, col2, col3 = st.columns([3, 3, 2])
                with col1:
                    st.markdown(
                        f"**{home}** ({format_spread(sh)}) vs **{away}** ({format_spread(sa)})"
                    )
                with col2:
                    kickoff_str = kickoff_dt.astimezone(DUBLIN_TZ).strftime(
                        "%a %d %b %H:%M") if kickoff_dt else "TBD"
                    st.markdown(f"Kickoff (Dublin): {kickoff_str}")
                with col3:
                    if locked:
                        st.markdown("**Locked**")
                    elif already_selected_same_match:
                        st.markdown(
                            "*Opponent locked (you selected the other team of this match)*"
                        )
                    else:
                        current = st.session_state.pending_selections.get(
                            fid, "No pick")
                        choice = st.selectbox(
                            "Pick", ["No pick", home, away],
                            index=(0 if current == "No pick" else
                                   (1 if current == home else 2)),
                            key=f"sel_{fid}")
                        if choice == "No pick":
                            if fid in st.session_state.pending_selections:
                                del st.session_state.pending_selections[fid]
                                sel_mk = id_to_matchkey.get(fid)
                                if sel_mk and sel_mk in selected_matchkeys:
                                    selected_matchkeys.discard(sel_mk)
                        else:
                            sel_mk = id_to_matchkey.get(fid)
                            if sel_mk in selected_matchkeys and fid not in st.session_state.pending_selections:
                                st.warning(
                                    "You already selected the opponent of this match; cannot pick both teams."
                                )
                            else:
                                st.session_state.pending_selections[
                                    fid] = choice
                                if sel_mk:
                                    selected_matchkeys.add(sel_mk)

            # Preview pending
            if st.session_state.pending_selections:
                st.subheader("Selected (preview, not confirmed)")
                preview_rows = []
                for fid, team in st.session_state.pending_selections.items():
                    r = fid_to_row.get(fid)
                    if not r:
                        continue
                    home, away, kickoff_iso, sh, sa = r[1], r[2], r[3], r[
                        4], r[5]
                    spread_val = sh if team == home else sa
                    preview_rows.append({
                        "Fixture": f"{home} vs {away}",
                        "Team": team,
                        "Spread": format_spread(spread_val)
                    })
                st.table(pd.DataFrame(preview_rows))

            existing_count = len(existing)
            pending_count = len(st.session_state.pending_selections)
            st.write(
                f"Existing picks: {existing_count}   |   Pending (to confirm): {pending_count}   | Max allowed: {MAX_PICKS_PER_WEEK}"
            )

            if st.button("Confirm Picks"):
                saved_count, err = save_user_picks_for_week(
                    username, st.session_state.pending_selections)
                if err:
                    st.error(err)
                else:
                    st.success(f"Saved {saved_count} picks for this week.")
                    st.session_state.pending_selections = {}
                    st.rerun()

    # --- Player: Selections Summary ---
    if (not admin_flag) and page == "Selections Summary":
        st.header("Selections Summary (this week)")
        df = selections_summary_for_week()
        if df.empty:
            st.info("No selections yet.")
        else:
            st.dataframe(df, use_container_width=True)

    # --- Player: Leaderboard ---
    if (not admin_flag) and page == "Leaderboard":
        st.header("Leaderboard (cumulative)")
        df_lb = compute_leaderboard()
        if df_lb.empty:
         st.info("No leaderboard yet (no results or picks).")
        else:
            # players don't need 'Played' if you prefer simpler view
            st.dataframe(df_lb[["Player", "Points"]], use_container_width=True)

    # --- Results (players see only published week) ---
    if page == "Results":
        st.header("Results — published week")
        if admin_flag:
            if st.button("Fetch results from ESPN",
                         key="admin_fetch_results"):
                saved, err = fetch_results_from_espn_for_week()
                if err:
                    st.error(err)
                else:
                    st.success(
                        f"Saved/updated {saved} result rows (matches found).")
            display_df, styler = build_results_table(for_admin=True)
            if display_df is None:
                st.info("No fixtures/picks for relevant week to show results.")
            else:
                st.write(
                    "Colors: green = win (3 pts), yellow = push (1 pt), red = loss (0 pts), white = not played"
                )
                if styler is None:
                    st.dataframe(display_df, use_container_width=True)
                else:
                    st.write(styler.to_html(), unsafe_allow_html=True)
        else:
            pub = get_published_week()
            if not pub:
                st.info(
                    "Results will be available once the admin updates them.")
            else:
                display_df, styler = build_results_table(for_admin=False)
                if display_df is None:
                    st.info(
                        "No fixtures/picks for the published week to show results."
                    )
                else:
                    st.write(
                        "Colors: green = win (3 pts), yellow = push (1 pt), red = loss (0 pt), white = not played"
                    )
                    if styler is None:
                        st.dataframe(display_df, use_container_width=True)
                    else:
                        st.write(styler.to_html(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
