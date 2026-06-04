from app.nhl_service import format_season_display, make_candidate_key, parse_candidate_key, primary_position_code, slot_for_position_code
from app.scoring import (
    map_letter_grade,
    percentile_rank,
    project_record,
    rate_metric_weights,
    rate_metrics,
    score_role_players,
    totals_metric_weights,
    totals_metrics,
)


def test_primary_position_code_uses_games_played_and_tie_order():
    assert primary_position_code({"L": 40, "R": 35, "C": 20}) == "L"
    assert primary_position_code({"L": 30, "R": 30}) == "L"


def test_candidate_key_round_trips():
    key = make_candidate_key("WSH:2000s", 8471214, "W")
    assert parse_candidate_key(key) == ("WSH:2000s", 8471214, "W")
    assert parse_candidate_key("bad-key") is None


def test_format_season_display_uses_hockey_style():
    assert format_season_display("20082009") == "2008-09"
    assert format_season_display(19801981) == "1980-81"


def test_slot_for_position_code_collapses_wingers():
    assert slot_for_position_code("C") == "C"
    assert slot_for_position_code("L") == "W"
    assert slot_for_position_code("R") == "W"
    assert slot_for_position_code("D") == "D"
    assert slot_for_position_code("G") == "G"


def test_percentile_rank_uses_average_rank_for_ties():
    values = [0, 10, 10, 30]
    assert percentile_rank(values, 10) == 0.5


def test_map_letter_grade_uses_expected_bands():
    assert map_letter_grade(95.0) == "A+"
    assert map_letter_grade(82.4) == "B+"
    assert map_letter_grade(39.9) == "F"


def test_project_record_uses_simple_hockey_projection():
    assert project_record(100.0) == {
        "wins": 58,
        "losses": 16,
        "overtimeLosses": 8,
        "display": "58-16-8",
    }


def test_rate_metrics_use_per_game_counts():
    stats = {"gamesPlayed": 50, "points": 100, "assists": 50, "goals": 25, "shots": 200}
    metrics = rate_metrics("C", stats)
    assert metrics["points"] == 2.0
    assert metrics["assists"] == 1.0
    assert metrics["goals"] == 0.5
    assert metrics["shots"] == 4.0


def test_rate_metric_weights_renormalize_after_metric_cleanup():
    weights = rate_metric_weights("C")
    assert round(sum(weights.values()), 5) == 1.0


def test_role_metric_weights_do_not_include_plus_minus():
    winger_total_weights = totals_metric_weights("W")
    defense_total_weights = totals_metric_weights("D")
    winger_weights = rate_metric_weights("W")
    defense_weights = rate_metric_weights("D")
    assert "plusMinus" not in winger_total_weights
    assert "plusMinus" not in defense_total_weights
    assert "plusMinus" not in winger_weights
    assert "plusMinus" not in defense_weights


def test_totals_metric_weights_drop_goalie_efficiency_metrics():
    goalie_totals_weights = totals_metric_weights("G")
    assert "savePercentage" not in goalie_totals_weights
    assert "goalsAgainstAverageInverse" not in goalie_totals_weights


def test_totals_metrics_keep_goalie_counting_values_only():
    goalie_totals = totals_metrics(
        "G",
        {"gamesPlayed": 120, "wins": 70, "shutouts": 10, "savePercentage": 0.921, "goalsAgainstAverage": 2.5},
    )
    assert goalie_totals["wins"] == 70.0
    assert goalie_totals["shutouts"] == 10.0
    assert "savePercentage" not in goalie_totals
    assert "goalsAgainstAverageInverse" not in goalie_totals


def test_rate_metrics_keep_goalie_efficiency_metrics_once():
    goalie_rates = rate_metrics(
        "G",
        {"gamesPlayed": 120, "wins": 70, "shutouts": 10, "savePercentage": 0.921, "goalsAgainstAverage": 2.5},
    )
    assert goalie_rates["wins"] == 70 / 120
    assert goalie_rates["shutouts"] == 10 / 120
    assert goalie_rates["savePercentage"] == 0.921
    assert goalie_rates["goalsAgainstAverageInverse"] == 0.4


def test_score_role_players_builds_hybrid_scores():
    players = [
        {
            "candidateKey": "AAA:2000s:1:C",
            "playerId": 1,
            "fullName": "Player One",
            "stats": {"gamesPlayed": 100, "points": 120, "assists": 70, "goals": 40, "shots": 260},
            "totalsMetrics": totals_metrics("C", {"gamesPlayed": 100, "points": 120, "assists": 70, "goals": 40, "shots": 260}),
            "rateMetrics": rate_metrics("C", {"gamesPlayed": 100, "points": 120, "assists": 70, "goals": 40, "shots": 260}),
        },
        {
            "candidateKey": "AAA:2000s:2:C",
            "playerId": 2,
            "fullName": "Player Two",
            "stats": {"gamesPlayed": 120, "points": 84, "assists": 42, "goals": 21, "shots": 180},
            "totalsMetrics": totals_metrics("C", {"gamesPlayed": 120, "points": 84, "assists": 42, "goals": 21, "shots": 180}),
            "rateMetrics": rate_metrics("C", {"gamesPlayed": 120, "points": 84, "assists": 42, "goals": 21, "shots": 180}),
        },
    ]

    scored = score_role_players("C", players)
    assert scored["AAA:2000s:1:C"]["score"] > scored["AAA:2000s:2:C"]["score"]
    assert scored["AAA:2000s:1:C"]["totalsScore"] == 100.0
    assert scored["AAA:2000s:1:C"]["rateScore"] == 100.0
    assert scored["AAA:2000s:2:C"]["totalsScore"] == 0.0
    assert scored["AAA:2000s:2:C"]["rateScore"] == 0.0
