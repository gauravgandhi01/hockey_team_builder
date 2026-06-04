# linecraft Agent Handoff

## Snapshot
`linecraft` is a FastAPI + vanilla JS single-page NHL lineup game built around historical franchise-and-decade draws.

This is no longer the original current-roster prototype. The shipped product is now:
- historical-only
- franchise-and-decade based
- backed by NHL historical team season stats
- cached aggressively in local SQLite plus in-memory hot caches
- branded as `linecraft`

As of the latest verification:
- tests: `36 passed`
- runtime entrypoint: `uvicorn app.main:app --reload`
- local cache DB: `storage/historical_cache.sqlite3`

## Current Product Behavior

### Core Game Loop
The user builds a fixed 6-slot lineup in this order:
1. `C`
2. `W`
3. `W`
4. `D`
5. `D`
6. `G`

Flow:
- user starts a run
- app draws a random valid `current franchise + decade` pair
- user can select any player from that franchise-decade pool whose natural slot still fits an open lineup slot
- after each pick, the next draw happens automatically
- after the final pick, the lineup is graded

### Draw Model
Supported decades:
- `1980s`
- `1990s`
- `2000s`
- `2010s`
- `2020s`

Only current NHL franchises are primary draw targets, but historical predecessor branding is resolved when the decade requires it.
Examples:
- `WPG + 2000s` can resolve to `ATL`
- `COL + 1980s` can resolve to `QUE`
- `CAR` can resolve to `HFD`
- `DAL` can resolve to `MNS`

The app presents the historical team identity as the primary draw label and logo, and shows modern franchise context as a secondary note when applicable.

### Rerolls
Normal mode uses two independent one-time rerolls handled in the frontend:
- `Reroll Team`: keeps the decade fixed and redraws only the franchise
- `Reroll Decade`: keeps the franchise fixed and redraws only the decade

Hard mode replaces those with a single shared one-time `Reroll Draw`, which redraws both the team and the decade at once.

The frontend enforces reroll usage. The backend does not independently enforce reroll budgets.

### Candidate Eligibility
A candidate is eligible only if:
- they are part of the aggregated regular-season franchise-decade pool
- they reached the minimum threshold of `100 GP` with that franchise in that decade
- their derived slot matches an open lineup slot
- they have not already been selected in the lineup

Primary position is inferred from the position where the player logged the most games in that franchise-decade pool:
- `C -> C`
- `L/R -> W`
- `D -> D`
- `G -> G`

### Candidate Ordering And Display
Normal mode candidates are currently sorted by:
1. decade `gamesPlayed` descending
2. slot sort order `C, W, D, G`
3. player name

Hard mode candidates are sorted alphabetically by player name on the server.

This is intentionally transparent. Hidden preview scores are not shown and do not drive ordering.

Normal mode candidate cards display:
- historical team abbreviation
- player position badge
- a coarse hidden-strength tier badge (`Tier 1` through `Tier 5`)
- role-specific decade stats
- awards / trophy badges, including a Stanley Cup badge when the player won with that exact team stint

Hard mode candidate cards intentionally hide pre-pick hinting:
- `offerStats` are omitted
- `ratingTier` is omitted
- award badges are omitted

Visible stats by role in normal mode:
- `C`: `P`, `A`, `G`, `SOG`
- `W`: `P`, `G`, `SOG`
- `D`: `P`, `A`, `SOG`, optionally `TOI`
- `G`: `W`, `SO`, `GAA`, `SV%`

### Tier System
The app now exposes a coarse tier bucket on candidate cards without revealing exact ratings.

Current tiers are percentile-based within each `decade + role` leaderboard:
- `Tier 1`: top `3%`
- `Tier 2`: next `7%`
- `Tier 3`: next `15%`
- `Tier 4`: next `25%`
- `Tier 5`: bottom `50%`

This is derived from the hidden role rating and exists only to give users directional signal without exposing exact scores.

## Branding And UI

### Brand
The site is branded as `linecraft`.
Current brand assets and text:
- logo file used by the app: `app/static/logo.png`
- transparent logo source was replaced from `xazvi-Photoroom.png`
- site footer includes:
  - `This site is not affiliated with the NHL.`
  - `Made by G`
- share card footer includes `linecraft.lol`

### Layout And Theme
The UI is currently:
- dark themed
- intentionally compacted for laptop and mobile
- mobile-optimized with internal scrolling for long candidate lists
- built entirely in `app/static/app.js` + `app/static/styles.css`

Important current UI details:
- `Start Over Run` is now a top-right hero chip, visually distinct from the informational chips
- the hero subtitle now explains grading more clearly
- the share card is the main end-state result artifact
- the results area no longer shows a duplicate score header above the share card
- the share-card score block is now the primary score presentation
- no export button exists anymore

### Shuffle Animation
The team/decade shuffle animation was refactored to stop flickering the lineup strip.
Current behavior:
- during shuffle, only the draw card is updated frame-by-frame
- the lineup strip is not fully re-rendered each frame
- shuffle uses team logos and decade pills
- the animation cadence eases instead of ticking at a flat interval

## Repository Layout
Key files:
- `app/main.py`: FastAPI app setup, lifespan, routes, service injection
- `app/constants.py`: slots, decades, scoring weights, curve constants, scoring version, logos
- `app/models.py`: request models
- `app/nhl_service.py`: core historical data pipeline, draw generation, grading
- `app/scoring.py`: weighted metric scoring, percentile logic, rating curves, grade/tier mapping
- `app/historical_store.py`: SQLite persistence layer
- `app/prewarm_historical.py`: manual cache prewarm entrypoint
- `app/templates/index.html`: only HTML template
- `app/static/app.js`: full frontend state machine and rendering
- `app/static/styles.css`: full styling
- `tests/test_api.py`: mocked integration tests
- `tests/test_scoring.py`: scoring and helper unit tests
- `storage/historical_cache.sqlite3`: local persisted cache, generated at runtime
- `nhl-api-docs/`: local reference docs, not used at runtime

## Runtime Stack
Backend:
- Python 3.13 in local development
- FastAPI
- Uvicorn
- httpx
- Jinja2
- sqlite3 from the stdlib

Frontend:
- server-rendered HTML shell
- vanilla JS
- vanilla CSS
- no bundler
- no npm tooling
- no TypeScript

## How To Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- `http://127.0.0.1:8000`

## Hidden Admin Dashboard
Access is intentionally unlinked and key-guarded.

Environment variables:
- `LINECRAFT_ADMIN_PATH`
- `LINECRAFT_ADMIN_KEY`

Example:
```bash
export LINECRAFT_ADMIN_KEY="your-secret-key"
export LINECRAFT_ADMIN_PATH="/_private_linecraft_admin"
uvicorn app.main:app --reload
```

Open:
- `http://127.0.0.1:8000/_private_linecraft_admin?key=your-secret-key`

Behavior:
- access can also be provided via `X-Linecraft-Admin-Key`
- missing or incorrect credentials return `404`
- the dashboard is read-only and meant for model inspection
- it currently shows role/decade distributions, top role tables, top overall tables, scoring version, and prewarm status

## How To Prewarm The Historical Cache
```bash
source .venv/bin/activate
python -m app.prewarm_historical
```

This fully materializes:
- franchise catalog
- draw pairs
- raw season stats
- team-decade pools
- decade-role leaderboards

## How To Test
```bash
source .venv/bin/activate
pytest -q
```

Current baseline:
- `36 passed`

## HTTP API

### `GET /`
Serves the single-page app.

### `POST /api/game/draw`
Request body:
```json
{
  "openSlots": ["C", "W", "W", "D", "D", "G"],
  "excludeCandidateKeys": [],
  "hardMode": false,
  "lockFranchiseAbbrev": "WSH",
  "lockDecade": "2000s",
  "excludePairKey": "WSH:1990s"
}
```

Notes:
- `lockFranchiseAbbrev` is used for decade rerolls
- `lockDecade` is used for team rerolls
- `excludePairKey` avoids redrawing the exact same franchise-decade pair

Response shape includes:
- `pairKey`
- `modernFranchise`
- `historicalTeam`
- `decade`
- `seasonRange`
- `availableSlots`
- `hardMode`
- `candidates[]`

Each candidate currently includes:
- `candidateKey`
- `playerId`
- `fullName`
- `headshot`
- `positionCode`
- `eligibleSlot`
- `eligibleSlotLabel`
- `historicalTeamAbbrev`
- `historicalTeamName`
- `historicalTeamLogo`
- `ratingTier`
- `offerStats`
- `awards`

Hard mode response differences:
- `offerStats` is `null`
- `ratingTier` is `null`
- `awards` is an empty list
- candidate ordering is alphabetical

### `POST /api/game/grade`
Request body:
```json
{
  "lineup": [
    {"slot": "C", "candidateKey": "..."},
    {"slot": "W", "candidateKey": "..."},
    {"slot": "W", "candidateKey": "..."},
    {"slot": "D", "candidateKey": "..."},
    {"slot": "D", "candidateKey": "..."},
    {"slot": "G", "candidateKey": "..."}
  ]
}
```

Response currently includes:
- `lineupBreakdown`
- `totalScore`
- `letterGrade`
- `projectedRecord`

Important nuance:
- `projectedRecord` is still returned by the API
- the UI no longer displays projected record


### `POST /api/game/best-lineup`
Request body:
```json
{
  "lineup": [
    {"slot": "C", "candidateKey": "..."},
    {"slot": "W", "candidateKey": "..."},
    {"slot": "W", "candidateKey": "..."},
    {"slot": "D", "candidateKey": "..."},
    {"slot": "D", "candidateKey": "..."},
    {"slot": "G", "candidateKey": "..."}
  ],
  "boards": [
    {"pairKey": "WSH:2000s", "candidateKeys": ["..."]}
  ]
}
```

Behavior:
- uses only the six accepted draw boards from the run
- chooses exactly one candidate from each board
- enforces the normal slot counts `C, W, W, D, D, G`
- enforces no duplicate `playerId` values across boards
- maximizes the hidden final displayed `score`, not `rawScore`

Response includes:
- `lineupBreakdown`
- `totalScore`
- `letterGrade`
- `projectedRecord`
- `currentTotalScore`
- `currentLetterGrade`
- `scoreDelta`

Each best-lineup breakdown row also includes `sourceDrawIndex` so the frontend can show which original draw board the optimal candidate came from.

## Backend Architecture

### `app/main.py`
Responsibilities:
- creates the FastAPI app
- creates or accepts an injected `NhlApiService`
- manages the shared `httpx.AsyncClient`
- mounts `/static`
- serves `/`
- exposes `/api/game/draw`, `/api/game/grade`, and `/api/game/best-lineup`
- exposes a hidden admin dashboard route guarded by an environment key
- optionally starts background prewarm on startup

Important note:
- Jinja `TemplateResponse` uses the current Starlette signature:
  - `TemplateResponse(request=..., name=..., context=...)`
- this fixed a real runtime bug and should not be reverted

### `app/models.py`
Current request models:
- `DrawRequest`
  - `openSlots`
  - `excludeCandidateKeys`
  - `hardMode`
  - `lockFranchiseAbbrev`
  - `lockDecade`
  - `excludePairKey`
- `GradeRequest`
  - `lineup: list[LineupItem]`
- `LineupItem`
  - `slot`
  - `candidateKey`

### `app/historical_store.py`
This is the persistent SQLite cache.

Tables:
- `meta`
- `franchise_catalog`
- `team_season_stats`
- `draw_pairs`
- `team_decade_pools`
- `decade_role_leaderboards`
- `award_details_cache`

Key design points:
- raw season payloads are persisted indefinitely
- derived caches are versioned by `SCORING_VERSION`
- schema version is tracked separately by `SCHEMA_VERSION`
- WAL mode and `synchronous=NORMAL` are enabled

### `app/nhl_service.py`
This is the core service and the most important file in the repo.

#### Data Sources
The service uses these NHL endpoints:
- `https://records.nhl.com/site/api/franchise`
- `https://records.nhl.com/site/api/franchise-season-results`
- `https://api-web.nhle.com/v1/club-stats/{team}/{season}/{gameType}`
- `https://records.nhl.com/site/api/award-details`
- `https://records.nhl.com/site/api/player-stanley-cup-wins`

It does not use the old active-roster endpoints anymore.

#### Franchise Catalog
`get_franchise_catalog()`:
- loads current franchises from the records API
- filters to franchises where `lastSeasonId` is `null`
- gathers regular-season franchise season rows
- stores season-by-season team-code history for each franchise

#### Draw Pair Generation
`get_draw_pairs()`:
- iterates current franchises
- iterates supported decades
- keeps only franchise/decade combinations with at least one season row
- derives the historical display team from the most common team code in that decade, tie-broken by latest season
- produces a stable `pairKey` like `WSH:2000s`
- persists the result to SQLite

Each pair contains:
- modern franchise identity
- historical display identity
- resolved team codes used in that decade
- season-by-season team rows
- a formatted start/end season range

#### Raw Team Season Stats
`get_team_season_stats()`:
- checks in-memory cache
- falls back to SQLite cache
- falls back to live NHL API fetch
- persists raw payload JSON to SQLite

#### Team-Decade Pool Construction
`get_team_decade_pool(pair_key)`:
- loads the relevant pair
- fetches each resolved team-season payload in that decade
- aggregates skaters by `playerId`
- aggregates goalies by `playerId`
- applies the `100 GP` minimum
- determines skater primary position by most games played
- generates `candidateKey = {pairKey}:{playerId}:{slot}`
- persists the derived pool to SQLite under the active `SCORING_VERSION`

Skater aggregate fields currently retained:
- `gamesPlayed`
- `goals`
- `assists`
- `points`
- `shots`
- `avgTimeOnIcePerGame`

Goalie aggregate fields currently retained:
- `gamesPlayed`
- `wins`
- `shutouts`
- `savePercentage`
- `goalsAgainstAverage`

#### TOI Tracking Compensation
This was a real bug area and matters.

Problem that existed:
- older skater seasons did not include `avgTimeOnIcePerGame`
- those missing seasons were effectively dragging decade TOI values toward zero
- this produced nonsense for older defensemen, for example Brian Leetch

Current fix:
- `SKATER_TOI_TRACKING_START_SEASON = 19971998`
- skater TOI is only weighted using seasons at or after that season when TOI exists
- pre-1997-98 missing seasons are not treated as zero
- pre-2000 defense scoring excludes TOI entirely to avoid partial-era bias

#### Decade Role Leaderboards
`get_decade_role_leaderboard(decade_start, role)`:
- gathers every eligible candidate from every pair in that decade for the requested role
- builds totals and rate metrics for each candidate
- scores them through `score_role_players()`
- persists the leaderboard to SQLite under the current `SCORING_VERSION`

#### Awards And Cup Graphics
The service enriches candidates with graphics-only accolade badges.

Tracked awards currently include:
- Hart / MVP
- Norris
- Vezina
- Art Ross
- Rocket Richard

Stanley Cup wins are also surfaced as a `🏆` badge, but only when the player won the Cup with the exact team stint being slotted. That match is derived by joining the player Cup-win feed against the candidate's `seasonTeams` entries by `seasonId + teamAbbrev`.

Awards are never part of ratings today. They are display-only.

#### Draw Generation
`get_random_draw(...)`:
- filters pairs by optional franchise/decade locks and optional excluded pair key
- excludes already-selected player IDs by parsing `candidateKey`
- checks whether each candidate still fits an open slot
- fetches role leaderboards for the eligible roles in that draw so tier labels can be computed
- adds `ratingTier` and award badges to each candidate in normal mode
- hides those hints in hard mode
- sorts display candidates by `gamesPlayed` in normal mode or alphabetically in hard mode
- returns the first pair with at least one valid candidate

#### Grading
`grade_lineup(...)` enforces:
- lineup length must match `SLOT_SEQUENCE`
- slot order must be exactly `C, W, W, D, D, G`
- no duplicate `candidateKey`
- no duplicate `playerId`
- each `candidateKey` must parse successfully
- submitted slot must match the slot encoded in the `candidateKey`
- draw pair must exist
- candidate must still exist in the current team-decade pool
- candidate must exist in the current decade-role leaderboard

Response breakdown rows currently include:
- `slot`
- `slotLabel`
- `candidateKey`
- `playerId`
- `fullName`
- `teamAbbrev`
- `teamName`
- `modernFranchiseAbbrev`
- `decade`
- `positionCode`
- `headshot`
- `score`
- `rawScore`
- `totalsScore`
- `rateScore`
- `metricPercentiles`
- `stats`
- `scorecardTotals`
- `awards`

Hard mode does not change grading output. It only hides hints during selection.

### `prewarm_missing()`
This method:
- initializes service metadata
- builds all pair pools
- builds all decade-role leaderboards
- writes `prewarm_complete = SCORING_VERSION` to `meta`

## Scoring Model
Implemented in `app/scoring.py`.

### High-Level Model
Scoring is position-relative and decade-relative.

Each player is compared against:
- players from the same role
- from the same decade

This is not a cross-era global model.

### Hybrid Score
Each player gets:
- `totalsScore`
- `rateScore`
- `rawScore = 0.70 * totalsScore + 0.30 * rateScore`
- `score = curved display/game rating from rawScore`

### Current Role Weights
Current `ROLE_CONFIG`:

`C`
- `points 0.40`
- `assists 0.20`
- `goals 0.15`
- `shots 0.15`

`W`
- `points 0.40`
- `goals 0.25`
- `shots 0.15`

`D`
- `points 0.25`
- `assists 0.20`
- `avgTimeOnIcePerGame 0.40`
- `shots 0.15`

`G`
- `savePercentage 0.40`
- `wins 0.20`
- `goalsAgainstAverageInverse 0.20`
- `shutouts 0.10`

Important current cleanup decisions:
- `plusMinus` is not considered anywhere anymore
- `gamesPlayed` is not an explicit scoring metric anymore
- goalie efficiency metrics are rate-only, not duplicated in totals
- defense TOI is rate-only and excluded entirely pre-2000

### Totals vs Rate Metrics
Per-game metrics are:
- `points`
- `assists`
- `goals`
- `shots`
- `wins`
- `shutouts`

Totals branch excludes:
- for `D`: `avgTimeOnIcePerGame`
- for `G`: `savePercentage`, `goalsAgainstAverageInverse`

Rate branch excludes:
- for pre-2000 `D`: `avgTimeOnIcePerGame`

### Cross-Position Calibration
A post-curve calibration layer now compresses very high defenseman and goalie ratings so they compare more reasonably against centers and wingers in lineup scoring.

Current post-curve factors above the `85` threshold:
- `C`: unchanged
- `W`: unchanged
- `D`: compressed by `0.88`
- `G`: compressed by `0.94`

This does not affect `rawScore` or within-role ordering. It only affects the final displayed/game `score` used in lineups and tiers.

### Rating Curves
There are now separate rating curves for skaters and goalies.

Skater/default curve:
- floor raw: `85.0`
- low: `40.0`
- mid: `70.0`
- high: `99.0`
- exponent: `1.6`

Goalie curve:
- floor raw: `80.0`
- low: `55.0`
- mid: `80.0`
- high: `99.0`
- exponent: `1.1`

Reason for the goalie-specific curve:
- the original curve produced overly harsh goalie dropoff
- for example, elite-but-not-very-top goalies were collapsing into the low `70s`
- the softer goalie curve now preserves separation without overpunishing very good goalies

### Letter Grades
Lineup `totalScore` is the average of the 6 displayed player scores.

Current bands:
- `A+ >= 95`
- `A >= 90`
- `A- >= 85`
- `B+ >= 80`
- `B >= 75`
- `B- >= 70`
- `C+ >= 65`
- `C >= 60`
- `C- >= 55`
- `D+ >= 50`
- `D >= 45`
- `D- >= 40`
- `F < 40`

## Frontend Architecture
All frontend behavior lives in `app/static/app.js`.

### State Model
Important client state includes:
- `lineup`
- `acceptedBoards`
- `currentIndex`
- `currentDraw`
- `result`
- `bestPossible`
- `bestPossibleVisible`
- `bestPossibleLoading`
- `loadingKind`
- `error`
- `shuffleFrame`
- `hardMode`
- `hardModeLocked`
- `rerollTeamUsed`
- `rerollDecadeUsed`
- `rerollDrawUsed`
- `candidateFilter`

### Key Frontend Behavior
- draws automatically after each non-final pick
- shuffling is visual only and delayed to feel game-like
- position filter chips (`All`, `C`, `W`, `D`, `G`) are client-side only
- candidate filtering resets to `ALL` after every new draw or reroll
- result rendering is now share-card-first
- post-run results can reveal the exact best possible lineup from the six accepted draw boards
- hard mode is selected before the first draw and locks for the rest of the run

### Candidate Card UX
Current cards show:
- player headshot
- team abbreviation
- coarse `Tier N` badge
- position pill
- player name
- historical team name
- visible role-specific stats

Hard mode cards only show:
- player headshot
- team abbreviation
- position pill
- player name
- historical team name

### Share Card UX
The final share card currently includes:
- linecraft logo
- combined decades used in the lineup
- cumulative `P`, `G`, `A` totals across the lineup
- one row per player with:
  - slot pill
  - player headshot
  - team logo
  - player/team/decade/position text
  - visible stats
  - per-player score
- bottom-right footer `linecraft.lol`

Important recent cleanup:
- the duplicate result header above the share card was removed
- the share card now owns the primary score presentation
- the numeric lineup score is emphasized more than the letter grade

### Mobile Behavior
The current UI has several mobile-specific optimizations:
- compressed hero
- horizontally scrollable lineup strip
- smaller lineup slots
- internal vertical scrolling in the candidate grid
- reduced share-card height
- denser candidate cards
- smaller chips and type

## Current Template / Copy Notes
`app/templates/index.html` currently contains:
- eyebrow: `Historical Franchise Mode`
- updated hero subtitle:
  - `Build a lineup from random NHL franchise-and-decade draws, then get graded by how each pick stacks up against players from the same decade at that position.`
- hero chips:
  - `6 picks`
  - `1980s to 2020s`
  - `Hard Mode`
  - `Start Over Run`
- footer disclaimer and credit

## Testing Surface

### `tests/test_api.py`
Covers:
- root render
- draw response shapes
- hard-mode draw hiding and alphabetical ordering
- persisted cache reuse across runs
- predecessor franchise resolution
- reroll lock behavior by filters
- invalid grading submissions
- cumulative scorecard totals
- draw candidate payloads including `ratingTier`
- hidden admin dashboard access
- Cup-badge team-stint matching
- best-lineup optimization from accepted boards

### `tests/test_scoring.py`
Covers:
- candidate key round-tripping
- slot mapping helpers
- season formatting
- percentile logic
- grade mapping
- projected record mapping
- rating curves for skaters and goalies
- tier mapping
- cross-position calibration
- totals/rate metric inclusion and exclusion
- TOI exclusion pre-2000
- hybrid role scoring

## Known Technical Debt / Caveats
- `README.md` is partially stale. It still mentions projected record as a visible product behavior even though the UI no longer shows it.
- API still returns `projectedRecord`, but frontend ignores it.
- Normal-mode and hard-mode reroll budgets are enforced in the frontend only.
- Candidate ordering is by `gamesPlayed` in normal mode and alphabetically in hard mode, not by rating, which is intentional but may not match user intuition.
- Historical logo URLs assume NHL asset availability by team abbreviation. If a predecessor logo disappears upstream, the UI may degrade visually.
- The app depends on external NHL APIs at runtime unless the relevant cache rows are already populated.
- The hidden admin route is key-guarded but intentionally lightweight; it is not a full auth system.
- There is no DB migration system, no deploy-specific config, and no analytics.

## Safe Places To Modify Common Features
- scoring weights / curves: `app/constants.py`, `app/scoring.py`
- historical aggregation rules: `app/nhl_service.py`
- draw payload shape: `app/nhl_service.py`, `app/models.py`, `app/static/app.js`, tests
- UI copy/layout: `app/templates/index.html`, `app/static/styles.css`, `app/static/app.js`
- persistence behavior: `app/historical_store.py`, `app/prewarm_historical.py`

## Current Version Markers
At time of this handoff:
- `SCHEMA_VERSION = historical-cache-v2`
- `SCORING_VERSION = historical-hybrid-70-30-v15`

Any scoring change that affects derived team-decade pools or leaderboards should usually bump `SCORING_VERSION` so stale SQLite-derived payloads are not reused.
