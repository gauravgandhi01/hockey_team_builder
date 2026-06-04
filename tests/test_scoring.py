from app.nhl_service import decade_offer_stats, format_season_display, make_candidate_key, parse_candidate_key, primary_position_code, slot_for_position_code
from app.scoring import (
    cross_position_adjust,
    curve_rating,
    map_letter_grade,
    percentile_rank,
    project_record,
    rate_metric_weights,
    rate_metrics,
    rating_tier,
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


def test_curve_rating_spreads_top_end_and_keeps_full_scale():
    assert curve_rating(99.8, 99.8, "C") == 99.0
    assert curve_rating(85.0, 99.8, "C") == 70.0
    assert curve_rating(42.5, 99.8, "C") == 55.0
    assert curve_rating(98.0, 99.8, "C") == 93.6


def test_goalie_curve_softens_dropoff():
    assert curve_rating(95.6, 95.6, "G") == 99.0
    assert curve_rating(86.5, 95.6, "G") == 87.3
    assert curve_rating(82.2, 95.6, "G") == 82.2


def test_cross_position_adjust_preserves_forwards_and_compresses_d_and_g():
    assert cross_position_adjust(93.6, "C") == 93.6
    assert cross_position_adjust(93.6, "W") == 93.6
    assert cross_position_adjust(99.0, "D") == 97.3
    assert cross_position_adjust(97.1, "D") == 95.6
    assert cross_position_adjust(99.0, "G") == 98.2
    assert cross_position_adjust(92.9, "G") == 92.4
    assert cross_position_adjust(84.9, "D") == 84.9


def test_rating_tier_uses_coarse_bands():
    assert rating_tier(99.0) == 1
    assert rating_tier(94.0) == 2
    assert rating_tier(80.0) == 3
    assert rating_tier(60.0) == 4
    assert rating_tier(49.9) == 5


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


def test_defense_time_on_ice_is_rate_only():
    defense_total_weights = totals_metric_weights("D")
    defense_rate_weights = rate_metric_weights("D")
    assert "avgTimeOnIcePerGame" not in defense_total_weights
    assert "avgTimeOnIcePerGame" in defense_rate_weights


def test_defense_time_on_ice_is_excluded_for_pre_2000_decades():
    assert "avgTimeOnIcePerGame" not in totals_metric_weights("D", 1990)
    assert "avgTimeOnIcePerGame" not in rate_metric_weights("D", 1990)
    assert "avgTimeOnIcePerGame" not in totals_metric_weights("D", 2000)
    assert "avgTimeOnIcePerGame" in rate_metric_weights("D", 2000)


def test_defense_offer_stats_omit_toi_when_untracked():
    assert decade_offer_stats(
        {
            "eligibleSlot": "D",
            "stats": {
                "points": 100,
                "assists": 80,
                "shots": 250,
                "avgTimeOnIcePerGame": None,
            },
        }
    ) == {
        "points": 100,
        "assists": 80,
    }


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
    assert scored["AAA:2000s:1:C"]["rawScore"] == 100.0
    assert scored["AAA:2000s:1:C"]["score"] == 99.0
    assert scored["AAA:2000s:1:C"]["overallPercentile"] == 100.0
    assert scored["AAA:2000s:1:C"]["ratingTier"] == 1
    assert scored["AAA:2000s:2:C"]["score"] == 40.0
    assert scored["AAA:2000s:2:C"]["overallPercentile"] == 0.0
    assert scored["AAA:2000s:2:C"]["ratingTier"] == 5
    assert scored["AAA:2000s:1:C"]["totalsScore"] == 100.0
    assert scored["AAA:2000s:1:C"]["rateScore"] == 100.0
    assert scored["AAA:2000s:2:C"]["totalsScore"] == 0.0
    assert scored["AAA:2000s:2:C"]["rateScore"] == 0.0
