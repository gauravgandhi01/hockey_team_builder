from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.constants import SCHEMA_VERSION


class HistoricalCacheStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._initialize_schema()

    def _initialize_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS franchise_catalog (
                current_abbrev TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS team_season_stats (
                team_code TEXT NOT NULL,
                season TEXT NOT NULL,
                game_type INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (team_code, season, game_type)
            );
            CREATE TABLE IF NOT EXISTS draw_pairs (
                pair_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS team_decade_pools (
                pair_key TEXT PRIMARY KEY,
                scoring_version TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decade_role_leaderboards (
                decade_start INTEGER NOT NULL,
                role TEXT NOT NULL,
                scoring_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (decade_start, role, scoring_version)
            );
            """
        )
        cursor.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, value),
            )
            self._conn.commit()

    def load_franchise_catalog(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM franchise_catalog ORDER BY current_abbrev"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_franchise_catalog(self, entries: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM franchise_catalog")
            self._conn.executemany(
                "INSERT INTO franchise_catalog (current_abbrev, payload_json) VALUES (?, ?)",
                [(entry["currentAbbrev"], json.dumps(entry)) for entry in entries],
            )
            self._conn.commit()

    def get_team_season_stats(self, team_code: str, season: str, game_type: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                (
                    "SELECT payload_json FROM team_season_stats "
                    "WHERE team_code = ? AND season = ? AND game_type = ?"
                ),
                (team_code, season, game_type),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def set_team_season_stats(
        self,
        team_code: str,
        season: str,
        game_type: int,
        payload: dict[str, Any],
    ) -> None:
        with self._lock:
            self._conn.execute(
                (
                    "INSERT OR REPLACE INTO team_season_stats "
                    "(team_code, season, game_type, payload_json) VALUES (?, ?, ?, ?)"
                ),
                (team_code, season, game_type, json.dumps(payload)),
            )
            self._conn.commit()

    def load_draw_pairs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM draw_pairs ORDER BY pair_key"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_draw_pairs(self, pairs: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM draw_pairs")
            self._conn.executemany(
                "INSERT INTO draw_pairs (pair_key, payload_json) VALUES (?, ?)",
                [(pair["pairKey"], json.dumps(pair)) for pair in pairs],
            )
            self._conn.commit()

    def get_team_decade_pool(self, pair_key: str, scoring_version: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT scoring_version, payload_json FROM team_decade_pools WHERE pair_key = ?",
                (pair_key,),
            ).fetchone()
        if row is None or row["scoring_version"] != scoring_version:
            return None
        return json.loads(row["payload_json"])

    def set_team_decade_pool(self, pair_key: str, scoring_version: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                (
                    "INSERT OR REPLACE INTO team_decade_pools "
                    "(pair_key, scoring_version, payload_json) VALUES (?, ?, ?)"
                ),
                (pair_key, scoring_version, json.dumps(payload)),
            )
            self._conn.commit()

    def get_decade_role_leaderboard(
        self,
        decade_start: int,
        role: str,
        scoring_version: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                (
                    "SELECT payload_json FROM decade_role_leaderboards "
                    "WHERE decade_start = ? AND role = ? AND scoring_version = ?"
                ),
                (decade_start, role, scoring_version),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def set_decade_role_leaderboard(
        self,
        decade_start: int,
        role: str,
        scoring_version: str,
        payload: dict[str, Any],
    ) -> None:
        with self._lock:
            self._conn.execute(
                (
                    "INSERT OR REPLACE INTO decade_role_leaderboards "
                    "(decade_start, role, scoring_version, payload_json) VALUES (?, ?, ?, ?)"
                ),
                (decade_start, role, scoring_version, json.dumps(payload)),
            )
            self._conn.commit()
