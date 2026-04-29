import logging

from .data_loader import load_songs
from .models import (
    AgentTraceStep,
    CurateResponse,
    EvaluateResponse,
    EvaluateRequest,
    CurateRequest,
    SongRecommendation,
    ValidationIssue,
)
from .parser import parse_user_prompt
from .planner import plan_arc
from .retriever import retrieve_candidates
from .selector import select_songs
from .sequencer import flatten_playlist, sequence_stage
from .validator import confidence_from_report, needs_revision, validate_playlist

logger = logging.getLogger(__name__)


def curate_playlist(request: CurateRequest) -> CurateResponse:
    trace: list[AgentTraceStep] = []
    songs = load_songs()
    intent = parse_user_prompt(
        prompt=request.prompt,
        target_duration_minutes=request.target_duration_minutes,
        allow_explicit=request.allow_explicit,
    )
    trace.append(AgentTraceStep(step="parser", summary="Parsed natural language prompt into structured intent.", details=intent.model_dump()))

    stages = plan_arc(intent, request.max_songs)
    trace.append(AgentTraceStep(step="planner", summary="Created a three-stage playlist arc.", details={"stages": [stage.model_dump() for stage in stages]}))

    grouped: dict[str, list[SongRecommendation]] = {}
    used_song_ids: set[int] = set()
    retrieval_counts: dict[str, int] = {}

    for stage in stages:
        candidates = retrieve_candidates(songs, stage, intent)
        retrieval_counts[stage.name] = len(candidates)
        trace.append(
            AgentTraceStep(
                step="retriever",
                summary=f"Retrieved candidates for stage '{stage.name}'.",
                details={"stage": stage.name, "candidate_ids": [song.id for song, _ in candidates[:8]]},
            )
        )
        selected = select_songs(stage, candidates, used_song_ids)
        grouped[stage.name] = sequence_stage(selected)
        trace.append(
            AgentTraceStep(
                step="selector",
                summary=f"Selected and sequenced songs for stage '{stage.name}'.",
                details={"stage": stage.name, "selected_ids": [rec.song.id for rec in grouped[stage.name]]},
            )
        )

    all_recommendations = flatten_playlist(grouped)
    report = validate_playlist(all_recommendations, intent, stages)
    trace.append(AgentTraceStep(step="critic", summary="Validated playlist against safety, diversity, fit, and structure checks.", details=report.model_dump()))

    if needs_revision(report):
        trace.append(
            AgentTraceStep(
                step="revision",
                summary="Revision is recommended by the critic; warnings are surfaced for user review.",
                details={"retrieval_counts": retrieval_counts},
            )
        )
    else:
        trace.append(AgentTraceStep(step="revision", summary="Playlist passed checks without revision.", details={"retrieval_counts": retrieval_counts}))

    confidence = confidence_from_report(report)
    logger.info("curation_complete confidence=%s songs=%s", confidence, len(all_recommendations))
    return CurateResponse(
        parsed_intent=intent,
        playlist_arc=stages,
        selected_songs_by_stage=grouped,
        validation_report=report,
        confidence_score=confidence,
        agent_trace=trace,
    )


def evaluate_playlist(request: EvaluateRequest) -> EvaluateResponse:
    songs_by_id = {song.id: song for song in load_songs()}
    intent = parse_user_prompt(
        prompt=request.prompt,
        target_duration_minutes=None,
        allow_explicit=request.allow_explicit,
    )
    stages = plan_arc(intent, max(3, min(len(request.song_ids), 24)))
    trace = [
        AgentTraceStep(step="parser", summary="Parsed evaluation prompt into structured intent.", details=intent.model_dump()),
        AgentTraceStep(step="planner", summary="Built expected arc for evaluation.", details={"stages": [stage.model_dump() for stage in stages]}),
    ]

    missing = [song_id for song_id in request.song_ids if song_id not in songs_by_id]
    if missing:
        trace.append(AgentTraceStep(step="critic", summary="Rejected playlist because unknown song ids were supplied.", details={"missing_ids": missing}))
        report = validate_playlist([], intent, stages)
        report.issues.append(ValidationIssue(severity="error", message=f"Unknown song ids: {missing}"))
        report.warnings.append(f"Unknown song ids: {missing}")
        report.constraint_satisfaction = 0.0
        report.overall_confidence = 0.0
        report.metrics["constraint_satisfaction"] = 0.0
        report.metrics["overall_confidence"] = 0.0
        report.passed = False
        return EvaluateResponse(parsed_intent=intent, validation_report=report, confidence_score=0.0, agent_trace=trace)

    grouped = {stage.name: [] for stage in stages}
    for index, song_id in enumerate(request.song_ids):
        stage = stages[min(index * len(stages) // len(request.song_ids), len(stages) - 1)]
        song = songs_by_id[song_id]
        grouped[stage.name].append(
            SongRecommendation(
                song=song,
                stage=stage.name,
                match_score=0.7 if set(song.mood_tags).intersection(stage.target_moods) else 0.35,
                explanation=f"Evaluated against '{stage.name}' using deterministic mood and energy checks.",
            )
        )

    report = validate_playlist(flatten_playlist(grouped), intent, stages)
    confidence = confidence_from_report(report)
    trace.append(AgentTraceStep(step="critic", summary="Validated supplied playlist ids.", details=report.model_dump()))
    return EvaluateResponse(parsed_intent=intent, validation_report=report, confidence_score=confidence, agent_trace=trace)
