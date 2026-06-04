from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.constants import (
    AWARD_TROPHIES,
    BASE_RECORDS_URL,
    BASE_WEB_URL,
    DECADE_LABELS,
    DEFAULT_DB_PATH,
    HEADSHOT_FALLBACK_TEMPLATE,
    LOGO_URL_TEMPLATE,
    MIN_DECADE_GAMES,
    SCORING_VERSION,
    SKATER_TOI_TRACKING_START_SEASON,
    SLOT_LABELS,
    SLOT_SEQUENCE,
    SLOT_SORT_ORDER,
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
AWARD_CACHE_KEY = "tracked-awards-v1"


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
    if slot == "C":
        return {
            "points": stats.get("points", 0),
            "assists": stats.get("assists", 0),
            "goals": stats.get("goals", 0),
            "shots": stats.get("shots", 0),
        }
    if slot == "W":
        return {
            "points": stats.get("points", 0),
            "goals": stats.get("goals", 0),
            "shots": stats.get("shots", 0),
        }
    if slot == "D":
        offer = {
            "points": stats.get("points", 0),
            "assists": stats.get("assists", 0),
            "shots": stats.get("shots", 0),
        }
        if stats.get("avgTimeOnIcePerGame") is not None:
            offer["avgTimeOnIcePerGame"] = stats.get("avgTimeOnIcePerGame")
        return offer
    return {
        "wins": stats.get("wins", 0),
        "shutouts": stats.get("shutouts", 0),
        "goalsAgainstAverage": stats.get("goalsAgainstAverage"),
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

    async def summarize_candidate_awards(
        self,
        player_id: int,
        season_teams: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        award_index = await self.get_award_index()
        trophy_counts: dict[int, dict[str, int]] = defaultdict(lambda: {"winner": 0, "finalist": 0})
        for season_team in season_teams:
            stint_key = (player_id, int(season_team["season"]), int(season_team["teamId"]))
            for award in award_index.get(stint_key, []):
                trophy_config = AWARD_TROPHIES[award["trophyId"]]
                if award["status"] == "WINNER":
                    trophy_counts[award["trophyId"]]["winner"] += 1
                elif trophy_config["allowFinalists"]:
                    trophy_counts[award["trophyId"]]["finalist"] += 1

        awards: list[dict[str, Any]] = []
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
            pool = await self.get_team_decade_pool(pair["pairKey"])
            eligible = [
                candidate
                for candidate in pool["candidates"]
                if candidate["eligibleSlot"] in open_slot_set and candidate["playerId"] not in excluded_player_ids
            ]
            if not eligible:
                continue

            eligible_roles = sorted({candidate["eligibleSlot"] for candidate in eligible}, key=ROLE_ORDER.index)
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
                        "ratingTier": scored.get("ratingTier") if scored is not None else None,
                        "awards": candidate.get("awards", []),
                        "offerStats": decade_offer_stats(candidate),
                    }
                )
            if not candidates:
                continue

            candidates.sort(
                key=lambda candidate: (
                    -eligible_games_played[candidate["candidateKey"]],
                    SLOT_SORT_ORDER[candidate["eligibleSlot"]],
                    candidate["fullName"],
                )
            )
            return {
                "pairKey": pair["pairKey"],
                "modernFranchise": pair["modernFranchise"],
                "historicalTeam": pair["historicalTeam"],
                "decade": pair["decadeLabel"],
                "seasonRange": pair["seasonRange"],
                "availableSlots": available_slots,
                "candidates": candidates,
            }

        raise HTTPException(status_code=503, detail="No eligible candidates available for the remaining lineup slots.")

    async def grade_lineup(self, lineup: list[Any]) -> dict[str, Any]:
        if len(lineup) != len(SLOT_SEQUENCE):
            raise HTTPException(status_code=400, detail=f"Lineup must contain exactly {len(SLOT_SEQUENCE)} selections.")

        ordered_slots = [item.slot for item in lineup]
        if ordered_slots != SLOT_SEQUENCE:
            raise HTTPException(status_code=400, detail="Lineup slots must follow C, W, W, D, D, G order.")

        seen_player_ids: set[int] = set()
        seen_candidate_keys: set[str] = set()
        breakdown: list[dict[str, Any]] = []

        for item in lineup:
            if item.candidateKey in seen_candidate_keys:
                raise HTTPException(status_code=400, detail="Each player may only be selected once.")
            seen_candidate_keys.add(item.candidateKey)

            parsed = parse_candidate_key(item.candidateKey)
            if parsed is None:
                raise HTTPException(status_code=400, detail=f"Invalid candidate key: {item.candidateKey}.")
            pair_key, player_id, slot_from_key = parsed
            if item.slot != slot_from_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"Candidate {item.candidateKey} is not eligible for slot {item.slot}.",
                )
            if player_id in seen_player_ids:
                raise HTTPException(status_code=400, detail="Each player may only be selected once.")
            seen_player_ids.add(player_id)

            pair = await self.get_draw_pair(pair_key)
            if pair is None:
                raise HTTPException(status_code=400, detail=f"Unknown draw pair {pair_key}.")
            pool = await self.get_team_decade_pool(pair_key)
            candidate = next(
                (entry for entry in pool["candidates"] if entry["candidateKey"] == item.candidateKey),
                None,
            )
            if candidate is None:
                raise HTTPException(status_code=400, detail=f"Candidate {item.candidateKey} is no longer valid.")

            leaderboard = await self.get_decade_role_leaderboard(pair["decadeStart"], item.slot)
            scored = leaderboard.get(item.candidateKey)
            if scored is None:
                raise HTTPException(status_code=503, detail="Unable to score selected player.")

            breakdown.append(
                {
                    "slot": item.slot,
                    "slotLabel": SLOT_LABELS[item.slot],
                    "candidateKey": item.candidateKey,
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
            )

        total_score = round(sum(player["score"] for player in breakdown) / len(breakdown), 1)
        return {
            "lineupBreakdown": breakdown,
            "totalScore": total_score,
            "letterGrade": map_letter_grade(total_score),
            "projectedRecord": project_record(total_score),
        }

    async def prewarm_missing(self) -> None:
        await self.initialize()
        pairs = await self.get_draw_pairs()
        for pair in pairs:
            await self.get_team_decade_pool(pair["pairKey"])
        for decade_start in sorted({pair["decadeStart"] for pair in pairs}):
            for role in ROLE_ORDER:
                await self.get_decade_role_leaderboard(decade_start, role)
        self.store.set_meta("prewarm_complete", SCORING_VERSION)
