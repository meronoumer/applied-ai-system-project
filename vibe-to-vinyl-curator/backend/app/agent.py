"""Main agentic workflow for deterministic playlist curation."""

import logging

from .data_loader import load_songs
from .models import (
    AgentTraceStep,
    CurateRequest,
    CurateResponse,
    EvaluateRequest,
    EvaluateResponse,
    ParsedIntent,
    PlaylistStage,
    Song,
    SongRecommendation,
    ValidationIssue,
    ValidationReport,
)
from .parser import parse_user_prompt
from .planner import plan_arc
from .retriever import retrieve_candidates
from .selector import select_songs_for_plan
from .sequencer import flatten_playlist, sequence_playlist
from .validator import confidence_from_report, needs_revision, validate_playlist

logger = logging.getLogger(__name__)


def curate_playlist(request: CurateRequest, songs: list[Song]) -> CurateResponse:
    """Run the full parser-planner-selector-critic workflow for one request."""
    trace: list[AgentTraceStep] = []

    intent = parse_user_prompt(
        prompt=request.prompt,
        target_duration_minutes=request.target_duration_minutes,
        allow_explicit=request.allow_explicit,
    )
    trace.append(
        AgentTraceStep(
            step="parser",
            summary="Extracted duration, moods, occasion, and constraints.",
            details={
                "target_duration_minutes": intent.target_duration_minutes,
                "occasion": intent.occasion,
                "moods": [intent.start_mood, intent.middle_mood, intent.end_mood],
                "constraints": intent.constraints,
            },
        )
    )

    plan = plan_arc(intent, request.max_songs)
    trace.append(
        AgentTraceStep(
            step="planner",
            summary="Created a 3-stage emotional playlist arc.",
            details={"stage_names": [stage.name for stage in plan]},
        )
    )

    if not songs:
        report = _empty_catalog_report()
        trace.append(
            AgentTraceStep(
                step="retriever",
                summary="No songs were available in the local database.",
                details={"candidate_counts": {}},
            )
        )
        trace.append(
            AgentTraceStep(
                step="critic",
                summary="Returned empty playlist because the song catalog is empty.",
                details=report.model_dump(),
            )
        )
        return _build_response(intent, plan, [], report, trace)

    candidate_counts = _candidate_counts(songs, plan, intent)
    trace.append(
        AgentTraceStep(
            step="retriever",
            summary="Retrieved candidate songs for each stage.",
            details={"candidate_counts": candidate_counts},
        )
    )

    selected = select_songs_for_plan(
        songs=songs,
        plan=plan,
        intent=intent,
        max_songs=request.max_songs,
    )
    trace.append(
        AgentTraceStep(
            step="selector",
            summary=f"Selected {len(selected)} songs across the planned stages.",
            details={"selected_ids": [rec.song.id for rec in selected]},
        )
    )

    sequenced = sequence_playlist(selected)
    trace.append(
        AgentTraceStep(
            step="sequencer",
            summary="Ordered songs by stage and energy smoothness.",
            details={"ordered_ids": [rec.song.id for rec in sequenced]},
        )
    )

    report = validate_playlist(sequenced, intent, plan)
    trace.append(
        AgentTraceStep(
            step="critic",
            summary="Computed validation scores for mood, transitions, duration, and constraints.",
            details=_report_summary(report),
        )
    )

    if needs_revision(report):
        sequenced, report, revision_summary = _revise_once(
            recommendations=sequenced,
            songs=songs,
            plan=plan,
            intent=intent,
            max_songs=request.max_songs,
        )
        trace.append(
            AgentTraceStep(
                step="revision",
                summary=revision_summary,
                details=_report_summary(report),
            )
        )
    else:
        trace.append(
            AgentTraceStep(
                step="revision",
                summary="No revision was needed after validation.",
                details={"changed": False},
            )
        )

    logger.info(
        "curation_complete confidence=%s songs=%s",
        confidence_from_report(report),
        len(sequenced),
    )
    return _build_response(intent, plan, sequenced, report, trace)


def evaluate_playlist(request: EvaluateRequest) -> EvaluateResponse:
    """Evaluate supplied song ids against a prompt-derived playlist plan."""
    songs_by_id = {song.id: song for song in load_songs()}
    intent = parse_user_prompt(
        prompt=request.prompt,
        target_duration_minutes=None,
        allow_explicit=request.allow_explicit,
    )
    stages = plan_arc(intent, max(3, min(len(request.song_ids), 24)))
    trace = [
        AgentTraceStep(
            step="parser",
            summary="Parsed evaluation prompt into structured intent.",
            details=intent.model_dump(),
        ),
        AgentTraceStep(
            step="planner",
            summary="Built expected arc for evaluation.",
            details={"stages": [stage.model_dump() for stage in stages]},
        ),
    ]

    missing = [song_id for song_id in request.song_ids if song_id not in songs_by_id]
    if missing:
        trace.append(
            AgentTraceStep(
                step="critic",
                summary="Rejected playlist because unknown song ids were supplied.",
                details={"missing_ids": missing},
            )
        )
        report = validate_playlist([], intent, stages)
        report.issues.append(
            ValidationIssue(severity="error", message=f"Unknown song ids: {missing}")
        )
        report.warnings.append(f"Unknown song ids: {missing}")
        report.constraint_satisfaction = 0.0
        report.overall_confidence = 0.0
        report.metrics["constraint_satisfaction"] = 0.0
        report.metrics["overall_confidence"] = 0.0
        report.passed = False
        return EvaluateResponse(
            parsed_intent=intent,
            validation_report=report,
            confidence_score=0.0,
            agent_trace=trace,
        )

    grouped = {stage.name: [] for stage in stages}
    for index, song_id in enumerate(request.song_ids):
        stage = stages[min(index * len(stages) // len(request.song_ids), len(stages) - 1)]
        song = songs_by_id[song_id]
        grouped[stage.name].append(
            SongRecommendation(
                song=song,
                stage_name=stage.name,
                stage=stage.name,
                match_score=0.7 if set(song.mood_tags).intersection(stage.target_moods) else 0.35,
                reason=f"Evaluated against '{stage.name}' using deterministic mood and energy checks.",
                explanation=f"Evaluated against '{stage.name}' using deterministic mood and energy checks.",
            )
        )

    report = validate_playlist(flatten_playlist(grouped), intent, stages)
    confidence = confidence_from_report(report)
    trace.append(
        AgentTraceStep(
            step="critic",
            summary="Validated supplied playlist ids.",
            details=report.model_dump(),
        )
    )
    return EvaluateResponse(
        parsed_intent=intent,
        validation_report=report,
        confidence_score=confidence,
        agent_trace=trace,
    )


def _revise_once(
    recommendations: list[SongRecommendation],
    songs: list[Song],
    plan: list[PlaylistStage],
    intent: ParsedIntent,
    max_songs: int,
) -> tuple[list[SongRecommendation], ValidationReport, str]:
    """Attempt one deterministic revision pass, then re-run validation."""
    revised = _remove_constraint_violations(recommendations, intent)
    used_ids = {rec.song.id for rec in revised}
    changed = len(revised) != len(recommendations)

    if _duration_too_short(revised, intent) and len(revised) < max_songs:
        added = _add_high_scoring_unused_songs(
            current=revised,
            used_ids=used_ids,
            songs=songs,
            plan=plan,
            intent=intent,
            max_songs=max_songs,
        )
        revised.extend(added)
        changed = changed or bool(added)

    revised = sequence_playlist(revised)
    report = validate_playlist(revised, intent, plan)

    if changed:
        summary = "Adjusted songs, resequenced the playlist, and re-ran validation."
    else:
        summary = "Resequenced the playlist and re-ran validation; no replacement candidates were available."
    return revised, report, summary


def _remove_constraint_violations(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
) -> list[SongRecommendation]:
    """Remove songs that directly violate explicit, lyric, or loudness constraints."""
    kept: list[SongRecommendation] = []
    for rec in recommendations:
        if rec.song.explicit and not intent.allow_explicit:
            continue
        if intent.avoid_lyrics and rec.song.lyrics_level in {"medium", "high"}:
            continue
        if _has_not_too_loud_constraint(intent) and rec.song.energy > 0.70:
            continue
        kept.append(rec)
    return kept


def _add_high_scoring_unused_songs(
    current: list[SongRecommendation],
    used_ids: set[int],
    songs: list[Song],
    plan: list[PlaylistStage],
    intent: ParsedIntent,
    max_songs: int,
) -> list[SongRecommendation]:
    """Add high-scoring songs that are not already in the playlist."""
    additions: list[SongRecommendation] = []
    for stage in plan:
        if len(current) + len(additions) >= max_songs:
            break
        candidates = retrieve_candidates(songs, stage, intent, top_k=24)
        for song, score in candidates:
            if song.id in used_ids:
                continue
            additions.append(
                SongRecommendation(
                    song=song,
                    stage_name=stage.name,
                    stage=stage.name,
                    match_score=round(score, 3),
                    reason=f"Added during revision for stronger {stage.target_mood} coverage and duration fit.",
                    explanation=f"Added during revision for stronger {stage.target_mood} coverage and duration fit.",
                )
            )
            used_ids.add(song.id)
            break
    return additions


def _candidate_counts(
    songs: list[Song],
    plan: list[PlaylistStage],
    intent: ParsedIntent,
) -> dict[str, int]:
    """Count retrievable candidates by stage for trace visibility."""
    return {
        stage.name: len(retrieve_candidates(songs, stage, intent, top_k=1000))
        for stage in plan
    }


def _build_response(
    intent: ParsedIntent,
    plan: list[PlaylistStage],
    recommendations: list[SongRecommendation],
    report: ValidationReport,
    trace: list[AgentTraceStep],
) -> CurateResponse:
    """Create the endpoint response in the expected grouped format."""
    return CurateResponse(
        parsed_intent=intent,
        playlist_arc=plan,
        selected_songs_by_stage=_group_by_stage(recommendations, plan),
        validation_report=report,
        confidence_score=confidence_from_report(report),
        agent_trace=trace,
    )


def _report_summary(report: ValidationReport) -> dict[str, float | bool | list[str]]:
    """Return compact validation metrics for the visible agent trace."""
    return {
        "mood_match": report.mood_match,
        "transition_smoothness": report.transition_smoothness,
        "duration_accuracy": report.duration_accuracy,
        "constraint_satisfaction": report.constraint_satisfaction,
        "overall_confidence": report.overall_confidence,
        "passed": report.passed,
        "warnings": report.warnings,
    }


def _group_by_stage(
    recommendations: list[SongRecommendation],
    plan: list[PlaylistStage],
) -> dict[str, list[SongRecommendation]]:
    """Group recommendations by planned stage order."""
    grouped = {stage.name: [] for stage in plan}
    for rec in recommendations:
        stage_name = rec.stage_name or rec.stage
        grouped.setdefault(stage_name, []).append(rec)
    return grouped


def _empty_catalog_report() -> ValidationReport:
    """Create a validation report for an unavailable or empty song catalog."""
    warning = "No songs could be found in the local database."
    return ValidationReport(
        mood_match=0.0,
        transition_smoothness=0.0,
        duration_accuracy=0.0,
        constraint_satisfaction=0.0,
        overall_confidence=0.0,
        warnings=[warning],
        passed=False,
        issues=[ValidationIssue(severity="error", message=warning)],
        metrics={"song_count": 0},
    )


def _duration_too_short(
    recommendations: list[SongRecommendation],
    intent: ParsedIntent,
) -> bool:
    """Return True when playlist duration is materially below requested duration."""
    if intent.target_duration_minutes is None:
        return False
    actual_minutes = sum(rec.song.duration_seconds for rec in recommendations) / 60
    return actual_minutes < intent.target_duration_minutes * 0.90


def _has_not_too_loud_constraint(intent: ParsedIntent) -> bool:
    """Return True when the prompt requested lower energy."""
    constraints = {constraint.lower() for constraint in intent.constraints}
    return "not too loud" in constraints or "lower energy preferred" in constraints
