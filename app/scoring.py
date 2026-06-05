from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

from app.constants import (
    CROSS_POSITION_CALIBRATION_FLOOR,
    GRADE_BANDS,
    GOALIE_RATING_CURVE_EXPONENT,
    GOALIE_RATING_CURVE_FLOOR_RAW,
    GOALIE_RATING_CURVE_HIGH,
    GOALIE_RATING_CURVE_LOW,
    GOALIE_RATING_CURVE_MID,
    HYBRID_RATES_WEIGHT,
    HYBRID_TOTALS_WEIGHT,
    PROJECTED_OTL,
    RATING_TIER_PERCENTILE_BANDS,
    RATING_CURVE_EXPONENT,
    RATING_CURVE_FLOOR_RAW,
    RATING_CURVE_HIGH,
    RATING_CURVE_LOW,
    RATING_CURVE_MID,
    SELKE_BONUS_BASE,
    SELKE_BONUS_CAP,
    SELKE_BONUS_GROWTH,
    ROLE_SCORE_ADJUST_FACTORS,
    ROLE_CONFIG,
)

PER_GAME_METRICS = {
    "points",
    "assists",
    "goals",
    "shots",
    "wins",
    "shutouts",
}

TOTALS_METRIC_EXCLUSIONS = {
    "D": {"avgTimeOnIcePerGame"},
    "G": {"savePercentage", "goalsAgainstAverageInverse"},
}


def decade_metric_exclusions(role: str, decade_start: int | None = None) -> set[str]:
    exclusions: set[str] = set()
    if role == "D" and decade_start is not None and decade_start < 2000:
        exclusions.add("avgTimeOnIcePerGame")
    return exclusions


def map_letter_grade(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def rating_tier(percentile: float) -> int:
    for threshold, tier in RATING_TIER_PERCENTILE_BANDS:
        if percentile >= threshold:
            return tier
    return RATING_TIER_PERCENTILE_BANDS[-1][1]


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def project_record(total_score: float) -> dict[str, Any]:
    wins = clamp(round(14 + total_score * 0.44), 14, 58)
    overtime_losses = PROJECTED_OTL
    losses = 82 - wins - overtime_losses
    return {
        "wins": wins,
        "losses": losses,
        "overtimeLosses": overtime_losses,
        "display": f"{wins}-{losses}-{overtime_losses}",
    }


def curve_rating(raw_score: float, top_score: float, role: str | None = None) -> float:
    if role == "G":
        floor = GOALIE_RATING_CURVE_FLOOR_RAW
        low = GOALIE_RATING_CURVE_LOW
        mid = GOALIE_RATING_CURVE_MID
        high = GOALIE_RATING_CURVE_HIGH
        exponent = GOALIE_RATING_CURVE_EXPONENT
    else:
        floor = RATING_CURVE_FLOOR_RAW
        low = RATING_CURVE_LOW
        mid = RATING_CURVE_MID
        high = RATING_CURVE_HIGH
        exponent = RATING_CURVE_EXPONENT

    raw = max(0.0, min(raw_score, top_score))
    if top_score <= 0:
        return round(low, 1)
    if top_score <= floor:
        return round(
            low + (raw / top_score) * (high - low),
            1,
        )
    if raw <= floor:
        return round(
            low
            + (raw / floor) * (mid - low),
            1,
        )
    normalized = (raw - floor) / (top_score - floor)
    return round(
        mid + (normalized**exponent) * (high - mid),
        1,
    )


def cross_position_adjust(score: float, role: str) -> float:
    factor = ROLE_SCORE_ADJUST_FACTORS.get(role, 1.0)
    if score <= CROSS_POSITION_CALIBRATION_FLOOR or factor == 1.0:
        return round(score, 1)
    return round(
        CROSS_POSITION_CALIBRATION_FLOOR
        + (score - CROSS_POSITION_CALIBRATION_FLOOR) * factor,
        1,
    )


def selke_bonus(awards: list[dict[str, Any]] | None) -> float:
    if not awards:
        return 0.0
    wins = next(
        (
            int(award.get("count") or 0)
            for award in awards
            if award.get("key") == "selke" and award.get("level") == "winner"
        ),
        0,
    )
    if wins <= 0:
        return 0.0

    bonus = 0.0
    for index in range(wins):
        bonus += SELKE_BONUS_BASE * (SELKE_BONUS_GROWTH**index)
        if bonus >= SELKE_BONUS_CAP:
            return round(SELKE_BONUS_CAP, 1)
    return round(min(bonus, SELKE_BONUS_CAP), 1)


def percentile_rank(values: list[float], target: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return 1.0
    left = bisect_left(ordered, target)
    right = bisect_right(ordered, target)
    average_rank = (left + right - 1) / 2
    return average_rank / (len(ordered) - 1)


def _inverse_goals_against_average(stats: dict[str, Any]) -> float:
    gaa = float(stats.get("goalsAgainstAverage") or 0)
    return 1.0 / gaa if gaa > 0 else 0.0


def _normalized_metric_weights(role: str, excluded_metrics: set[str] | None = None) -> dict[str, float]:
    filtered = {
        metric: weight
        for metric, weight in ROLE_CONFIG[role]["weights"].items()
        if metric not in (excluded_metrics or set())
    }
    total_weight = sum(filtered.values())
    if total_weight <= 0:
        return {}
    return {metric: weight / total_weight for metric, weight in filtered.items()}


def totals_metric_weights(role: str, decade_start: int | None = None) -> dict[str, float]:
    return _normalized_metric_weights(
        role,
        set(TOTALS_METRIC_EXCLUSIONS.get(role, set())) | decade_metric_exclusions(role, decade_start),
    )


def totals_metrics(role: str, stats: dict[str, Any] | None, decade_start: int | None = None) -> dict[str, float]:
    raw_stats = stats or {}
    totals: dict[str, float] = {}
    for metric in totals_metric_weights(role, decade_start):
        if metric == "goalsAgainstAverageInverse":
            totals[metric] = _inverse_goals_against_average(raw_stats)
        else:
            totals[metric] = float(raw_stats.get(metric) or 0)
    return totals


def rate_metric_weights(role: str, decade_start: int | None = None) -> dict[str, float]:
    return _normalized_metric_weights(role, decade_metric_exclusions(role, decade_start))


def rate_metrics(role: str, stats: dict[str, Any] | None, decade_start: int | None = None) -> dict[str, float]:
    raw_stats = stats or {}
    games_played = float(raw_stats.get("gamesPlayed") or 0)
    rates: dict[str, float] = {}
    for metric in rate_metric_weights(role, decade_start):
        if metric == "goalsAgainstAverageInverse":
            rates[metric] = _inverse_goals_against_average(raw_stats)
        elif metric in PER_GAME_METRICS:
            raw_value = float(raw_stats.get(metric) or 0)
            rates[metric] = raw_value / games_played if games_played > 0 else 0.0
        else:
            rates[metric] = float(raw_stats.get(metric) or 0)
    return rates


def _weighted_percentile_scores(
    weights: dict[str, float],
    metric_values: dict[str, list[float]],
    player_metrics: dict[str, float],
) -> tuple[dict[str, float], float]:
    percentiles = {
        metric: percentile_rank(metric_values[metric], player_metrics[metric])
        for metric in weights
    }
    score = sum(weights[metric] * percentiles[metric] * 100 for metric in weights)
    rounded = {metric: round(percentiles[metric] * 100, 1) for metric in weights}
    return rounded, round(score, 1)


def score_role_players(
    role: str,
    players: list[dict[str, Any]],
    decade_start: int | None = None,
) -> dict[str, dict[str, Any]]:
    total_weights = totals_metric_weights(role, decade_start)
    rate_weights = rate_metric_weights(role, decade_start)

    totals_values = {
        metric: [player["totalsMetrics"][metric] for player in players]
        for metric in total_weights
    }
    rate_values = {
        metric: [player["rateMetrics"][metric] for player in players]
        for metric in rate_weights
    }

    raw_scored: dict[str, dict[str, Any]] = {}
    for player in players:
        total_percentiles, total_score = _weighted_percentile_scores(
            total_weights,
            totals_values,
            player["totalsMetrics"],
        )
        rate_percentiles, rate_score = _weighted_percentile_scores(
            rate_weights,
            rate_values,
            player["rateMetrics"],
        )
        raw_score = round(
            HYBRID_TOTALS_WEIGHT * total_score + HYBRID_RATES_WEIGHT * rate_score,
            1,
        )
        raw_scored[player["candidateKey"]] = {
            **player,
            "totalsPercentiles": total_percentiles,
            "ratePercentiles": rate_percentiles,
            "totalsScore": total_score,
            "rateScore": rate_score,
            "rawScore": raw_score,
        }

    top_raw_score = max((player["rawScore"] for player in raw_scored.values()), default=0.0)
    raw_score_values = [player["rawScore"] for player in raw_scored.values()]
    scored: dict[str, dict[str, Any]] = {}
    for candidate_key, player in raw_scored.items():
        overall_percentile = round(percentile_rank(raw_score_values, player["rawScore"]) * 100, 1)
        curved_score = curve_rating(player["rawScore"], top_raw_score, role)
        calibrated_score = cross_position_adjust(curved_score, role)
        award_bonus = selke_bonus(player.get("awards"))
        scored[candidate_key] = {
            **player,
            "overallPercentile": overall_percentile,
            "ratingTier": rating_tier(overall_percentile),
            "curveScore": round(curved_score, 1),
            "calibratedScore": round(calibrated_score, 1),
            "awardBonus": award_bonus,
            "score": round(min(99.0, calibrated_score + award_bonus), 1),
        }
    return scored
