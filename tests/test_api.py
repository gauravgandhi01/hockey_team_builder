from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.nhl_service import NhlApiService


def make_response(data: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=data)


def skater(player_id: int, first: str, last: str, position: str, games: int, goals: int, assists: int, points: int, plus_minus: int, shots: int) -> dict[str, Any]:
    return {
        "playerId": player_id,
        "headshot": f"https://example.com/{player_id}.png",
        "firstName": {"default": first},
        "lastName": {"default": last},
        "positionCode": position,
        "gamesPlayed": games,
        "goals": goals,
        "assists": assists,
        "points": points,
        "plusMinus": plus_minus,
        "shots": shots,
    }


def goalie(player_id: int, first: str, last: str, games: int, wins: int, goals_against: int, shots_against: int, saves: int, shutouts: int, time_on_ice: int) -> dict[str, Any]:
    return {
        "playerId": player_id,
        "headshot": f"https://example.com/{player_id}.png",
        "firstName": {"default": first},
        "lastName": {"default": last},
        "gamesPlayed": games,
        "wins": wins,
        "goalsAgainst": goals_against,
        "shotsAgainst": shots_against,
        "saves": saves,
        "shutouts": shutouts,
        "timeOnIce": time_on_ice,
    }


class MockHistoricalApi:
    def __init__(self):
        self.calls: dict[str, int] = defaultdict(int)
        self.franchises = {
            "data": [
                {"id": 27, "teamAbbrev": "COL", "fullName": "Colorado Avalanche", "firstSeasonId": 19791980, "lastSeasonId": None},
                {"id": 40, "teamAbbrev": "UTA", "fullName": "Utah Mammoth", "firstSeasonId": 20242025, "lastSeasonId": None},
                {"id": 15, "teamAbbrev": "WSH", "fullName": "Washington Capitals", "firstSeasonId": 19741975, "lastSeasonId": None},
                {"id": 35, "teamAbbrev": "WPG", "fullName": "Winnipeg Jets", "firstSeasonId": 19992000, "lastSeasonId": None},
            ]
        }
        self.season_results = {
            "data": [
                {"franchiseId": 27, "seasonId": 19801981, "teamId": 32, "triCode": "QUE", "teamName": "Quebec Nordiques", "gameTypeId": 2},
                {"franchiseId": 27, "seasonId": 19811982, "teamId": 32, "triCode": "QUE", "teamName": "Quebec Nordiques", "gameTypeId": 2},
                {"franchiseId": 27, "seasonId": 19951996, "teamId": 21, "triCode": "COL", "teamName": "Colorado Avalanche", "gameTypeId": 2},
                {"franchiseId": 27, "seasonId": 19961997, "teamId": 21, "triCode": "COL", "teamName": "Colorado Avalanche", "gameTypeId": 2},
                {"franchiseId": 27, "seasonId": 20242025, "teamId": 21, "triCode": "COL", "teamName": "Colorado Avalanche", "gameTypeId": 2},
                {"franchiseId": 40, "seasonId": 20242025, "teamId": 59, "triCode": "UTA", "teamName": "Utah Mammoth", "gameTypeId": 2},
                {"franchiseId": 40, "seasonId": 20252026, "teamId": 59, "triCode": "UTA", "teamName": "Utah Mammoth", "gameTypeId": 2},
                {"franchiseId": 15, "seasonId": 20082009, "teamId": 15, "triCode": "WSH", "teamName": "Washington Capitals", "gameTypeId": 2},
                {"franchiseId": 15, "seasonId": 20092010, "teamId": 15, "triCode": "WSH", "teamName": "Washington Capitals", "gameTypeId": 2},
                {"franchiseId": 15, "seasonId": 20242025, "teamId": 15, "triCode": "WSH", "teamName": "Washington Capitals", "gameTypeId": 2},
                {"franchiseId": 35, "seasonId": 20052006, "teamId": 11, "triCode": "ATL", "teamName": "Atlanta Thrashers", "gameTypeId": 2},
                {"franchiseId": 35, "seasonId": 20062007, "teamId": 11, "triCode": "ATL", "teamName": "Atlanta Thrashers", "gameTypeId": 2},
                {"franchiseId": 35, "seasonId": 20112012, "teamId": 52, "triCode": "WPG", "teamName": "Winnipeg Jets", "gameTypeId": 2},
                {"franchiseId": 35, "seasonId": 20122013, "teamId": 52, "triCode": "WPG", "teamName": "Winnipeg Jets", "gameTypeId": 2},
                {"franchiseId": 35, "seasonId": 20242025, "teamId": 52, "triCode": "WPG", "teamName": "Winnipeg Jets", "gameTypeId": 2},
            ]
        }
        self.award_details = {
            "data": [
                {"playerId": 100, "fullName": "Alex Ovechkin", "seasonId": 20082009, "teamId": 15, "trophyId": 8, "status": "WINNER"},
                {"playerId": 100, "fullName": "Alex Ovechkin", "seasonId": 20092010, "teamId": 15, "trophyId": 8, "status": "WINNER"},
                {"playerId": 100, "fullName": "Alex Ovechkin", "seasonId": 20082009, "teamId": 15, "trophyId": 16, "status": "WINNER"},
                {"playerId": 100, "fullName": "Alex Ovechkin", "seasonId": 20092010, "teamId": 15, "trophyId": 15, "status": "WINNER"},
                {"playerId": 104, "fullName": "Brooks Laich", "seasonId": 20092010, "teamId": 15, "trophyId": 17, "status": "FINALIST"},
                {"playerId": 103, "fullName": "Mike Green", "seasonId": 20082009, "teamId": 15, "trophyId": 11, "status": "FINALIST"},
                {"playerId": 103, "fullName": "Mike Green", "seasonId": 20092010, "teamId": 15, "trophyId": 11, "status": "FINALIST"},
                {"playerId": 105, "fullName": "Jose Theodore", "seasonId": 20092010, "teamId": 15, "trophyId": 18, "status": "FINALIST"},
                {"playerId": 217, "fullName": "Connor Hellebuyck", "seasonId": 20242025, "teamId": 52, "trophyId": 18, "status": "WINNER"},
            ]
        }
        self.player_stanley_cup_wins = {
            "data": [
                {
                    "playerId": 100,
                    "playerName": "Alex Ovechkin",
                    "cupsWon": 1,
                    "seasonsWon": "2017-18 (WSH)",
                    "teamAbbrevs": "WSH",
                },
                {
                    "playerId": 314,
                    "playerName": "Patrick Roy",
                    "cupsWon": 1,
                    "seasonsWon": "1995-96 (COL)",
                    "teamAbbrevs": "COL",
                },
            ]
        }
        self.club_stats = {
            ("QUE", "19801981"): {
                "season": "19801981",
                "gameType": 2,
                "skaters": [
                    skater(300, "Peter", "Stastny", "C", 77, 39, 70, 109, 25, 250),
                    skater(301, "Michel", "Goulet", "L", 80, 32, 38, 70, 10, 225),
                    skater(302, "Marian", "Stastny", "R", 80, 28, 44, 72, 11, 210),
                    skater(303, "Mario", "Marois", "D", 80, 8, 29, 37, 18, 150),
                ],
                "goalies": [goalie(304, "Dan", "Bouchard", 53, 30, 172, 1840, 1668, 2, 186345)],
            },
            ("QUE", "19811982"): {
                "season": "19811982",
                "gameType": 2,
                "skaters": [
                    skater(300, "Peter", "Stastny", "C", 80, 46, 93, 139, 22, 271),
                    skater(301, "Michel", "Goulet", "L", 80, 33, 56, 89, 17, 240),
                    skater(302, "Marian", "Stastny", "R", 80, 35, 54, 89, 20, 218),
                    skater(303, "Mario", "Marois", "D", 80, 10, 32, 42, 15, 160),
                ],
                "goalies": [goalie(304, "Dan", "Bouchard", 54, 28, 175, 1900, 1725, 3, 189000)],
            },
            ("COL", "19951996"): {
                "season": "19951996",
                "gameType": 2,
                "skaters": [
                    skater(310, "Joe", "Sakic", "C", 82, 51, 69, 120, 18, 300),
                    skater(311, "Valeri", "Kamensky", "L", 82, 38, 47, 85, 14, 221),
                    skater(312, "Claude", "Lemieux", "R", 82, 38, 24, 62, 5, 240),
                    skater(313, "Sandis", "Ozolinsh", "D", 80, 13, 34, 47, 9, 180),
                ],
                "goalies": [goalie(314, "Patrick", "Roy", 82, 38, 170, 1905, 1735, 5, 198200)],
            },
            ("COL", "19961997"): {
                "season": "19961997",
                "gameType": 2,
                "skaters": [
                    skater(310, "Joe", "Sakic", "C", 65, 36, 38, 74, 16, 244),
                    skater(311, "Valeri", "Kamensky", "L", 81, 22, 38, 60, 10, 190),
                    skater(312, "Claude", "Lemieux", "R", 82, 36, 14, 50, 8, 222),
                    skater(313, "Sandis", "Ozolinsh", "D", 80, 23, 45, 68, 12, 210),
                ],
                "goalies": [goalie(314, "Patrick", "Roy", 63, 38, 140, 1605, 1465, 6, 150500)],
            },
            ("COL", "20242025"): {
                "season": "20242025",
                "gameType": 2,
                "skaters": [
                    skater(315, "Nathan", "MacKinnon", "C", 82, 42, 76, 118, 21, 330),
                    skater(316, "Mikko", "Rantanen", "R", 82, 39, 65, 104, 18, 290),
                    skater(317, "Cale", "Makar", "D", 79, 21, 69, 90, 28, 230),
                ],
                "goalies": [goalie(318, "Alexandar", "Georgiev", 60, 34, 165, 1820, 1655, 2, 174000)],
            },
            ("UTA", "20242025"): {
                "season": "20242025",
                "gameType": 2,
                "skaters": [
                    skater(400, "Clayton", "Keller", "R", 82, 37, 51, 88, 8, 250),
                    skater(401, "Logan", "Cooley", "C", 82, 28, 46, 74, 7, 200),
                    skater(402, "Mikhail", "Sergachev", "D", 79, 14, 42, 56, 11, 180),
                ],
                "goalies": [goalie(403, "Karel", "Vejmelka", 55, 26, 149, 1652, 1503, 2, 162000)],
            },
            ("UTA", "20252026"): {
                "season": "20252026",
                "gameType": 2,
                "skaters": [
                    skater(400, "Clayton", "Keller", "R", 82, 35, 50, 85, 9, 248),
                    skater(401, "Logan", "Cooley", "C", 82, 30, 48, 78, 10, 210),
                    skater(402, "Mikhail", "Sergachev", "D", 82, 16, 44, 60, 12, 185),
                ],
                "goalies": [goalie(403, "Karel", "Vejmelka", 56, 28, 150, 1670, 1520, 3, 165000)],
            },
            ("WSH", "20082009"): {
                "season": "20082009",
                "gameType": 2,
                "skaters": [
                    skater(100, "Alex", "Ovechkin", "L", 79, 56, 54, 110, 8, 528),
                    skater(101, "Nicklas", "Backstrom", "C", 82, 22, 66, 88, 37, 183),
                    skater(102, "Alexander", "Semin", "R", 62, 34, 45, 79, 26, 219),
                    skater(103, "Mike", "Green", "D", 68, 31, 42, 73, 39, 244),
                    skater(104, "Brooks", "Laich", "C", 82, 23, 30, 53, 12, 180),
                ],
                "goalies": [goalie(105, "Jose", "Theodore", 61, 32, 166, 1790, 1624, 1, 178200)],
            },
            ("WSH", "20092010"): {
                "season": "20092010",
                "gameType": 2,
                "skaters": [
                    skater(100, "Alex", "Ovechkin", "L", 72, 50, 59, 109, 45, 368),
                    skater(101, "Nicklas", "Backstrom", "C", 82, 33, 68, 101, 37, 216),
                    skater(102, "Alexander", "Semin", "R", 73, 40, 44, 84, 36, 266),
                    skater(103, "Mike", "Green", "D", 75, 19, 57, 76, 26, 251),
                    skater(104, "Brooks", "Laich", "C", 78, 25, 34, 59, 6, 221),
                ],
                "goalies": [goalie(105, "Jose", "Theodore", 47, 30, 121, 1352, 1231, 1, 155138)],
            },
            ("WSH", "20242025"): {
                "season": "20242025",
                "gameType": 2,
                "skaters": [
                    skater(100, "Alex", "Ovechkin", "L", 65, 44, 29, 73, 3, 240),
                    skater(101, "Nicklas", "Backstrom", "C", 0, 0, 0, 0, 0, 0),
                    skater(103, "Mike", "Green", "D", 0, 0, 0, 0, 0, 0),
                ],
                "goalies": [goalie(106, "Charlie", "Lindgren", 51, 26, 128, 1400, 1272, 4, 150000)],
            },
            ("ATL", "20052006"): {
                "season": "20052006",
                "gameType": 2,
                "skaters": [
                    skater(200, "Marc", "Savard", "C", 82, 28, 69, 97, 9, 233),
                    skater(201, "Ilya", "Kovalchuk", "L", 78, 52, 46, 98, 17, 371),
                    skater(202, "Marian", "Hossa", "R", 80, 39, 53, 92, 14, 275),
                    skater(203, "Garnet", "Exelby", "D", 75, 7, 18, 25, 6, 150),
                ],
                "goalies": [goalie(204, "Kari", "Lehtonen", 38, 20, 110, 1215, 1105, 2, 112000)],
            },
            ("ATL", "20062007"): {
                "season": "20062007",
                "gameType": 2,
                "skaters": [
                    skater(200, "Marc", "Savard", "C", 82, 28, 69, 97, 8, 240),
                    skater(201, "Ilya", "Kovalchuk", "L", 76, 42, 34, 76, 5, 315),
                    skater(202, "Marian", "Hossa", "R", 82, 43, 57, 100, 18, 295),
                    skater(203, "Garnet", "Exelby", "D", 70, 5, 17, 22, 8, 141),
                ],
                "goalies": [goalie(204, "Kari", "Lehtonen", 68, 34, 180, 1945, 1765, 2, 201000)],
            },
            ("WPG", "20112012"): {
                "season": "20112012",
                "gameType": 2,
                "skaters": [
                    skater(210, "Bryan", "Little", "C", 74, 24, 22, 46, 2, 165),
                    skater(211, "Blake", "Wheeler", "R", 80, 17, 47, 64, 7, 190),
                    skater(212, "Dustin", "Byfuglien", "D", 66, 12, 41, 53, 8, 209),
                ],
                "goalies": [goalie(213, "Ondrej", "Pavelec", 68, 29, 191, 2134, 1943, 4, 234000)],
            },
            ("WPG", "20122013"): {
                "season": "20122013",
                "gameType": 2,
                "skaters": [
                    skater(210, "Bryan", "Little", "C", 48, 7, 25, 32, 4, 98),
                    skater(211, "Blake", "Wheeler", "R", 48, 19, 22, 41, 2, 120),
                    skater(212, "Dustin", "Byfuglien", "D", 43, 8, 20, 28, 1, 110),
                ],
                "goalies": [goalie(213, "Ondrej", "Pavelec", 44, 22, 117, 1290, 1173, 3, 145000)],
            },
            ("WPG", "20242025"): {
                "season": "20242025",
                "gameType": 2,
                "skaters": [
                    skater(214, "Mark", "Scheifele", "C", 82, 34, 44, 78, 15, 210),
                    skater(215, "Kyle", "Connor", "L", 82, 41, 48, 89, 13, 300),
                    skater(216, "Josh", "Morrissey", "D", 81, 12, 54, 66, 18, 185),
                ],
                "goalies": [goalie(217, "Connor", "Hellebuyck", 60, 40, 130, 1750, 1620, 5, 176000)],
            },
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls[url] += 1
        path = request.url.path
        if path.endswith("/site/api/franchise"):
            return make_response(self.franchises)
        if path.endswith("/site/api/franchise-season-results"):
            return make_response(self.season_results)
        if path.endswith("/site/api/award-details"):
            return make_response(self.award_details)
        if path.endswith("/site/api/player-stanley-cup-wins"):
            return make_response(self.player_stanley_cup_wins)
        if "/v1/club-stats/" in path:
            parts = path.split("/")
            team = parts[-3]
            season = parts[-2]
            payload = self.club_stats.get((team, season))
            if payload is None:
                return httpx.Response(404, json={"detail": f"Unhandled team season {team} {season}"})
            return make_response(payload)
        return httpx.Response(404, json={"detail": f"Unhandled path {path}"})


def create_test_client(store_path: Path, transport: MockHistoricalApi, rng_seed: int = 0) -> TestClient:
    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    service = NhlApiService(client, rng=random.Random(rng_seed), store_path=store_path)
    app = create_app(service=service)
    return TestClient(app)


def test_root_page_renders(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Historical Franchise Mode" in response.text


def test_admin_dashboard_requires_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LINECRAFT_ADMIN_KEY", "secret-admin-key")
    monkeypatch.setenv("LINECRAFT_ADMIN_PATH", "/_private_linecraft_admin")
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.get("/_private_linecraft_admin")

    assert response.status_code == 404


def test_admin_dashboard_renders_with_valid_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LINECRAFT_ADMIN_KEY", "secret-admin-key")
    monkeypatch.setenv("LINECRAFT_ADMIN_PATH", "/_private_linecraft_admin")
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.get(
            "/_private_linecraft_admin",
            params={"key": "secret-admin-key", "decade": "2000s", "role": "W"},
        )

    assert response.status_code == 200
    assert "Ratings dashboard" in response.text
    assert "2000s W top" in response.text
    assert "Alex Ovechkin" in response.text


def test_draw_endpoint_returns_wsh_2000s_candidates_sorted_by_games_played(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WSH",
                "lockDecade": "2000s",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pairKey"] == "WSH:2000s"
    assert body["historicalTeam"]["abbrev"] == "WSH"
    assert body["seasonRange"] == {"start": "2008-09", "end": "2009-10"}
    assert body["provenance"]["kind"] == "fresh"
    assert body["provenance"]["poolSource"] == "fresh"
    assert body["provenance"]["leaderboardSources"]["C"] == "fresh"
    assert [entry["playerId"] for entry in body["candidates"]] == [101, 104, 100, 103, 102, 105]
    assert all("previewScore" not in entry for entry in body["candidates"])
    assert all("ratingTier" in entry for entry in body["candidates"])
    candidate = next(entry for entry in body["candidates"] if entry["playerId"] == 100)
    assert candidate["offerStats"] == {"points": 219, "goals": 106, "assists": 113}
    assert candidate["ratingTier"] == 1
    assert candidate["awards"] == [
        {"key": "mvp", "label": "MVP", "level": "winner", "count": 2},
        {"key": "art-ross", "label": "Art Ross", "level": "winner", "count": 1},
        {"key": "rocket", "label": "Rocket", "level": "winner", "count": 1},
    ]
    defenseman = next(entry for entry in body["candidates"] if entry["playerId"] == 103)
    assert defenseman["awards"] == [
        {"key": "norris", "label": "Norris", "level": "finalist", "count": 2},
    ]
    center = next(entry for entry in body["candidates"] if entry["playerId"] == 104)
    assert center["awards"] == [
        {"key": "selke", "label": "Selke", "level": "finalist", "count": 1},
    ]


def test_cup_badge_only_appears_for_matching_team_stint(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        col_response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "COL",
                "lockDecade": "1990s",
            },
        )
        wsh_response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WSH",
                "lockDecade": "2000s",
            },
        )

    assert col_response.status_code == 200
    roy = next(entry for entry in col_response.json()["candidates"] if entry["playerId"] == 314)
    assert roy["awards"] == [{"key": "cup", "label": "🏆", "level": "winner", "count": 1}]

    assert wsh_response.status_code == 200
    ovechkin = next(entry for entry in wsh_response.json()["candidates"] if entry["playerId"] == 100)
    assert {"key": "cup", "label": "🏆", "level": "winner", "count": 1} not in ovechkin["awards"]


def test_draw_endpoint_hard_mode_hides_hints_and_sorts_alphabetically(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "hardMode": True,
                "lockFranchiseAbbrev": "WSH",
                "lockDecade": "2000s",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["hardMode"] is True
    assert [entry["playerId"] for entry in body["candidates"]] == [100, 102, 104, 105, 103, 101]
    assert all(entry["offerStats"] is None for entry in body["candidates"])
    assert all(entry["ratingTier"] is None for entry in body["candidates"])
    assert all(entry["awards"] == [] for entry in body["candidates"])


def test_repeated_draw_uses_persisted_team_decade_pool_without_new_network_fetch(tmp_path: Path):
    store_path = tmp_path / "cache.sqlite3"
    first_transport = MockHistoricalApi()
    with create_test_client(store_path, first_transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WSH",
                "lockDecade": "2000s",
            },
        )
        assert response.status_code == 200

    first_club_calls = sum(
        count for url, count in first_transport.calls.items() if "/v1/club-stats/" in url
    )
    assert first_club_calls > 0

    second_transport = MockHistoricalApi()
    with create_test_client(store_path, second_transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WSH",
                "lockDecade": "2000s",
            },
        )
        assert response.status_code == 200
        assert response.json()["provenance"]["poolSource"] == "sqlite"

    second_club_calls = sum(
        count for url, count in second_transport.calls.items() if "/v1/club-stats/" in url
    )
    assert second_club_calls == 0
    second_award_calls = sum(
        count for url, count in second_transport.calls.items() if url.endswith("/site/api/award-details")
    )
    assert second_award_calls == 0


def test_hard_mode_draw_can_redraw_to_a_different_pair(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "hardMode": True,
                "excludePairKey": "WSH:2000s",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["hardMode"] is True
    assert body["pairKey"] != "WSH:2000s"


def test_historical_branding_resolves_predecessor_franchises(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        wpg_response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WPG",
                "lockDecade": "2000s",
            },
        )
        col_response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "COL",
                "lockDecade": "1980s",
            },
        )

    assert wpg_response.status_code == 200
    assert wpg_response.json()["historicalTeam"]["abbrev"] == "ATL"
    assert wpg_response.json()["historicalTeam"]["logo"] == "/static/thrashers.gif"
    assert wpg_response.json()["historicalTeam"]["secondaryNote"] == "Modern franchise: Winnipeg Jets"
    assert col_response.status_code == 200
    assert col_response.json()["historicalTeam"]["abbrev"] == "QUE"
    assert col_response.json()["historicalTeam"]["logo"] == "/static/nordiques.png"


def test_uta_only_exposes_2020s(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        valid = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "UTA",
                "lockDecade": "2020s",
            },
        )
        invalid = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "UTA",
                "lockDecade": "2010s",
            },
        )

    assert valid.status_code == 200
    assert valid.json()["decade"] == "2020s"
    assert invalid.status_code == 400


def test_team_reroll_preserves_decade_and_changes_pair(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockDecade": "2000s",
                "excludePairKey": "WSH:2000s",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decade"] == "2000s"
    assert body["pairKey"] == "WPG:2000s"


def test_decade_reroll_preserves_franchise_and_changes_pair(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/draw",
            json={
                "openSlots": ["C", "W", "D", "G"],
                "excludeCandidateKeys": [],
                "lockFranchiseAbbrev": "WPG",
                "excludePairKey": "WPG:2000s",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["modernFranchise"]["abbrev"] == "WPG"
    assert body["pairKey"] != "WPG:2000s"


def test_grade_endpoint_returns_record_projection(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/grade",
            json={
                "lineup": [
                    {"slot": "C", "candidateKey": "WSH:2000s:101:C"},
                    {"slot": "W", "candidateKey": "WSH:2000s:100:W"},
                    {"slot": "W", "candidateKey": "WSH:2000s:102:W"},
                    {"slot": "D", "candidateKey": "WSH:2000s:103:D"},
                    {"slot": "D", "candidateKey": "WPG:2000s:203:D"},
                    {"slot": "G", "candidateKey": "WSH:2000s:105:G"},
                ]
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["letterGrade"]
    assert body["projectedRecord"]["display"].count("-") == 2
    assert len(body["lineupBreakdown"]) == 6
    winger_row = next(item for item in body["lineupBreakdown"] if item["candidateKey"] == "WSH:2000s:100:W")
    assert winger_row["scorecardTotals"] == {"points": 219, "goals": 106, "assists": 113}
    assert winger_row["awards"] == [
        {"key": "mvp", "label": "MVP", "level": "winner", "count": 2},
        {"key": "art-ross", "label": "Art Ross", "level": "winner", "count": 1},
        {"key": "rocket", "label": "Rocket", "level": "winner", "count": 1},
    ]
    goalie_row = next(item for item in body["lineupBreakdown"] if item["slot"] == "G")
    assert goalie_row["teamAbbrev"] == "WSH"
    assert goalie_row["stats"] == {
        "wins": 62,
        "savePercentage": goalie_row["stats"]["savePercentage"],
    }
    assert goalie_row["scorecardTotals"] == {"points": 0, "goals": 0, "assists": 0}
    assert goalie_row["awards"] == [
        {"key": "vezina", "label": "Vezina", "level": "finalist", "count": 1},
    ]


def test_best_lineup_endpoint_returns_optimal_lineup_from_offered_boards(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/best-lineup",
            json={
                "lineup": [
                    {"slot": "C", "candidateKey": "WSH:2000s:104:C"},
                    {"slot": "W", "candidateKey": "WSH:2000s:100:W"},
                    {"slot": "W", "candidateKey": "WSH:2000s:102:W"},
                    {"slot": "D", "candidateKey": "WSH:2000s:103:D"},
                    {"slot": "D", "candidateKey": "COL:1990s:313:D"},
                    {"slot": "G", "candidateKey": "COL:1990s:314:G"},
                ],
                "boards": [
                    {"pairKey": "WSH:2000s", "candidateKeys": ["WSH:2000s:101:C", "WSH:2000s:104:C"]},
                    {"pairKey": "WSH:2000s", "candidateKeys": ["WSH:2000s:100:W", "WSH:2000s:102:W"]},
                    {"pairKey": "WSH:2000s", "candidateKeys": ["WSH:2000s:100:W", "WSH:2000s:102:W"]},
                    {"pairKey": "WSH:2000s", "candidateKeys": ["WSH:2000s:103:D"]},
                    {"pairKey": "COL:1990s", "candidateKeys": ["COL:1990s:313:D"]},
                    {"pairKey": "COL:1990s", "candidateKeys": ["COL:1990s:314:G"]},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["totalScore"] > body["currentTotalScore"]
    assert body["scoreDelta"] > 0
    assert len(body["lineupBreakdown"]) == 6
    assert len({row["playerId"] for row in body["lineupBreakdown"]}) == 6

    center_row = next(item for item in body["lineupBreakdown"] if item["slot"] == "C")
    assert center_row["candidateKey"] == "WSH:2000s:101:C"
    assert center_row["sourceDrawIndex"] == 1

    winger_rows = [item for item in body["lineupBreakdown"] if item["slot"] == "W"]
    assert {row["candidateKey"] for row in winger_rows} == {
        "WSH:2000s:100:W",
        "WSH:2000s:102:W",
    }
    assert {row["sourceDrawIndex"] for row in winger_rows} == {2, 3}


def test_grade_endpoint_rejects_duplicate_players(tmp_path: Path):
    transport = MockHistoricalApi()
    with create_test_client(tmp_path / "cache.sqlite3", transport) as client:
        response = client.post(
            "/api/game/grade",
            json={
                "lineup": [
                    {"slot": "C", "candidateKey": "WSH:2000s:101:C"},
                    {"slot": "W", "candidateKey": "WSH:2000s:100:W"},
                    {"slot": "W", "candidateKey": "WSH:2000s:100:W"},
                    {"slot": "D", "candidateKey": "WSH:2000s:103:D"},
                    {"slot": "D", "candidateKey": "WPG:2000s:203:D"},
                    {"slot": "G", "candidateKey": "WSH:2000s:105:G"},
                ]
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Each player may only be selected once."
