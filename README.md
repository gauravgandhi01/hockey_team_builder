# NHL Builder

A FastAPI prototype of an NHL lineup builder based on historical franchise-and-decade draws.

## What It Does

- draws a random current NHL franchise and supported decade (`1980s` to `2020s`)
- resolves predecessor branding when a franchise changed cities or names
- lets you fill `C, W, W, D, D, G` with players from that franchise-decade pool
- grades the lineup against same-position players from the same decade
- returns both a letter grade and a projected `82-game` NHL record
- persists historical source data and computed aggregates to local SQLite for fast repeat runs

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Hidden Admin Dashboard

Set these env vars before starting the app:

```bash
export LINECRAFT_ADMIN_KEY="your-secret-key"
export LINECRAFT_ADMIN_PATH="/_private_linecraft_admin"
```

Then open:

```text
http://127.0.0.1:8000/_private_linecraft_admin?key=your-secret-key
```

The admin page is read-only and shows:
- decade/role rating distributions
- top players by decade and position
- top overall ratings for the selected decade

## Prewarm Historical Cache

```bash
source .venv/bin/activate
python -m app.prewarm_historical
```

This populates the local historical SQLite cache under `storage/`.

## Test

```bash
source .venv/bin/activate
pytest -q
```
