# 🏈 NFL Picks App

A full-featured **NFL weekly picks web app** built with [Streamlit](https://streamlit.io/) and SQLite.  
It allows players to log in, select up to 5 teams per week (Thu–Tue), and automatically tracks results, points, and leaderboards.

---

## 🚀 Features

### 👥 Authentication
- Secure login/register (SHA256-hashed passwords)
- Default **admin** user:  
  - **Username:** `admin`  
  - **Password:** `admin123`

### 🕒 Active Window (Weekly Picks)
- Admin defines a weekly window **Thursday → next Tuesday (Dublin time)**  
- Only fixtures within that period are available for picks
- Matches lock automatically **2 hours before kickoff**

### 🧾 Picks Management
- Each player can pick up to **5 teams per week**
- Picks are **append-only** — once confirmed, they can’t be changed
- Prevents duplicate or conflicting team selections

### 🏆 Leaderboard
- Auto-calculated points system:
  - ✅ **Win:** 3 pts  
  - ⚖️ **Push (tie vs spread):** 1 pt  
  - ❌ **Loss:** 0 pts
- **Cumulative** across all played weeks

### 📊 Admin Dashboard
- Fetches fixtures from [The Odds API](https://the-odds-api.com/)
- Fetches scores from ESPN’s public scoreboard
- Publishes weekly results to players
- Shows selection summaries and leaderboards

---

## 🧩 Tech Stack

| Layer | Technology |
|-------|-------------|
| UI | [Streamlit](https://streamlit.io/) |
| Database | SQLite |
| Data APIs | The Odds API, ESPN Scoreboard |
| Language | Python 3.9+ |
| Auth | SHA256 password hashing |

---

## ⚙️ Installation

### 1️⃣ Clone the repo
```bash
git clone https://github.com/YOUR-USERNAME/NFL-Picks.git
cd NFL-Picks
