# NHL Builder Agent Handoff

## Project Summary
`nhl_builder` is a lightweight FastAPI web prototype for an NHL lineup-building game inspired by `82-0.com`.

The current product is a single-page web app with a Python backend and a vanilla JS/CSS frontend. It uses live NHL API data and has no database, authentication, persistence, or build step.

Current gameplay:
- The user builds a 5-slot lineup in this fixed order: `C`, `W`, `W`, `D`, `G`.
- Team selection is team-first, not slot-first.
- The user manually clicks a button to draw a random team.
- The user may choose any player from that team whose natural position still fits an open lineup slot.
- The user has exactly one reroll per run, only while a team is currently offered.
- After 5 picks, the lineup is graded against the active NHL player pool.

## Repository Layout
Top-level files and directories that matter:
- `app/main.py`: FastAPI app setup, lifespan management, route wiring.
- `app/nhl_service.py`: NHL API access, caching, candidate generation, leaderboard construction, lineup grading.
- `app/scoring.py`: percentile ranking, per-game normalization, weighted scoring, letter-grade mapping.
- `app/constants.py`: game constants, scoring weights, cache TTLs, game slot order, minimum games threshold.
- `app/models.py`: Pydantic request models.
- `app/templates/index.html`: single Jinja template.
- `app/static/app.js`: entire frontend state machine and rendering logic.
- `app/static/styles.css`: all styling and UI animation.
- `tests/test_api.py`: integration-style tests using a mocked NHL API transport.
- `tests/test_scoring.py`: unit tests for filtering and scoring behavior.
- `nhl-api-docs/`: local NHL API reference materials used during development. Runtime does not import from here.
- `README.md`: minimal run/test instructions.

## Runtime Stack
Backend:
- Python 3.13 in local development so far.
- FastAPI
- Uvicorn
- httpx
- Jinja2

Frontend:
- Server-rendered HTML shell via Jinja.
- No framework.
- All interaction is in `app/static/app.js`.
- No bundler, no TypeScript, no npm tooling.

## How To Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Then open `http://127.0.0.1:8000`.

## How To Test
```bash
source .venv/bin/activate
pytest -q
```
Current test status at last verification:
- `11 passed`

## Current Product Rules

### Lineup Structure
The lineup always contains exactly:
1. `C`
2. `W`
3. `W`
4. `D`
5. `G`

This order is enforced during grading.

### Team Draw Rules
- Draws are manual, triggered by the frontend button.
- The backend selects a random team from current NHL standings.
- The frontend handles the one-time reroll UX.
- Reroll is not enforced on the backend. It is a frontend-only product rule right now.

### Candidate Eligibility Rules
A player is offered only if all of these are true:
- They are on `v1/roster/{team}/current`.
- Their natural position maps to at least one open lineup slot:
  - `C` -> Center slot
  - `L` or `R` -> Winger slot
  - `D` -> Defenseman slot
  - `G` -> Goalie slot
- They have not already been selected in the current run.
- Their current-season featured stat block reports at least `20` games played.

This 20-game threshold is defined in `app/constants.py` as `MIN_GAMES_PLAYED = 20`.

### Candidate Sorting
Offered candidates are sorted by current-season raw `points` descending.
This is only for display ordering.
It is not the rating formula.

### Visible Card Stats
Offer cards show season totals, not per-game values:
- Skaters: `PTS`, `G`, `A`
- Goalies: `GAA`, `SV%`

### Rating Rules
The actual lineup grading uses percentile-based weighted composites across the active-player pool for each role.

Important nuance:
- Display ordering uses raw season `points`.
- Display card stats use raw totals.
- Rating normalization uses per-game values where appropriate.

## NHL Data Sources
The app uses live NHL endpoints from `https://api-web.nhle.com/v1`.

Primary endpoints in use:
- `v1/standings/now`
  - used to get current teams
  - also used to capture `teamLogo` if available
- `v1/roster/{team}/current`
  - used to get the current roster
- `v1/player/{playerId}/landing`
  - used to get `featuredStats.regularSeason.subSeason`

The local `nhl-api-docs/` folder is reference material only.
The app does not consume any generated artifacts from it at runtime.

## Backend Architecture

### `app/main.py`
Responsibilities:
- Creates the FastAPI app.
- Creates or injects an `NhlApiService`.
- Owns the shared `httpx.AsyncClient` lifecycle.
- Mounts `/static`.
- Serves `/` and the two JSON routes.

Routes:
- `GET /`
- `POST /api/game/slot`
- `POST /api/game/grade`

Important implementation note:
- The Jinja `TemplateResponse` call must use the current Starlette signature:
  - `TemplateResponse(request=..., name=..., context=...)`
- This was a real bug earlier and is worth preserving.

### `app/models.py`
Request models:
- `OfferRequest`
  - `availableSlots: list["C"|"W"|"D"|"G"]`
  - `excludePlayerIds: list[int]`
- `GradeRequest`
  - `lineup: list[LineupItem]`
- `LineupItem`
  - `slot`, `playerId`, `teamAbbrev`

### `app/cache.py`
Simple in-memory TTL cache.
Used only in-process.
No external store.

### `app/constants.py`
Key constants:
- `SLOT_SEQUENCE`
- `SLOT_LABELS`
- `ROLE_CONFIG`
- `GRADE_BANDS`
- `MIN_GAMES_PLAYED = 20`
- cache TTL values

### `app/nhl_service.py`
This is the core backend module.

Key responsibilities:
- load current teams
- cache teams, rosters, player landing payloads, and role leaderboards
- build candidate offers for a random team
- compute the global rating pool by role
- validate and grade submitted lineups

Key helper functions:
- `player_slot(player)`
  - maps NHL roster position to game slot
- `roster_players(roster)`
  - flattens forwards + defensemen + goalies
- `featured_stats_from_landing(landing)`
  - extracts `featuredStats.regularSeason.subSeason`
- `meets_games_threshold(stats)`
  - enforces 20 GP minimum
- `offer_stats_for_slot(slot, stats)`
  - trims stats for card display
- `team_logo(team_data, abbrev)`
  - uses `teamLogo` from standings or falls back to NHL asset URL

#### `get_random_team_offer(...)`
Input:
- `available_slots`
- `exclude_player_ids`

Behavior:
- loops through a randomized team order
- loads the team roster
- filters to players whose natural positions still fit an open slot
- fetches landing data for those candidates
- removes players below the minimum games threshold
- sorts by `seasonPoints` descending
- returns the first team that yields at least one valid candidate

Returned payload shape:
- `team`
  - `abbrev`
  - `name`
  - `logo`
- `availableSlots`
- `candidates[]`
  - `playerId`
  - `fullName`
  - `headshot`
  - `sweaterNumber`
  - `positionCode`
  - `teamAbbrev`
  - `teamName`
  - `teamLogo`
  - `eligibleSlot`
  - `eligibleSlotLabel`
  - `offerStats`
  - `hasCurrentSeasonStats`
  - `seasonPoints`

#### `get_role_leaderboards()`
Builds the rating pool for `C`, `W`, `D`, and `G`.

Flow:
- load all current teams
- load all current rosters
- group players by role
- fetch all landing payloads for those players
- exclude anyone below 20 GP
- normalize stats
- score each role pool via `score_role_players`
- cache the result for 15 minutes

#### `grade_lineup(...)`
Validation steps:
- lineup length must be exactly 5
- slot order must be `C, W, W, D, G`
- no duplicate player IDs
- selected player must still belong to the submitted team and slot
- selected player must still meet the 20-game minimum
- selected player must exist in the cached role leaderboard

Output:
- `lineupBreakdown`
- `totalScore`
- `letterGrade`

## Scoring System
Implemented in `app/scoring.py`.

### Percentile Logic
For each role:
- each metric is converted into a percentile rank among all eligible players in that role
- percentile uses average rank for ties
- weighted percentiles are summed into a `0-100` score

### Per-Game Normalization
The following counting metrics are normalized to per-game values before percentile scoring:
- `points`
- `assists`
- `goals`
- `shots`
- `plusMinus`
- `wins`
- `shutouts`

These metrics are not converted to per-game:
- `gamesPlayed`
- `savePctg`
- inverse `goalsAgainstAvg`

### Current Role Weights
Center:
- points 0.40
- assists 0.20
- goals 0.15
- shots 0.15
- gamesPlayed 0.10

Winger:
- points 0.40
- goals 0.25
- shots 0.15
- plusMinus 0.10
- gamesPlayed 0.10

Defenseman:
- points 0.35
- assists 0.20
- plusMinus 0.20
- shots 0.15
- gamesPlayed 0.10

Goalie:
- savePctg 0.40
- wins 0.20
- inverse GAA 0.20
- shutouts 0.10
- gamesPlayed 0.10

### Letter Grade Mapping
`GRADE_BANDS` currently maps:
- `A+` at `>= 95`
- down through `D-`
- `F` below `40`

## Frontend Architecture
All frontend behavior lives in `app/static/app.js`.

### Frontend State
Main `state` keys:
- `lineup`
- `currentIndex`
- `currentOffer`
- `result`
- `loadingKind`
- `error`
- `shuffleTeam`
- `rerollUsed`

### Frontend Flow
1. `startNewRun()` resets all state.
2. User clicks `Draw Opening Team`.
3. `drawTeamOffer()` starts a shuffle animation and calls `/api/game/slot`.
4. Offered candidates are displayed.
5. User selects a player.
6. The candidate is assigned to the first open matching slot.
7. User clicks `Draw Next Team` and repeats.
8. After 5 picks, `gradeLineup()` calls `/api/game/grade`.
9. Scorecard renders.

### Important Frontend Product Rules
- Reroll is frontend-enforced only.
- Reroll can be used once and only when a team is currently active.
- When there is no active team, the team panel is empty and the draw button is the primary action.
- Shuffle animation uses a static frontend pool of team names/logos while waiting for the backend response.

### Team Logos in Frontend
The shuffle animation currently uses a hardcoded `SHUFFLE_TEAM_POOL` with NHL asset URLs.
The actual offered team uses `team.logo` returned by the backend.

### Styling
Everything is in `app/static/styles.css`.

Current design priorities:
- compact laptop-friendly layout
- vanilla CSS only
- logo-based shuffle card
- responsive enough for mobile

## Testing Strategy

### Unit Tests
`tests/test_scoring.py` covers:
- slot filtering behavior
- percentile tie handling
- letter grade mapping
- missing goalie stats
- per-game normalization for counting metrics
- weighted role scoring

### Integration-Style Tests
`tests/test_api.py` uses `httpx.MockTransport` to fake NHL API responses.
It covers:
- root page rendering
- offer generation
- team logo propagation
- candidate sort order
- 20-game exclusion from offers
- lineup grading
- duplicate player rejection
- sub-threshold player rejection during grading

## Current Known Constraints / Technical Debt

### Backend / Data
- No persistence.
- No auth.
- No leaderboard/history.
- No server-side session or anti-cheat logic.
- Reroll count is not validated server-side.
- Candidate generation still requires multiple live NHL API calls per team draw because player landing data is fetched for all eligible team candidates.
- First grade request may be relatively expensive because it constructs cached role leaderboards across the league.

### Frontend
- Vanilla JS rendering is manageable now, but state transitions are becoming more complex.
- There is no dedicated frontend test suite.
- The frontend assumes backend payload shapes exactly; no versioning layer exists.

### Product / Data Semantics
- “Played at least 20 games for the team this season” is approximated by the player landing `featuredStats.regularSeason.subSeason.gamesPlayed` from the current team context.
- If the NHL API changes shape, candidate filtering and scoring can silently drift.
- Offer card display stats remain totals even though ratings use per-game normalization.

## Useful Upgrade Directions
High-value next improvements another agent could take on:
- Add server-side reroll/session validation.
- Add seeded daily challenge mode.
- Add local or backend persistence for game history.
- Add explanations of why a player graded well or poorly using metric percentiles.
- Add loading/error retry UX for NHL API failures.
- Add frontend tests.
- Add precomputed/cached league leaderboards on startup or background refresh to reduce first-grade latency.
- Add more nuanced scoring metrics, especially for defensemen and goalies.
- Add filters or alternate modes for historical players if that becomes a requirement.

## Files Most Likely To Change For Common Tasks
If the next agent needs to:
- change game rules: `app/constants.py`, `app/nhl_service.py`, `app/static/app.js`
- change scoring: `app/constants.py`, `app/scoring.py`, `app/nhl_service.py`, `tests/test_scoring.py`
- change candidate eligibility: `app/nhl_service.py`, `tests/test_api.py`
- change UI flow: `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css`
- change API contracts: `app/models.py`, `app/main.py`, `app/nhl_service.py`, `tests/test_api.py`

## Last Verified State
Last locally verified commands:
```bash
source .venv/bin/activate
pytest -q
```
Result:
- `11 passed`

A live API smoke test also succeeded after the 20-game threshold update, returning a real team offer with valid logo data and points-sorted candidates.
