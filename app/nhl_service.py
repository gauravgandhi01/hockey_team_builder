from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.constants import (
    AWARD_TROPHIES,
    BASE_RECORDS_URL,
    BASE_WEB_URL,
    DECADE_START_BY_LABEL,
    DECADE_LABELS,
    DEFAULT_DB_PATH,
    HEADSHOT_FALLBACK_TEMPLATE,
    LOGO_URL_TEMPLATE,
    MIN_DECADE_GAMES,
    SCORING_VERSION,
    SKATER_FACEOFF_TRACKING_START_SEASON,
    SKATER_TOI_TRACKING_START_SEASON,
    SLOT_LABELS,
    SLOT_SEQUENCE,
    SLOT_SORT_ORDER,
    STANLEY_CUP_BADGE,
    TRACKED_AWARD_TROPHY_IDS,
    SUPPORTED_DECADES,
    SUPPORTED_GAME_TYPE,
)
from app.historical_store import HistoricalCacheStore
from app.scoring import (
    map_letter_grade,
    project_record,
    rate_metrics,
    score_role_players,
    totals_metrics,
)

PRIMARY_POSITION_ORDER = {"C": 0, "L": 1, "R": 2, "D": 3, "G": 4}
ROLE_ORDER = ["C", "W", "D", "G"]
AWARD_CACHE_KEY = "tracked-awards-v2"
CUP_WINS_CACHE_KEY = "stanley-cup-wins-v1"
ADMIN_SCORE_BUCKETS = [
    (95.0, "95+"),
    (90.0, "90-94.9"),
    (85.0, "85-89.9"),
    (80.0, "80-84.9"),
    (70.0, "70-79.9"),
    (0.0, "<70"),
]


def summarize_draw_provenance(pool_source: str, leaderboard_sources: dict[str, str]) -> dict[str, Any]:
    sources = [pool_source, *leaderboard_sources.values()]
    if "fresh" in sources:
        return {
            "kind": "fresh",
            "label": "Built fresh",
            "message": "Built this draw from live NHL history. Next time it should load faster.",
            "poolSource": pool_source,
            "leaderboardSources": leaderboard_sources,
        }
    if "sqlite" in sources:
        return {
            "kind": "sqlite",
            "label": "Disk cache",
            "message": "Loaded this draw from local disk cache.",
            "poolSource": pool_source,
            "leaderboardSources": leaderboard_sources,
        }
    return {
        "kind": "memory",
        "label": "Hot cache",
        "message": "Loaded this draw from in-memory cache.",
        "poolSource": pool_source,
        "leaderboardSources": leaderboard_sources,
    }


def logo_url(abbrev: str) -> str:
    return LOGO_URL_TEMPLATE.format(abbrev=abbrev)


def season_start_year(season_id: int | str) -> int:
    season_str = str(season_id)
    return int(season_str[:4])


def format_season_display(season_id: int | str) -> str:
    season_str = str(season_id)
    return f"{season_str[:4]}-{season_str[6:8]}"


def player_full_name(player: dict[str, Any]) -> str:
    return f"{player['firstName']['default']} {player['lastName']['default']}"


def slot_for_position_code(position_code: str | None) -> str | None:
    if position_code == "C":
        return "C"
    if position_code in {"L", "R"}:
        return "W"
    if position_code == "D":
        return "D"
    if position_code == "G":
        return "G"
    return None


def primary_position_code(position_games: dict[str, int]) -> str | None:
    if not position_games:
        return None
    return max(
        position_games.items(),
        key=lambda item: (item[1], -PRIMARY_POSITION_ORDER.get(item[0], 99)),
    )[0]


def make_candidate_key(pair_key: str, player_id: int, slot: str) -> str:
    return f"{pair_key}:{player_id}:{slot}"


def parse_candidate_key(candidate_key: str) -> tuple[str, int, str] | None:
    try:
        pair_key, player_id, slot = candidate_key.rsplit(":", 2)
    except ValueError:
        return None
    if slot not in SLOT_LABELS:
        return None
    try:
        return pair_key, int(player_id), slot
    except ValueError:
        return None


def decade_offer_stats(candidate: dict[str, Any]) -> dict[str, Any]:
    stats = candidate["stats"]
    slot = candidate["eligibleSlot"]
    if slot in {"C", "W"}:
        return {
            "points": stats.get("points", 0),
            "goals": stats.get("goals", 0),
            "assists": stats.get("assists", 0),
        }
    if slot == "D":
        offer = {
            "points": stats.get("points", 0),
        }
        if stats.get("avgTimeOnIcePerGame") is not None:
            offer["avgTimeOnIcePerGame"] = stats.get("avgTimeOnIcePerGame")
        return offer
    return {
        "wins": stats.get("wins", 0),
        "savePercentage": stats.get("savePercentage"),
    }


def scorecard_totals(candidate: dict[str, Any]) -> dict[str, int]:
    stats = candidate["stats"]
    return {
        "points": int(stats.get("points", 0) or 0),
        "goals": int(stats.get("goals", 0) or 0),
        "assists": int(stats.get("assists", 0) or 0),
    }


class NhlApiService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        rng: random.Random | None = None,
        store_path: Path | None = None,
    ):
        self.client = client
        self.rng = rng or random.Random()
        self.store = HistoricalCacheStore(store_path or DEFAULT_DB_PATH)
        self._init_lock = asyncio.Lock()
        self._pair_locks: dict[str, asyncio.Lock] = {}
        self._leaderboard_locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._franchise_catalog: list[dict[str, Any]] | None = None
        self._franchise_by_abbrev: dict[str, dict[str, Any]] = {}
        self._draw_pairs: list[dict[str, Any]] | None = None
        self._draw_pair_by_key: dict[str, dict[str, Any]] = {}
        self._season_stats_cache: dict[tuple[str, str, int], dict[str, Any]] = {}
        self._pair_pool_cache: dict[str, dict[str, Any]] = {}
        self._leaderboard_cache: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
        self._award_details: list[dict[str, Any]] | None = None
        self._award_index: dict[tuple[int, int, int], list[dict[str, Any]]] | None = None
        self._cup_wins: list[dict[str, Any]] | None = None
        self._cup_win_index: dict[int, set[tuple[int, str]]] | None = None
        self._closed = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.store.close()
        await self.client.aclose()

    async def initialize(self) -> None:
        async with self._init_lock:
            await self.get_franchise_catalog()
            await self.get_draw_pairs()

    async def _get_json(self, url: str) -> dict[str, Any]:
        response = await self.client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"NHL API request failed for {url}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"Invalid JSON received from {url}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail=f"Unexpected response shape from {url}")
        return payload

    async def _get_records_json(self, path: str) -> dict[str, Any]:
        return await self._get_json(f"{BASE_RECORDS_URL}/{path}")

    async def _get_web_json(self, path: str) -> dict[str, Any]:
        return await self._get_json(f"{BASE_WEB_URL}/{path}")

    def _cache_franchise_catalog(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._franchise_catalog = entries
        self._franchise_by_abbrev = {entry["currentAbbrev"]: entry for entry in entries}
        return entries

    def _cache_draw_pairs(self, pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(pairs, key=lambda pair: pair["pairKey"])
        self._draw_pairs = ordered
        self._draw_pair_by_key = {pair["pairKey"]: pair for pair in ordered}
        return ordered

    def _franchise_catalog_has_team_ids(self, entries: list[dict[str, Any]]) -> bool:
        return all(
            "teamId" in season_row
            for entry in entries
            for season_row in entry.get("seasonRows", [])
        )

    def _draw_pairs_have_team_ids(self, pairs: list[dict[str, Any]]) -> bool:
        return all(
            "teamId" in season_team
            for pair in pairs
            for season_team in pair.get("seasonTeams", [])
        )

    async def get_franchise_catalog(self) -> list[dict[str, Any]]:
        if self._franchise_catalog is not None:
            return self._franchise_catalog

        cached = self.store.load_franchise_catalog()
        if cached and self._franchise_catalog_has_team_ids(cached):
            return self._cache_franchise_catalog(cached)

        franchise_payload = await self._get_records_json("franchise")
        season_results_payload = await self._get_records_json("franchise-season-results")

        current_franchises = sorted(
            [entry for entry in franchise_payload.get("data", []) if entry.get("lastSeasonId") is None],
            key=lambda entry: entry["teamAbbrev"],
        )
        rows_by_franchise: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in season_results_payload.get("data", []):
            if row.get("gameTypeId") != SUPPORTED_GAME_TYPE:
                continue
            rows_by_franchise[int(row["franchiseId"])] .append(
                {
                    "seasonId": int(row["seasonId"]),
                    "teamId": int(row["teamId"]),
                    "triCode": row["triCode"],
                    "teamName": row["teamName"],
                }
            )

        catalog: list[dict[str, Any]] = []
        for franchise in current_franchises:
            season_rows = sorted(
                rows_by_franchise.get(int(franchise["id"]), []),
                key=lambda row: row["seasonId"],
            )
            catalog.append(
                {
                    "franchiseId": int(franchise["id"]),
                    "currentAbbrev": franchise["teamAbbrev"],
                    "fullName": franchise["fullName"],
                    "logo": logo_url(franchise["teamAbbrev"]),
                    "firstSeasonId": int(franchise["firstSeasonId"]),
                    "seasonRows": season_rows,
                }
            )

        self.store.save_franchise_catalog(catalog)
        return self._cache_franchise_catalog(catalog)

    async def get_draw_pairs(self) -> list[dict[str, Any]]:
        if self._draw_pairs is not None:
            return self._draw_pairs

        cached = self.store.load_draw_pairs()
        if cached and self._draw_pairs_have_team_ids(cached):
            return self._cache_draw_pairs(cached)

        catalog = await self.get_franchise_catalog()
        pairs: list[dict[str, Any]] = []
        for franchise in catalog:
            for decade_start in SUPPORTED_DECADES:
                decade_rows = [
                    row
                    for row in franchise["seasonRows"]
                    if decade_start <= season_start_year(row["seasonId"]) <= decade_start + 9
                ]
                if not decade_rows:
                    continue

                code_summary: dict[str, dict[str, Any]] = {}
                for row in decade_rows:
                    summary = code_summary.setdefault(
                        row["triCode"],
                        {
                            "count": 0,
                            "latestSeasonId": 0,
                            "teamName": row["teamName"],
                        },
                    )
                    summary["count"] += 1
                    if row["seasonId"] >= summary["latestSeasonId"]:
                        summary["latestSeasonId"] = row["seasonId"]
                        summary["teamName"] = row["teamName"]

                historical_abbrev, historical_info = max(
                    code_summary.items(),
                    key=lambda item: (item[1]["count"], item[1]["latestSeasonId"], item[0]),
                )
                pair_key = f"{franchise['currentAbbrev']}:{DECADE_LABELS[decade_start]}"
                season_teams = [
                    {
                        "season": str(row["seasonId"]),
                        "teamId": row["teamId"],
                        "teamCode": row["triCode"],
                        "teamName": row["teamName"],
                    }
                    for row in decade_rows
                ]
                resolved_team_codes = list(dict.fromkeys(row["teamCode"] for row in season_teams))
                pairs.append(
                    {
                        "pairKey": pair_key,
                        "franchiseId": franchise["franchiseId"],
                        "currentAbbrev": franchise["currentAbbrev"],
                        "decadeStart": decade_start,
                        "decadeLabel": DECADE_LABELS[decade_start],
                        "modernFranchise": {
                            "abbrev": franchise["currentAbbrev"],
                            "name": franchise["fullName"],
                            "logo": franchise["logo"],
                        },
                        "historicalTeam": {
                            "abbrev": historical_abbrev,
                            "name": historical_info["teamName"],
                            "logo": logo_url(historical_abbrev),
                            "secondaryNote": None
                            if historical_abbrev == franchise["currentAbbrev"]
                            else f"Modern franchise: {franchise['fullName']}",
                        },
                        "resolvedTeamCodes": resolved_team_codes,
                        "seasonTeams": season_teams,
                        "seasonRange": {
                            "start": format_season_display(season_teams[0]["season"]),
                            "end": format_season_display(season_teams[-1]["season"]),
                        },
                    }
                )

        self.store.save_draw_pairs(pairs)
        return self._cache_draw_pairs(pairs)

    async def get_award_details(self) -> list[dict[str, Any]]:
        if self._award_details is not None:
            return self._award_details

        cached = self.store.get_award_details(AWARD_CACHE_KEY)
        if cached is not None:
            self._award_details = cached
            return cached

        payload = await self._get_records_json("award-details")
        tracked_rows: list[dict[str, Any]] = []
        for row in payload.get("data", []):
            trophy_id = int(row.get("trophyId") or 0)
            if trophy_id not in TRACKED_AWARD_TROPHY_IDS:
                continue
            player_id = row.get("playerId")
            season_id = row.get("seasonId")
            team_id = row.get("teamId")
            if player_id is None or season_id is None or team_id is None:
                continue
            status = row.get("status")
            if status not in {"WINNER", "RUNNER_UP", "FINALIST"}:
                continue
            tracked_rows.append(
                {
                    "playerId": int(player_id),
                    "seasonId": int(season_id),
                    "teamId": int(team_id),
                    "trophyId": trophy_id,
                    "status": status,
                }
            )

        self.store.set_award_details(AWARD_CACHE_KEY, tracked_rows)
        self._award_details = tracked_rows
        return tracked_rows

    async def get_award_index(self) -> dict[tuple[int, int, int], list[dict[str, Any]]]:
        if self._award_index is not None:
            return self._award_index

        rows = await self.get_award_details()
        index: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            index[(row["playerId"], row["seasonId"], row["teamId"])].append(row)
        self._award_index = dict(index)
        return self._award_index

    async def get_cup_wins(self) -> list[dict[str, Any]]:
        if self._cup_wins is not None:
            return self._cup_wins

        cached = self.store.get_award_details(CUP_WINS_CACHE_KEY)
        if cached is not None:
            self._cup_wins = cached
            return cached

        payload = await self._get_records_json("player-stanley-cup-wins")
        rows: list[dict[str, Any]] = []
        for row in payload.get("data", []):
            player_id = row.get("playerId")
            seasons_won = row.get("seasonsWon")
            if player_id is None or not seasons_won:
                continue
            wins: list[dict[str, Any]] = []
            for entry in str(seasons_won).split(","):
                part = entry.strip()
                if not part or "(" not in part or ")" not in part:
                    continue
                season_label, team_part = part.split("(", 1)
                season_label = season_label.strip()
                team_abbrev = team_part.rstrip(")").strip()
                try:
                    start_year = int(season_label[:4])
                except ValueError:
                    continue
                season_id = int(f"{start_year}{start_year + 1}")
                wins.append({"seasonId": season_id, "teamAbbrev": team_abbrev})
            if not wins:
                continue
            rows.append({"playerId": int(player_id), "wins": wins})

        self.store.set_award_details(CUP_WINS_CACHE_KEY, rows)
        self._cup_wins = rows
        return rows

    async def get_cup_win_index(self) -> dict[int, set[tuple[int, str]]]:
        if self._cup_win_index is not None:
            return self._cup_win_index

        rows = await self.get_cup_wins()
        index: dict[int, set[tuple[int, str]]] = {}
        for row in rows:
            index[row["playerId"]] = {
                (int(win["seasonId"]), str(win["teamAbbrev"]))
                for win in row["wins"]
            }
        self._cup_win_index = index
        return index

    async def summarize_candidate_awards(
        self,
        player_id: int,
        season_teams: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        award_index = await self.get_award_index()
        cup_win_index = await self.get_cup_win_index()
        trophy_counts: dict[int, dict[str, int]] = defaultdict(lambda: {"winner": 0, "finalist": 0})
        cup_wins = 0
        for season_team in season_teams:
            stint_key = (player_id, int(season_team["season"]), int(season_team["teamId"]))
            for award in award_index.get(stint_key, []):
                trophy_config = AWARD_TROPHIES[award["trophyId"]]
                if award["status"] == "WINNER":
                    trophy_counts[award["trophyId"]]["winner"] += 1
                elif trophy_config["allowFinalists"]:
                    trophy_counts[award["trophyId"]]["finalist"] += 1
            if (int(season_team["season"]), season_team["teamCode"]) in cup_win_index.get(player_id, set()):
                cup_wins += 1

        awards: list[dict[str, Any]] = []
        if cup_wins > 0:
            awards.append(
                {
                    "key": STANLEY_CUP_BADGE["key"],
                    "label": STANLEY_CUP_BADGE["label"],
                    "level": "winner",
                    "count": cup_wins,
                }
            )
        for trophy_id, trophy_config in AWARD_TROPHIES.items():
            counts = trophy_counts.get(trophy_id)
            if counts is None:
                continue
            if counts["winner"] > 0:
                awards.append(
                    {
                        "key": trophy_config["key"],
                        "label": trophy_config["label"],
                        "level": "winner",
                        "count": counts["winner"],
                    }
                )
            elif counts["finalist"] > 0 and trophy_config["allowFinalists"]:
                awards.append(
                    {
                        "key": trophy_config["key"],
                        "label": trophy_config["label"],
                        "level": "finalist",
                        "count": counts["finalist"],
                    }
                )
        return awards

    async def get_draw_pair(self, pair_key: str) -> dict[str, Any] | None:
        pairs = await self.get_draw_pairs()
        if not pairs:
            return None
        return self._draw_pair_by_key.get(pair_key)

    def _pair_lock(self, pair_key: str) -> asyncio.Lock:
        lock = self._pair_locks.get(pair_key)
        if lock is None:
            lock = asyncio.Lock()
            self._pair_locks[pair_key] = lock
        return lock

    def _leaderboard_lock(self, decade_start: int, role: str) -> asyncio.Lock:
        key = (decade_start, role)
        lock = self._leaderboard_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._leaderboard_locks[key] = lock
        return lock

    def _team_decade_pool_source(self, pair_key: str) -> str:
        if pair_key in self._pair_pool_cache:
            return "memory"
        if self.store.get_team_decade_pool(pair_key, SCORING_VERSION) is not None:
            return "sqlite"
        return "fresh"

    def _leaderboard_source(self, decade_start: int, role: str) -> str:
        cache_key = (decade_start, role)
        if cache_key in self._leaderboard_cache:
            return "memory"
        if self.store.get_decade_role_leaderboard(decade_start, role, SCORING_VERSION) is not None:
            return "sqlite"
        return "fresh"

    async def get_team_season_stats(
        self,
        team_code: str,
        season: str,
        game_type: int = SUPPORTED_GAME_TYPE,
    ) -> dict[str, Any]:
        cache_key = (team_code, season, game_type)
        cached = self._season_stats_cache.get(cache_key)
        if cached is not None:
            return cached

        stored = self.store.get_team_season_stats(team_code, season, game_type)
        if stored is not None:
            self._season_stats_cache[cache_key] = stored
            return stored

        payload = await self._get_web_json(f"club-stats/{team_code}/{season}/{game_type}")
        self.store.set_team_season_stats(team_code, season, game_type, payload)
        self._season_stats_cache[cache_key] = payload
        return payload

    async def get_team_decade_pool(self, pair_key: str) -> dict[str, Any]:
        cached = self._pair_pool_cache.get(pair_key)
        if cached is not None:
            return cached

        stored = self.store.get_team_decade_pool(pair_key, SCORING_VERSION)
        if stored is not None:
            self._pair_pool_cache[pair_key] = stored
            return stored

        async with self._pair_lock(pair_key):
            cached = self._pair_pool_cache.get(pair_key)
            if cached is not None:
                return cached

            stored = self.store.get_team_decade_pool(pair_key, SCORING_VERSION)
            if stored is not None:
                self._pair_pool_cache[pair_key] = stored
                return stored

            pair = await self.get_draw_pair(pair_key)
            if pair is None:
                raise HTTPException(status_code=404, detail=f"Unknown draw pair {pair_key}.")

            skaters: dict[int, dict[str, Any]] = {}
            goalies: dict[int, dict[str, Any]] = {}
            for season_team in pair["seasonTeams"]:
                season = season_team["season"]
                team_code = season_team["teamCode"]
                stats = await self.get_team_season_stats(team_code, season)
                for player in stats.get("skaters", []):
                    player_id = int(player["playerId"])
                    aggregate = skaters.setdefault(
                        player_id,
                        {
                            "playerId": player_id,
                            "fullName": player_full_name(player),
                            "headshot": player.get("headshot")
                            or HEADSHOT_FALLBACK_TEMPLATE.format(
                                season=season,
                                abbrev=team_code,
                                player_id=player_id,
                            ),
                            "positionGames": defaultdict(int),
                            "stats": {
                                "gamesPlayed": 0,
                                "goals": 0,
                                "assists": 0,
                                "points": 0,
                                "shots": 0,
                                "avgTimeOnIcePerGameWeighted": 0.0,
                                "avgTimeOnIcePerGameTrackedGames": 0,
                                "faceoffWinPctgWeighted": 0.0,
                                "faceoffWinPctgTrackedGames": 0,
                            },
                        },
                    )
                    games_played = int(player.get("gamesPlayed") or 0)
                    aggregate["positionGames"][player.get("positionCode", "")] += games_played
                    for metric in ("gamesPlayed", "goals", "assists", "points", "shots"):
                        aggregate["stats"][metric] += float(player.get(metric) or 0)
                    avg_toi = player.get("avgTimeOnIcePerGame")
                    if (
                        int(season) >= SKATER_TOI_TRACKING_START_SEASON
                        and avg_toi not in (None, "")
                    ):
                        aggregate["stats"]["avgTimeOnIcePerGameWeighted"] += float(avg_toi) * games_played
                        aggregate["stats"]["avgTimeOnIcePerGameTrackedGames"] += games_played
                    faceoff_win_pctg = player.get("faceoffWinPctg")
                    if (
                        int(season) >= SKATER_FACEOFF_TRACKING_START_SEASON
                        and faceoff_win_pctg not in (None, "")
                    ):
                        aggregate["stats"]["faceoffWinPctgWeighted"] += float(faceoff_win_pctg) * games_played
                        aggregate["stats"]["faceoffWinPctgTrackedGames"] += games_played

                for player in stats.get("goalies", []):
                    player_id = int(player["playerId"])
                    aggregate = goalies.setdefault(
                        player_id,
                        {
                            "playerId": player_id,
                            "fullName": player_full_name(player),
                            "headshot": player.get("headshot")
                            or HEADSHOT_FALLBACK_TEMPLATE.format(
                                season=season,
                                abbrev=team_code,
                                player_id=player_id,
                            ),
                            "stats": {
                                "gamesPlayed": 0,
                                "wins": 0,
                                "goalsAgainst": 0,
                                "shotsAgainst": 0,
                                "saves": 0,
                                "shutouts": 0,
                                "timeOnIce": 0,
                            },
                        },
                    )
                    for metric in aggregate["stats"]:
                        aggregate["stats"][metric] += float(player.get(metric) or 0)

            candidates: list[dict[str, Any]] = []
            for aggregate in skaters.values():
                if aggregate["stats"]["gamesPlayed"] < MIN_DECADE_GAMES:
                    continue
                position_code = primary_position_code(dict(aggregate["positionGames"]))
                slot = slot_for_position_code(position_code)
                if slot is None:
                    continue
                awards = await self.summarize_candidate_awards(aggregate["playerId"], pair["seasonTeams"])
                games_played = aggregate["stats"]["gamesPlayed"]
                stats = {
                    "gamesPlayed": int(games_played),
                    "goals": int(aggregate["stats"]["goals"]),
                    "assists": int(aggregate["stats"]["assists"]),
                    "points": int(aggregate["stats"]["points"]),
                    "shots": int(aggregate["stats"]["shots"]),
                    "avgTimeOnIcePerGame": round(
                        aggregate["stats"]["avgTimeOnIcePerGameWeighted"]
                        / aggregate["stats"]["avgTimeOnIcePerGameTrackedGames"],
                        3,
                    )
                    if aggregate["stats"]["avgTimeOnIcePerGameTrackedGames"]
                    else None,
                    "faceoffWinPctg": round(
                        aggregate["stats"]["faceoffWinPctgWeighted"]
                        / aggregate["stats"]["faceoffWinPctgTrackedGames"],
                        6,
                    )
                    if aggregate["stats"]["faceoffWinPctgTrackedGames"]
                    else None,
                }
                candidate = {
                    "candidateKey": make_candidate_key(pair_key, aggregate["playerId"], slot),
                    "pairKey": pair_key,
                    "playerId": aggregate["playerId"],
                    "fullName": aggregate["fullName"],
                    "headshot": aggregate["headshot"],
                    "positionCode": position_code,
                    "eligibleSlot": slot,
                    "slotLabel": SLOT_LABELS[slot],
                    "historicalTeamAbbrev": pair["historicalTeam"]["abbrev"],
                    "historicalTeamName": pair["historicalTeam"]["name"],
                    "historicalTeamLogo": pair["historicalTeam"]["logo"],
                    "modernFranchiseAbbrev": pair["modernFranchise"]["abbrev"],
                    "decade": pair["decadeLabel"],
                    "awards": awards,
                    "stats": stats,
                }
                candidates.append(candidate)

            for aggregate in goalies.values():
                if aggregate["stats"]["gamesPlayed"] < MIN_DECADE_GAMES:
                    continue
                awards = await self.summarize_candidate_awards(aggregate["playerId"], pair["seasonTeams"])
                stats = {
                    "gamesPlayed": int(aggregate["stats"]["gamesPlayed"]),
                    "wins": int(aggregate["stats"]["wins"]),
                    "shutouts": int(aggregate["stats"]["shutouts"]),
                    "savePercentage": round(
                        aggregate["stats"]["saves"] / aggregate["stats"]["shotsAgainst"],
                        6,
                    )
                    if aggregate["stats"]["shotsAgainst"]
                    else 0.0,
                    "goalsAgainstAverage": round(
                        aggregate["stats"]["goalsAgainst"] * 3600 / aggregate["stats"]["timeOnIce"],
                        6,
                    )
                    if aggregate["stats"]["timeOnIce"]
                    else 0.0,
                }
                candidate = {
                    "candidateKey": make_candidate_key(pair_key, aggregate["playerId"], "G"),
                    "pairKey": pair_key,
                    "playerId": aggregate["playerId"],
                    "fullName": aggregate["fullName"],
                    "headshot": aggregate["headshot"],
                    "positionCode": "G",
                    "eligibleSlot": "G",
                    "slotLabel": SLOT_LABELS["G"],
                    "historicalTeamAbbrev": pair["historicalTeam"]["abbrev"],
                    "historicalTeamName": pair["historicalTeam"]["name"],
                    "historicalTeamLogo": pair["historicalTeam"]["logo"],
                    "modernFranchiseAbbrev": pair["modernFranchise"]["abbrev"],
                    "decade": pair["decadeLabel"],
                    "awards": awards,
                    "stats": stats,
                }
                candidates.append(candidate)

            pool = {"pairKey": pair_key, "candidates": candidates}
            self.store.set_team_decade_pool(pair_key, SCORING_VERSION, pool)
            self._pair_pool_cache[pair_key] = pool
            return pool

    async def get_decade_role_leaderboard(self, decade_start: int, role: str) -> dict[str, dict[str, Any]]:
        cache_key = (decade_start, role)
        cached = self._leaderboard_cache.get(cache_key)
        if cached is not None:
            return cached

        stored = self.store.get_decade_role_leaderboard(decade_start, role, SCORING_VERSION)
        if stored is not None:
            leaderboard = stored["players"]
            self._leaderboard_cache[cache_key] = leaderboard
            return leaderboard

        async with self._leaderboard_lock(decade_start, role):
            cached = self._leaderboard_cache.get(cache_key)
            if cached is not None:
                return cached

            stored = self.store.get_decade_role_leaderboard(decade_start, role, SCORING_VERSION)
            if stored is not None:
                leaderboard = stored["players"]
                self._leaderboard_cache[cache_key] = leaderboard
                return leaderboard

            pairs = [
                pair
                for pair in await self.get_draw_pairs()
                if pair["decadeStart"] == decade_start
            ]
            players: list[dict[str, Any]] = []
            for pair in pairs:
                pool = await self.get_team_decade_pool(pair["pairKey"])
                for candidate in pool["candidates"]:
                    if candidate["eligibleSlot"] != role:
                        continue
                    players.append(
                        {
                            **candidate,
                            "totalsMetrics": totals_metrics(role, candidate["stats"], decade_start),
                            "rateMetrics": rate_metrics(role, candidate["stats"], decade_start),
                        }
                    )

            leaderboard = score_role_players(role, players, decade_start)
            self.store.set_decade_role_leaderboard(
                decade_start,
                role,
                SCORING_VERSION,
                {"players": leaderboard},
            )
            self._leaderboard_cache[cache_key] = leaderboard
            return leaderboard

    async def get_random_draw(
        self,
        available_slots: list[str],
        exclude_candidate_keys: list[str],
        hard_mode: bool = False,
        lock_franchise_abbrev: str | None = None,
        lock_decade: str | None = None,
        exclude_pair_key: str | None = None,
    ) -> dict[str, Any]:
        if not available_slots:
            raise HTTPException(status_code=400, detail="At least one available slot is required.")

        pairs = await self.get_draw_pairs()
        filtered_pairs = [
            pair
            for pair in pairs
            if (lock_franchise_abbrev is None or pair["currentAbbrev"] == lock_franchise_abbrev)
            and (lock_decade is None or pair["decadeLabel"] == lock_decade)
            and (exclude_pair_key is None or pair["pairKey"] != exclude_pair_key)
        ]
        if not filtered_pairs:
            raise HTTPException(status_code=400, detail="No valid draw pairs match the requested filters.")

        excluded_player_ids = {
            parsed[1]
            for parsed in (parse_candidate_key(candidate_key) for candidate_key in exclude_candidate_keys)
            if parsed is not None
        }
        open_slot_set = set(available_slots)

        for pair in self.rng.sample(filtered_pairs, len(filtered_pairs)):
            pool_source = self._team_decade_pool_source(pair["pairKey"])
            pool = await self.get_team_decade_pool(pair["pairKey"])
            eligible = [
                candidate
                for candidate in pool["candidates"]
                if candidate["eligibleSlot"] in open_slot_set and candidate["playerId"] not in excluded_player_ids
            ]
            if not eligible:
                continue

            eligible_roles = sorted({candidate["eligibleSlot"] for candidate in eligible}, key=ROLE_ORDER.index)
            leaderboard_sources = {
                role: self._leaderboard_source(pair["decadeStart"], role)
                for role in eligible_roles
            }
            role_leaderboards = {
                role: leaderboard
                for role, leaderboard in zip(
                    eligible_roles,
                    await asyncio.gather(
                        *(self.get_decade_role_leaderboard(pair["decadeStart"], role) for role in eligible_roles)
                    ),
                )
            }
            eligible_games_played = {
                candidate["candidateKey"]: candidate["stats"]["gamesPlayed"]
                for candidate in eligible
            }
            candidates = []
            for candidate in eligible:
                scored = role_leaderboards[candidate["eligibleSlot"]].get(candidate["candidateKey"])
                candidates.append(
                    {
                        "candidateKey": candidate["candidateKey"],
                        "playerId": candidate["playerId"],
                        "fullName": candidate["fullName"],
                        "headshot": candidate["headshot"],
                        "positionCode": candidate["positionCode"],
                        "eligibleSlot": candidate["eligibleSlot"],
                        "eligibleSlotLabel": candidate["slotLabel"],
                        "historicalTeamAbbrev": candidate["historicalTeamAbbrev"],
                        "historicalTeamName": candidate["historicalTeamName"],
                        "historicalTeamLogo": candidate["historicalTeamLogo"],
                        "ratingTier": None if hard_mode else (scored.get("ratingTier") if scored is not None else None),
                        "awards": [] if hard_mode else candidate.get("awards", []),
                        "offerStats": None if hard_mode else decade_offer_stats(candidate),
                    }
                )
            if not candidates:
                continue

            if hard_mode:
                candidates.sort(
                    key=lambda candidate: (
                        candidate["fullName"],
                        SLOT_SORT_ORDER[candidate["eligibleSlot"]],
                        candidate["playerId"],
                    )
                )
            else:
                candidates.sort(
                    key=lambda candidate: (
                        -eligible_games_played[candidate["candidateKey"]],
                        SLOT_SORT_ORDER[candidate["eligibleSlot"]],
                        candidate["fullName"],
                    )
                )
            return {
                "pairKey": pair["pairKey"],
                "hardMode": hard_mode,
                "modernFranchise": pair["modernFranchise"],
                "historicalTeam": pair["historicalTeam"],
                "decade": pair["decadeLabel"],
                "seasonRange": pair["seasonRange"],
                "availableSlots": available_slots,
                "provenance": summarize_draw_provenance(pool_source, leaderboard_sources),
                "candidates": candidates,
            }

        raise HTTPException(status_code=503, detail="No eligible candidates available for the remaining lineup slots.")

    async def _score_lineup_selections(self, selections: list[dict[str, Any]]) -> dict[str, Any]:
        if len(selections) != len(SLOT_SEQUENCE):
            raise HTTPException(status_code=400, detail=f"Lineup must contain exactly {len(SLOT_SEQUENCE)} selections.")

        ordered_slots = [selection["slot"] for selection in selections]
        if ordered_slots != SLOT_SEQUENCE:
            raise HTTPException(status_code=400, detail="Lineup slots must follow C, W, W, D, D, G order.")

        seen_player_ids: set[int] = set()
        seen_candidate_keys: set[str] = set()
        breakdown: list[dict[str, Any]] = []

        for selection in selections:
            slot = selection["slot"]
            candidate_key = selection["candidateKey"]
            if candidate_key in seen_candidate_keys:
                raise HTTPException(status_code=400, detail="Each player may only be selected once.")
            seen_candidate_keys.add(candidate_key)

            parsed = parse_candidate_key(candidate_key)
            if parsed is None:
                raise HTTPException(status_code=400, detail=f"Invalid candidate key: {candidate_key}.")
            pair_key, player_id, slot_from_key = parsed
            if slot != slot_from_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"Candidate {candidate_key} is not eligible for slot {slot}.",
                )
            if player_id in seen_player_ids:
                raise HTTPException(status_code=400, detail="Each player may only be selected once.")
            seen_player_ids.add(player_id)

            pair = await self.get_draw_pair(pair_key)
            if pair is None:
                raise HTTPException(status_code=400, detail=f"Unknown draw pair {pair_key}.")
            pool = await self.get_team_decade_pool(pair_key)
            candidate = next(
                (entry for entry in pool["candidates"] if entry["candidateKey"] == candidate_key),
                None,
            )
            if candidate is None:
                raise HTTPException(status_code=400, detail=f"Candidate {candidate_key} is no longer valid.")

            leaderboard = await self.get_decade_role_leaderboard(pair["decadeStart"], slot)
            scored = leaderboard.get(candidate_key)
            if scored is None:
                raise HTTPException(status_code=503, detail="Unable to score selected player.")

            row = {
                "slot": slot,
                "slotLabel": SLOT_LABELS[slot],
                "candidateKey": candidate_key,
                "playerId": player_id,
                "fullName": candidate["fullName"],
                "teamAbbrev": pair["historicalTeam"]["abbrev"],
                "teamName": pair["historicalTeam"]["name"],
                "modernFranchiseAbbrev": pair["modernFranchise"]["abbrev"],
                "decade": pair["decadeLabel"],
                "positionCode": candidate["positionCode"],
                "headshot": candidate["headshot"],
                "awards": candidate.get("awards", []),
                "score": scored["score"],
                "rawScore": scored["rawScore"],
                "totalsScore": scored["totalsScore"],
                "rateScore": scored["rateScore"],
                "metricPercentiles": {
                    "totals": scored["totalsPercentiles"],
                    "rates": scored["ratePercentiles"],
                },
                "stats": decade_offer_stats(candidate),
                "scorecardTotals": scorecard_totals(candidate),
            }
            source_draw_index = selection.get("sourceDrawIndex")
            if source_draw_index is not None:
                row["sourceDrawIndex"] = source_draw_index
            breakdown.append(row)

        total_score = round(sum(player["score"] for player in breakdown) / len(breakdown), 1)
        return {
            "lineupBreakdown": breakdown,
            "totalScore": total_score,
            "letterGrade": map_letter_grade(total_score),
            "projectedRecord": project_record(total_score),
        }

    async def grade_lineup(self, lineup: list[Any]) -> dict[str, Any]:
        return await self._score_lineup_selections(
            [{"slot": item.slot, "candidateKey": item.candidateKey} for item in lineup]
        )

    async def _board_candidates_for_best_lineup(self, board: Any) -> list[dict[str, Any]]:
        pair = await self.get_draw_pair(board.pairKey)
        if pair is None:
            raise HTTPException(status_code=400, detail=f"Unknown draw pair {board.pairKey}.")

        pool = await self.get_team_decade_pool(board.pairKey)
        candidates_by_key = {candidate["candidateKey"]: candidate for candidate in pool["candidates"]}
        role_leaderboards: dict[str, dict[str, dict[str, Any]]] = {}
        resolved: list[dict[str, Any]] = []
        seen_candidate_keys: set[str] = set()

        for candidate_key in board.candidateKeys:
            if candidate_key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(candidate_key)
            parsed = parse_candidate_key(candidate_key)
            if parsed is None:
                raise HTTPException(status_code=400, detail=f"Invalid candidate key: {candidate_key}.")
            pair_key, _, slot = parsed
            if pair_key != board.pairKey:
                raise HTTPException(
                    status_code=400,
                    detail=f"Candidate {candidate_key} does not belong to draw pair {board.pairKey}.",
                )
            candidate = candidates_by_key.get(candidate_key)
            if candidate is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Candidate {candidate_key} is not valid for draw pair {board.pairKey}.",
                )
            leaderboard = role_leaderboards.get(slot)
            if leaderboard is None:
                leaderboard = await self.get_decade_role_leaderboard(pair["decadeStart"], slot)
                role_leaderboards[slot] = leaderboard
            scored = leaderboard.get(candidate_key)
            if scored is None:
                raise HTTPException(status_code=503, detail=f"Unable to score candidate {candidate_key}.")
            resolved.append(
                {
                    "candidateKey": candidate_key,
                    "playerId": candidate["playerId"],
                    "eligibleSlot": candidate["eligibleSlot"],
                    "score": scored["score"],
                }
            )

        if not resolved:
            raise HTTPException(status_code=400, detail=f"Draw board {board.pairKey} has no valid candidates.")
        return resolved

    def _best_lineup_for_board_candidates(self, boards: list[list[dict[str, Any]]]) -> list[dict[str, Any]] | None:
        remaining_target = {
            "C": SLOT_SEQUENCE.count("C"),
            "W": SLOT_SEQUENCE.count("W"),
            "D": SLOT_SEQUENCE.count("D"),
            "G": SLOT_SEQUENCE.count("G"),
        }
        available_slots_by_board = [
            sorted(
                {candidate["eligibleSlot"] for candidate in board},
                key=lambda slot: SLOT_SORT_ORDER[slot],
            )
            for board in boards
        ]

        assignments: list[tuple[str, ...]] = []

        def enumerate_assignments(board_index: int, current: list[str]) -> None:
            if board_index == len(boards):
                if all(count == 0 for count in remaining_target.values()):
                    assignments.append(tuple(current))
                return
            for slot in available_slots_by_board[board_index]:
                if remaining_target[slot] <= 0:
                    continue
                remaining_target[slot] -= 1
                current.append(slot)
                enumerate_assignments(board_index + 1, current)
                current.pop()
                remaining_target[slot] += 1

        enumerate_assignments(0, [])
        if not assignments:
            return None

        best_total = -1
        best_choices: list[dict[str, Any]] | None = None

        for assignment in assignments:
            player_options: dict[int, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
            for board_index, slot in enumerate(assignment):
                for candidate in boards[board_index]:
                    if candidate["eligibleSlot"] != slot:
                        continue
                    player_options[candidate["playerId"]].append((board_index, candidate))

            players = list(player_options.items())
            full_mask = (1 << len(boards)) - 1
            impossible = -10**9

            @lru_cache(maxsize=None)
            def solve(player_index: int, filled_mask: int) -> int:
                if filled_mask == full_mask:
                    return 0
                if player_index == len(players):
                    return impossible

                best_here = solve(player_index + 1, filled_mask)
                for board_index, candidate in players[player_index][1]:
                    if filled_mask & (1 << board_index):
                        continue
                    downstream = solve(player_index + 1, filled_mask | (1 << board_index))
                    if downstream == impossible:
                        continue
                    candidate_score = int(round(candidate["score"] * 10))
                    best_here = max(best_here, candidate_score + downstream)
                return best_here

            assignment_total = solve(0, 0)
            if assignment_total == impossible or assignment_total < best_total:
                continue

            selected_by_board: dict[int, dict[str, Any]] = {}

            def rebuild(player_index: int, filled_mask: int) -> None:
                if filled_mask == full_mask or player_index == len(players):
                    return
                best_here = solve(player_index, filled_mask)
                if solve(player_index + 1, filled_mask) == best_here:
                    rebuild(player_index + 1, filled_mask)
                    return
                for board_index, candidate in players[player_index][1]:
                    if filled_mask & (1 << board_index):
                        continue
                    downstream = solve(player_index + 1, filled_mask | (1 << board_index))
                    if downstream == impossible:
                        continue
                    candidate_score = int(round(candidate["score"] * 10))
                    if candidate_score + downstream == best_here:
                        selected_by_board[board_index] = candidate
                        rebuild(player_index + 1, filled_mask | (1 << board_index))
                        return

            rebuild(0, 0)
            if len(selected_by_board) != len(boards):
                continue

            ordered_selections: list[dict[str, Any]] = []
            chosen_by_slot: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
            for board_index, candidate in selected_by_board.items():
                chosen_by_slot[assignment[board_index]].append((board_index, candidate))
            for slot in chosen_by_slot:
                chosen_by_slot[slot].sort(key=lambda entry: entry[0])

            slot_offsets = defaultdict(int)
            for slot in SLOT_SEQUENCE:
                board_index, candidate = chosen_by_slot[slot][slot_offsets[slot]]
                slot_offsets[slot] += 1
                ordered_selections.append(
                    {
                        "slot": slot,
                        "candidateKey": candidate["candidateKey"],
                        "sourceDrawIndex": board_index + 1,
                    }
                )

            best_total = assignment_total
            best_choices = ordered_selections

        return best_choices

    async def best_lineup_from_boards(self, lineup: list[Any], boards: list[Any]) -> dict[str, Any]:
        current_result = await self.grade_lineup(lineup)
        if len(boards) != len(SLOT_SEQUENCE):
            raise HTTPException(
                status_code=400,
                detail=f"Exactly {len(SLOT_SEQUENCE)} draw boards are required to compute the best lineup.",
            )

        board_candidates = [await self._board_candidates_for_best_lineup(board) for board in boards]
        best_selections = self._best_lineup_for_board_candidates(board_candidates)
        if best_selections is None:
            raise HTTPException(status_code=400, detail="Unable to derive a valid best lineup from the provided boards.")

        best_result = await self._score_lineup_selections(best_selections)
        for best_row, selection in zip(best_result["lineupBreakdown"], best_selections):
            best_row["sourceDrawIndex"] = selection["sourceDrawIndex"]

        best_result["currentTotalScore"] = current_result["totalScore"]
        best_result["currentLetterGrade"] = current_result["letterGrade"]
        best_result["scoreDelta"] = round(best_result["totalScore"] - current_result["totalScore"], 1)
        return best_result

    async def prewarm_missing(self) -> None:
        await self.initialize()
        pairs = await self.get_draw_pairs()
        for pair in pairs:
            await self.get_team_decade_pool(pair["pairKey"])
        for decade_start in sorted({pair["decadeStart"] for pair in pairs}):
            for role in ROLE_ORDER:
                await self.get_decade_role_leaderboard(decade_start, role)
        self.store.set_meta("prewarm_complete", SCORING_VERSION)

    async def get_admin_snapshot(
        self,
        decade_label: str,
        role: str,
        role_limit: int = 25,
        overall_limit: int = 20,
    ) -> dict[str, Any]:
        if decade_label not in DECADE_START_BY_LABEL:
            raise HTTPException(status_code=400, detail=f"Unsupported decade {decade_label}.")
        if role not in ROLE_ORDER:
            raise HTTPException(status_code=400, detail=f"Unsupported role {role}.")

        decade_start = DECADE_START_BY_LABEL[decade_label]
        role_leaderboard = await self.get_decade_role_leaderboard(decade_start, role)
        role_rows = sorted(
            role_leaderboard.values(),
            key=lambda player: (-player["score"], -player["rawScore"], player["fullName"]),
        )

        distribution = []
        for threshold, label in ADMIN_SCORE_BUCKETS:
            if label == "<70":
                count = sum(1 for player in role_rows if player["score"] < 70.0)
            else:
                next_threshold = next(
                    (
                        ADMIN_SCORE_BUCKETS[index - 1][0]
                        for index, bucket in enumerate(ADMIN_SCORE_BUCKETS)
                        if bucket[1] == label and index > 0
                    ),
                    None,
                )
                count = sum(
                    1
                    for player in role_rows
                    if player["score"] >= threshold
                    and (next_threshold is None or player["score"] < next_threshold)
                )
            distribution.append({"label": label, "count": count})

        role_table = [
            {
                "rank": index + 1,
                "playerId": player["playerId"],
                "fullName": player["fullName"],
                "teamAbbrev": player["historicalTeamAbbrev"],
                "teamName": player["historicalTeamName"],
                "positionCode": player["positionCode"],
                "gamesPlayed": player["stats"].get("gamesPlayed", 0),
                "score": player["score"],
                "rawScore": player["rawScore"],
                "overallPercentile": player["overallPercentile"],
                "ratingTier": player["ratingTier"],
                "statsSummary": decade_offer_stats(player),
            }
            for index, player in enumerate(role_rows[:role_limit])
        ]

        overall_rows: list[dict[str, Any]] = []
        for overview_role in ROLE_ORDER:
            leaderboard = await self.get_decade_role_leaderboard(decade_start, overview_role)
            overall_rows.extend(leaderboard.values())
        overall_rows.sort(
            key=lambda player: (-player["score"], -player["rawScore"], player["fullName"])
        )
        overall_table = [
            {
                "rank": index + 1,
                "fullName": player["fullName"],
                "role": player["eligibleSlot"],
                "teamAbbrev": player["historicalTeamAbbrev"],
                "positionCode": player["positionCode"],
                "score": player["score"],
                "rawScore": player["rawScore"],
                "ratingTier": player["ratingTier"],
            }
            for index, player in enumerate(overall_rows[:overall_limit])
        ]

        pairs = await self.get_draw_pairs()
        decade_pair_count = sum(1 for pair in pairs if pair["decadeStart"] == decade_start)

        return {
            "selectedDecade": decade_label,
            "selectedRole": role,
            "scoringVersion": SCORING_VERSION,
            "prewarmComplete": self.store.get_meta("prewarm_complete") == SCORING_VERSION,
            "decadePairCount": decade_pair_count,
            "rolePlayerCount": len(role_rows),
            "distribution": distribution,
            "roleTable": role_table,
            "overallTable": overall_table,
        }
