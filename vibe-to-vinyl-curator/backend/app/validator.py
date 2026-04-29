from statistics import mean

from .models import ArcStage, Intent, SongRecommendation, ValidationIssue, ValidationReport


def validate_playlist(
    intent: Intent,
    stages: list[ArcStage],
    grouped: dict[str, list[SongRecommendation]],
    allow_explicit: bool,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    all_recs = [rec for songs in grouped.values() for rec in songs]

    if not all_recs:
        issues.append(ValidationIssue(severity="error", message="No songs were selected."))
        return ValidationReport(passed=False, issues=issues, metrics={"song_count": 0})

    ids = [rec.song.id for rec in all_recs]
    if len(ids) != len(set(ids)):
        issues.append(ValidationIssue(severity="error", message="Playlist contains duplicate songs."))

    for stage in stages:
        count = len(grouped.get(stage.name, []))
        if count < stage.song_count:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Stage '{stage.name}' requested {stage.song_count} songs but selected {count}.",
                )
            )

    if not allow_explicit and any(rec.song.explicit for rec in all_recs):
        issues.append(ValidationIssue(severity="error", message="Explicit song selected despite clean constraint."))

    mood_hits = sum(bool(set(intent.target_moods).intersection(rec.song.mood_tags)) for rec in all_recs)
    mood_coverage = mood_hits / len(all_recs)
    if mood_coverage < 0.45:
        issues.append(ValidationIssue(severity="warning", message="Low coverage of requested mood tags."))

    energies = [rec.song.energy for rec in all_recs]
    transition_spikes = sum(
        1 for left, right in zip(energies, energies[1:]) if abs(right - left) > 0.45
    )
    if transition_spikes:
        issues.append(ValidationIssue(severity="info", message=f"{transition_spikes} high-contrast energy transition(s) detected."))

    average_score = mean(rec.match_score for rec in all_recs)
    metrics = {
        "song_count": len(all_recs),
        "average_match_score": round(average_score, 3),
        "mood_coverage": round(mood_coverage, 3),
        "average_energy": round(mean(energies), 3),
        "transition_spikes": transition_spikes,
    }
    passed = not any(issue.severity == "error" for issue in issues)
    return ValidationReport(passed=passed, issues=issues, metrics=metrics)


def confidence_from_report(report: ValidationReport) -> float:
    base = float(report.metrics.get("average_match_score", 0.5))
    coverage = float(report.metrics.get("mood_coverage", 0.0))
    penalty = 0.08 * sum(issue.severity == "warning" for issue in report.issues)
    penalty += 0.2 * sum(issue.severity == "error" for issue in report.issues)
    return round(max(0.0, min(1.0, (base * 0.65) + (coverage * 0.35) - penalty)), 3)
