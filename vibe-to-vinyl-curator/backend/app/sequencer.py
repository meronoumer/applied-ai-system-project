"""Sequencing utilities for turning selected songs into a smooth arc."""

from statistics import mean

from .models import SongRecommendation


def sequence_playlist(
    recommendations: list[SongRecommendation],
) -> list[SongRecommendation]:
    """Sequence recommendations while preserving stage groups.

    Stage groups remain in their original plan order. Inside each stage, the
    function chooses ascending or descending energy order based on which creates
    the smallest jump from the previous stage.
    """
    grouped = _group_by_stage(recommendations)
    sequenced: list[SongRecommendation] = []

    for stage_recommendations in grouped:
        ascending = sorted(
            stage_recommendations,
            key=lambda rec: (rec.song.energy, rec.song.bpm, rec.song.id),
        )
        descending = list(reversed(ascending))

        if not sequenced:
            chosen = ascending
        else:
            previous_energy = sequenced[-1].song.energy
            ascending_jump = abs(previous_energy - ascending[0].song.energy)
            descending_jump = abs(previous_energy - descending[0].song.energy)
            chosen = ascending if ascending_jump <= descending_jump else descending

        sequenced.extend(chosen)

    return sequenced


def calculate_transition_smoothness(
    recommendations: list[SongRecommendation],
) -> float:
    """Return 1.0 for tiny energy transitions and lower values for jumps."""
    if len(recommendations) < 2:
        return 1.0

    penalties = [
        abs(left.song.energy - right.song.energy)
        for left, right in zip(recommendations, recommendations[1:])
    ]
    average_penalty = mean(penalties)
    return round(max(0.0, 1.0 - average_penalty), 3)


def sequence_stage(songs: list[SongRecommendation]) -> list[SongRecommendation]:
    """Compatibility helper for sequencing a single stage."""
    return sequence_playlist(songs)


def flatten_playlist(
    grouped: dict[str, list[SongRecommendation]],
) -> list[SongRecommendation]:
    """Flatten stage-grouped recommendations in insertion order."""
    ordered: list[SongRecommendation] = []
    for stage_songs in grouped.values():
        ordered.extend(stage_songs)
    return ordered


def _group_by_stage(
    recommendations: list[SongRecommendation],
) -> list[list[SongRecommendation]]:
    """Group recommendations by first-seen stage order."""
    grouped: list[list[SongRecommendation]] = []
    stage_indexes: dict[str, int] = {}

    for recommendation in recommendations:
        stage_name = recommendation.stage_name or recommendation.stage
        if stage_name not in stage_indexes:
            stage_indexes[stage_name] = len(grouped)
            grouped.append([])
        grouped[stage_indexes[stage_name]].append(recommendation)

    return grouped
