# PocketSmart AI – Your Smart Budget & Recommendation Assistant

A FastAPI + Gemini web app that turns a budget into personalised recommendations for
**Home Interiors**, **Party Planning** and **Jewelry** (with optional outfit-image analysis).

## Project structure
```
pocketsmart-ai/
├── main.py                    # FastAPI app: startup, CORS, static files, error handlers, uvicorn entry
├── requirements.txt
├── .env.example               # copy to .env and add your Gemini key
├── app/
│   ├── config.py              # settings from .env
│   ├── database.py            # SQLite (users, recommendations/history)
│   ├── security.py            # bcrypt passwords, JWT, auth dependencies
│   ├── schemas.py             # Pydantic input models + validation
│   ├── templating.py          # Jinja2 setup + filters (₹ formatting, dates)
│   ├── routes/
│   │   ├── auth.py            # /register /login /logout /token /session-info /session-data
│   │   ├── planners.py        # /generate-home /generate-party /generate-jewelry
│   │   └── pages.py           # HTML pages, /history, /recommendations-details
│   └── services/
│       ├── gemini_utils.py    # prompts, Gemini call, JSON parsing, budget checks, fallback
│       ├── catalog.py         # platform links + rule-based fallback recommendations
│       └── images.py          # safe outfit-image upload handling
├── templates/                 # index, register, login, dashboard, home/party/jewelry planners,
│                              # recommendation (results), history, error
├── static/{css,js,uploads}/
├── tests/                     # pytest suite (no real API key needed)
└── scripts/test_gemini.py     # check your Gemini key (text + image)
```

## Setup (VS Code, Windows / macOS / Linux)
1. Install **Python 3.10+** and **VS Code** (with the *Python* extension).
2. **File → Open Folder…** → choose `pocketsmart-ai`.
3. Open a terminal in VS Code (**Terminal → New Terminal**) and create a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
   (If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.)
4. Install dependencies: `pip install -r requirements.txt`
5. Create your config: copy `.env.example` to `.env` (Windows: `copy .env.example .env`), then edit it:
   - `GEMINI_API_KEY` → get a free key at https://aistudio.google.com/apikey
   - `SECRET_KEY` → run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output
6. In VS Code press **Ctrl+Shift+P → Python: Select Interpreter → the `venv` one**.

## Run
```
python main.py
```
(or `uvicorn main:app --reload`, or press **F5** – a launch config is included.)
Open **http://127.0.0.1:8000** · API docs: **http://127.0.0.1:8000/docs**

No API key? The app still works and shows built-in sample recommendations (marked as such).

## Test
```
python scripts/test_gemini.py              # verifies your key (text)
python scripts/test_gemini.py outfit.jpg   # also verifies image + text
pytest -v                                  # full automated test suite
```
Manual check: register → sign in → run each planner → open History.

## Troubleshooting
| Problem | Fix |
|---|---|
| `404 … model is no longer available` | Model names change. Set `GEMINI_MODEL` in `.env` to a current one from https://ai.google.dev/gemini-api/docs/models |
| Sample data shown instead of AI | Key missing/invalid, quota hit, or model name outdated – check the terminal log |
| `ModuleNotFoundError` | Activate the venv and run `pip install -r requirements.txt` |
| Port 8000 busy | Set `PORT=8001` in `.env` and add it to `CORS_ORIGINS` |
| Logged out after each restart | `SECRET_KEY` not set in `.env` |
