# 🏈 NFL Picks App

A web application built with [Streamlit](https://streamlit.io) that lets users register, log in, and make weekly NFL picks.
Admins can fetch new fixtures from [OddsAPI](https://the-odds-api.com) and update results after games are played.

---

## ✨ Features

* 🔑 **User Authentication**

  * Register & log in with a username and password
  * Case-insensitive usernames
  * Passwords securely stored using hashing

* 📅 **NFL Fixtures & Results**

  * Admins can fetch the latest fixtures from OddsAPI
  * Display fixtures and results for the current week
  * Update results after games finish

* 👑 **Admin Features**

  * Manage fixtures and results
  * Control updates before the next week starts

* 🎨 **Custom Styling**

  * Styled login and register pages
  * NFL-themed header image

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/nfl-picks.git
cd nfl-picks
```

### 2. Install dependencies

It’s best to use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # On Mac/Linux
.venv\Scripts\activate      # On Windows

pip install -r requirements.txt
```

### 3. Add your OddsAPI key

Create a `.streamlit/secrets.toml` file (not committed to GitHub):

```toml
ODDS_API_KEY = "your_oddsapi_key_here"
```

### 4. Run the app

```bash
streamlit run nfl_picks.py
```

Open your browser at [http://localhost:8501](http://localhost:8501).

---

## 🛠️ Project Structure

```
.
├── nfl_picks.py            # Main Streamlit app
├── requirements.txt        # Dependencies
├── .streamlit/
│   └── secrets.toml        # API key (local only)
└── README.md               # This file
```

---

## 🔒 Security Notes

* Do **not** hardcode your OddsAPI key into the code. Use `st.secrets` as shown above.
* Passwords are stored hashed — not plain text.
* Usernames are case-insensitive.

---

## 📌 Roadmap

* [ ] Add leaderboards
* [ ] Allow weekly pick submissions
* [ ] Export results to CSV
* [ ] Dark mode styling

---

## 🤝 Contributing

1. Fork this repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add feature'`)
4. Push the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📜 License

MIT License — feel free to use and adapt.
