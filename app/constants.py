from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DEFAULT_DB_PATH = STORAGE_DIR / "historical_cache.sqlite3"

BASE_WEB_URL = "https://api-web.nhle.com/v1"
BASE_RECORDS_URL = "https://records.nhl.com/site/api"
SUPPORTED_GAME_TYPE = 2

SLOT_SEQUENCE = ["C", "W", "W", "D", "D", "G"]
SLOT_SORT_ORDER = {slot: index for index, slot in enumerate(["C", "W", "D", "G"])}
SLOT_LABELS = {
    "C": "Center",
    "W": "Winger",
    "D": "Defenseman",
    "G": "Goalie",
}

SUPPORTED_DECADES = [1980, 1990, 2000, 2010, 2020]
DECADE_LABELS = {start: f"{start}s" for start in SUPPORTED_DECADES}
DECADE_START_BY_LABEL = {label: start for start, label in DECADE_LABELS.items()}
SKATER_TOI_TRACKING_START_SEASON = 19971998

ROLE_CONFIG = {
    "C": {
        "eligible_positions": {"C"},
        "weights": {
            "points": 0.40,
            "assists": 0.20,
            "goals": 0.15,
            "shots": 0.15,
        },
    },
    "W": {
        "eligible_positions": {"L", "R"},
        "weights": {
            "points": 0.40,
            "goals": 0.25,
            "shots": 0.15,
        },
    },
    "D": {
        "eligible_positions": {"D"},
        "weights": {
            "points": 0.25,
            "assists": 0.20,
            "avgTimeOnIcePerGame": 0.40,
            "shots": 0.15,
        },
    },
    "G": {
        "eligible_positions": {"G"},
        "weights": {
            "savePercentage": 0.40,
            "wins": 0.20,
            "goalsAgainstAverageInverse": 0.20,
            "shutouts": 0.10,
        },
    },
}

GRADE_BANDS = [
    (95.0, "A+"),
    (90.0, "A"),
    (85.0, "A-"),
    (80.0, "B+"),
    (75.0, "B"),
    (70.0, "B-"),
    (65.0, "C+"),
    (60.0, "C"),
    (55.0, "C-"),
    (50.0, "D+"),
    (45.0, "D"),
    (40.0, "D-"),
    (0.0, "F"),
]

RATING_TIER_BANDS = [
    (95.0, 1),
    (90.0, 2),
    (84.0, 3),
    (76.0, 4),
    (0.0, 5),
]

MIN_DECADE_GAMES = 100
HYBRID_TOTALS_WEIGHT = 0.70
HYBRID_RATES_WEIGHT = 0.30
RATING_CURVE_FLOOR_RAW = 85.0
RATING_CURVE_LOW = 40.0
RATING_CURVE_MID = 70.0
RATING_CURVE_HIGH = 99.0
RATING_CURVE_EXPONENT = 1.6
GOALIE_RATING_CURVE_FLOOR_RAW = 80.0
GOALIE_RATING_CURVE_LOW = 55.0
GOALIE_RATING_CURVE_MID = 80.0
GOALIE_RATING_CURVE_HIGH = 99.0
GOALIE_RATING_CURVE_EXPONENT = 1.1
PROJECTED_OTL = 8
SCHEMA_VERSION = "historical-cache-v1"
SCORING_VERSION = "historical-hybrid-70-30-v10"
LOGO_URL_TEMPLATE = "https://assets.nhle.com/logos/nhl/svg/{abbrev}_light.svg"
HEADSHOT_FALLBACK_TEMPLATE = "https://assets.nhle.com/mugs/nhl/{season}/{abbrev}/{player_id}.png"
