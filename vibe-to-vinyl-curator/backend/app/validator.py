"""Critic agent and guardrail validation for generated playlists."""

from statistics import mean

from .models import (
    ParsedIntent,
    PlaylistStage,
    SongRecommendation,
    ValidationIssue,
    ValidationReport,
)
from .sequencer import calculate_transition_smoothness


def validate_playlist(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    plan: list[PlaylistStage],
) -> ValidationReport:
    """Validate a playlist against mood, transition, duration, and constraints."""
    warnings: list[str] = []

    mood_match = calculate_mood_match(recommendations)
    transition_smoothness = calculate_transition_smoothness(recommendations)
    duration_accuracy = calculate_duration_accuracy(recommendations, intent, warnings)
    constraint_satisfaction = calculate_constraint_satisfaction(
        recommendations=recommendations,
        intent=intent,
        plan=plan,
        warnings=warnings,
    )
    warnings.extend(_stage_quality_warnings(recommendations, plan))

    overall_confidence = round(
        (0.35 * mood_match)
        + (0.25 * transition_smoothness)
        + (0.20 * duration_accuracy)
        + (0.20 * constraint_satisfaction),
        3,
    )
    passed = overall_confidence >= 0.70 and constraint_satisfaction >= 0.80

    issues = [
        ValidationIssue(severity="warning", message=warning)
        for warning in warnings
    ]
    metrics = {
        "song_count": len(recommendations),
        "total_duration_minutes": round(_total_duration_minutes(recommendations), 1),
        "mood_match": mood_match,
        "transition_smoothness": transition_smoothness,
        "duration_accuracy": duration_accuracy,
        "constraint_satisfaction": constraint_satisfaction,
        "overall_confidence": overall_confidence,
    }

    return ValidationReport(
        mood_match=mood_match,
        transition_smoothness=transition_smoothness,
        duration_accuracy=duration_accuracy,
        constraint_satisfaction=constraint_satisfaction,
        overall_confidence=overall_confidence,
        warnings=warnings,
        passed=passed,
        issues=issues,
        metrics=metrics,
    )


def needs_revision(report: ValidationReport) -> bool:
    """Return True when critic metrics indicate the playlist needs revision."""
    return (
        report.overall_confidence < 0.70
        or report.constraint_satisfaction < 0.80
        or report.duration_accuracy < 0.60
    )


def confidence_from_report(report: ValidationReport) -> float:
    """Return the canonical confidence score for endpoint responses."""
    return report.overall_confidence


def calculate_mood_match(recommendations: list[SongRecommendation]) -> float:
    """Average recommendation match scores, bounded to 0-1."""
    if not recommendations:
        return 0.0
    average_score = mean(rec.match_score for rec in recommendations)
    return round(max(0.0, min(1.0, average_score)), 3)


def calculate_duration_accuracy(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    warnings: list[str],
) -> float:
    """Score how close total duration is to the requested target duration."""
    if intent.target_duration_minutes is None:
        return 1.0

    actual_minutes = _total_duration_minutes(recommendations)
    target_minutes = float(intent.target_duration_minutes)
    difference = actual_minutes - target_minutes
    absolute_difference = abs(difference)

    if absolute_difference > 0.5:
        direction = "longer" if difference > 0 else "shorter"
        warnings.append(
            f"Playlist is {round(absolute_difference)} minutes {direction} than requested."
        )

    tolerance = target_minutes * 0.10
    if absolute_difference <= tolerance:
        return 1.0

    # After the 10 percent tolerance, accuracy falls off linearly against target.
    excess_difference = absolute_difference - tolerance
    score = 1.0 - (excess_difference / target_minutes)
    return round(max(0.0, min(1.0, score)), 3)


def calculate_constraint_satisfaction(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    plan: list[PlaylistStage],
    warnings: list[str],
) -> float:
    """Score hard and soft guardrail satisfaction from 0 to 1."""
    checks = [
        _explicit_content_check(recommendations, intent, warnings),
        _lyrics_check(recommendations, intent, warnings),
        _loudness_check(recommendations, intent, warnings),
        _stage_coverage_check(recommendations, plan, warnings),
    ]
    return round(mean(checks), 3)


def _explicit_content_check(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    warnings: list[str],
) -> float:
    """Return 0 if explicit songs violate a clean-content constraint."""
    if intent.allow_explicit:
        return 1.0
    explicit_count = sum(rec.song.explicit for rec in recommendations)
    if explicit_count:
        warnings.append("Explicit songs were found despite a clean-content preference.")
        return 0.0
    return 1.0


def _lyrics_check(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    warnings: list[str],
) -> float:
    """Penalize medium/high lyrical content when lyrics should be avoided."""
    if not intent.avoid_lyrics:
        return 1.0

    lyrical_count = sum(
        rec.song.lyrics_level in {"medium", "high"} for rec in recommendations
    )
    if not lyrical_count:
        return 1.0

    warnings.append(
        "Some songs have medium lyrical content despite a no-lyrics preference."
    )
    ratio = lyrical_count / max(len(recommendations), 1)
    return round(max(0.0, 1.0 - ratio), 3)


def _loudness_check(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
    warnings: list[str],
) -> float:
    """Penalize high-energy songs when the user asked for lower loudness."""
    if not _has_not_too_loud_constraint(intent):
        return 1.0

    loud_count = sum(rec.song.energy > 0.70 for rec in recommendations)
    if not loud_count:
        return 1.0

    warnings.append("Some songs may be too energetic for the not-too-loud constraint.")
    ratio = loud_count / max(len(recommendations), 1)
    return round(max(0.0, 1.0 - ratio), 3)


def _stage_coverage_check(
    recommendations: list[SongRecommendation],
    plan: list[PlaylistStage],
    warnings: list[str],
) -> float:
    """Ensure every planned stage receives at least one selected song."""
    if not plan:
        return 1.0

    stages_with_songs = {
        rec.stage_name or rec.stage
        for rec in recommendations
    }
    missing = [stage.name for stage in plan if stage.name not in stages_with_songs]
    for stage_name in missing:
        warnings.append(f"No songs were selected for the {stage_name} stage.")
    return round((len(plan) - len(missing)) / len(plan), 3)


def _stage_quality_warnings(
    recommendations: list[SongRecommendation],
    plan: list[PlaylistStage],
) -> list[str]:
    """Warn when a stage has too few or low-confidence recommendations."""
    warnings: list[str] = []
    for stage in plan:
        stage_recs = [
            rec for rec in recommendations if (rec.stage_name or rec.stage) == stage.name
        ]
        if not stage_recs:
            continue
        average_match = mean(rec.match_score for rec in stage_recs)
        if average_match < 0.55:
            warnings.append(
                f"Not enough high-confidence songs were found for the {stage.target_mood} stage."
            )
    return warnings


def _total_duration_minutes(recommendations: list[SongRecommendation]) -> float:
    """Return playlist duration in minutes."""
    return sum(rec.song.duration_seconds for rec in recommendations) / 60


def _has_not_too_loud_constraint(intent: ParsedIntent) -> bool:
    """Return True if user requested a controlled or lower-energy playlist."""
    constraints = {constraint.lower() for constraint in intent.constraints}
    return "not too loud" in constraints or "lower energy preferred" in constraints
