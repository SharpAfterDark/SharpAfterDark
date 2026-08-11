# SharpAfterDark Machine v1 — MLB

Mobile-first analysis engine. Designed to live on your iPhone home screen.

## What it does

1. Pulls the day’s MLB schedule (free official API)
2. Snapshots multi-book odds with exact timestamp
3. Stores everything permanently so you can measure later
4. (Next) Calculates probability / edge / SAD Score → ranked board

No auto-posting. Engine first.

---

## Get it on your iPhone (free)

### 1. Deploy (one-time, free)

**Easiest option — Streamlit Community Cloud**

1. Create a free account at https://share.streamlit.io
2. Push this folder to a **private** GitHub repo
3. Click “New app” → select the repo → set main file to `app.py`
4. In **Advanced settings → Secrets** add:

```
ODDS_API_KEY = "your_key_here"
```

5. Deploy. You get a permanent URL like `https://sharpafterdark.streamlit.app`

**Alternative free hosts:** Railway, Render, or Fly.io (same idea).

### 2. Add to iPhone Home Screen

1. Open the app URL in **Safari** (must be Safari)
2. Tap the **Share** icon (square with upward arrow)
3. Scroll and tap **Add to Home Screen**
4. Name it **SharpAfterDark** → tap **Add**

You now have an icon. It opens full-screen with no browser bars.

### 3. Get a free Odds API key

Go to https://the-odds-api.com → sign up → copy the key.  
Paste it in the app’s Settings tab (or put it in Streamlit secrets as shown above).

---

## Local development

```bash
cd sharp_after_dark
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your ODDS_API_KEY

streamlit run app.py
```

---

## Project structure

```
sharp_after_dark/
├── app.py                 # Mobile-first Streamlit UI
├── requirements.txt
├── .env.example
├── utils/
│   ├── db.py              # Games, OddsSnapshots, Predictions, Results
│   ├── mlb_data.py        # Official MLB Stats API
│   └── odds_data.py       # The Odds API + timestamped snapshots
├── models/                # Future probability models
└── data/                  # SQLite database
```

---

## Next pieces

- Feature engineering (pitcher form, team splits, park factors)
- Baseline probability model
- Edge calculation + SAD Score ranking
- Results settlement + performance tracking
- Closing Line Value (CLV)

---

SharpAfterDark · Engine first
