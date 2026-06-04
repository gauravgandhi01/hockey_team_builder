from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

from app.constants import (
    GRADE_BANDS,
    HYBRID_RATES_WEIGHT,
    HYBRID_TOTALS_WEIGHT,
    PROJECTED_OTL,
    RATING_CURVE_EXPONENT,
    RATING_CURVE_FLOOR_RAW,
    RATING_CURVE_HIGH,
    RATING_CURVE_LOW,
    RATING_CURVE_MID,
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


def curve_rating(raw_score: float, top_score: float) -> float:
    raw = max(0.0, min(raw_score, top_score))
    if top_score <= 0:
        return round(RATING_CURVE_LOW, 1)
    if top_score <= RATING_CURVE_FLOOR_RAW:
        return round(
            RATING_CURVE_LOW + (raw / top_score) * (RATING_CURVE_HIGH - RATING_CURVE_LOW),
            1,
        )
    if raw <= RATING_CURVE_FLOOR_RAW:
        return round(
            RATING_CURVE_LOW
            + (raw / RATING_CURVE_FLOOR_RAW) * (RATING_CURVE_MID - RATING_CURVE_LOW),
            1,
        )
    normalized = (raw - RATING_CURVE_FLOOR_RAW) / (top_score - RATING_CURVE_FLOOR_RAW)
    return round(
        RATING_CURVE_MID + (normalized**RATING_CURVE_EXPONENT) * (RATING_CURVE_HIGH - RATING_CURVE_MID),
        1,
    )


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
    scored: dict[str, dict[str, Any]] = {}
    for candidate_key, player in raw_scored.items():
        scored[candidate_key] = {
            **player,
            "score": curve_rating(player["rawScore"], top_raw_score),
        }
    return scored
