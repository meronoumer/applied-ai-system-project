"""Selector agent for choosing final songs from retrieved candidates."""

from .models import ParsedIntent, PlaylistStage, Song, SongRecommendation
from .retriever import retrieve_candidates


def select_songs_for_plan(
    songs: list[Song],
    plan: list[PlaylistStage],
    intent: ParsedIntent,
    max_songs: int,
) -> list[SongRecommendation]:
    """Select stage-aware songs for a full playlist plan.

    Each stage receives a song budget based on its duration share. The selector
    avoids duplicate songs across stages and returns fewer songs when the local
    catalog cannot satisfy a stage cleanly.
    """
    stage_counts = _allocate_stage_song_counts(plan, max_songs)
    selected: list[SongRecommendation] = []
    used_song_ids: set[int] = set()

    for stage, target_count in zip(plan, stage_counts):
        candidates = retrieve_candidates(
            songs=songs,
            stage=stage,
            intent=intent,
            top_k=max(12, target_count * 4),
        )
        stage_recommendations = _select_for_stage(
            stage=stage,
            candidates=candidates,
            used_song_ids=used_song_ids,
            target_count=target_count,
        )
        selected.extend(stage_recommendations)

    return selected[:max_songs]


def select_songs(
    stage: PlaylistStage,
    candidates: list[tuple[Song, float]],
    used_song_ids: set[int],
) -> list[SongRecommendation]:
    """Compatibility helper used by the initial agent implementation."""
    return _select_for_stage(
        stage=stage,
        candidates=candidates,
        used_song_ids=used_song_ids,
        target_count=stage.song_count,
    )


def _select_for_stage(
    stage: PlaylistStage,
    candidates: list[tuple[Song, float]],
    used_song_ids: set[int],
    target_count: int,
) -> list[SongRecommendation]:
    """Choose songs for one stage while limiting duplicate artists."""
    selected: list[SongRecommendation] = []
    stage_artists: set[str] = set()

    for song, score in candidates:
        if song.id in used_song_ids:
            continue

        artist_key = song.artist.lower()
        if artist_key in stage_artists and len(selected) < target_count - 1:
            continue

        selected.append(
            SongRecommendation(
                song=song,
                stage_name=stage.name,
                stage=stage.name,
                match_score=round(score, 3),
                reason=_build_reason(song, stage),
                explanation=_build_reason(song, stage),
            )
        )
        used_song_ids.add(song.id)
        stage_artists.add(artist_key)

        if len(selected) >= target_count:
            break

    if len(selected) < target_count:
        selected.extend(
            _fill_stage_without_artist_limit(
                stage=stage,
                candidates=candidates,
                used_song_ids=used_song_ids,
                remaining=target_count - len(selected),
            )
        )

    return selected


def _fill_stage_without_artist_limit(
    stage: PlaylistStage,
    candidates: list[tuple[Song, float]],
    used_song_ids: set[int],
    remaining: int,
) -> list[SongRecommendation]:
    """Fill a sparse stage with any unused high-scoring candidates."""
    fallback: list[SongRecommendation] = []
    for song, score in candidates:
        if song.id in used_song_ids:
            continue
        fallback.append(
            SongRecommendation(
                song=song,
                stage_name=stage.name,
                stage=stage.name,
                match_score=round(score, 3),
                reason=_build_reason(song, stage),
                explanation=_build_reason(song, stage),
            )
        )
        used_song_ids.add(song.id)
        if len(fallback) >= remaining:
            break
    return fallback


def _allocate_stage_song_counts(
    plan: list[PlaylistStage],
    max_songs: int,
) -> list[int]:
    """Allocate max_songs by duration_share using largest remainders."""
    if not plan:
        return []

    raw_counts = [stage.duration_share * max_songs for stage in plan]
    counts = [max(1, int(count)) for count in raw_counts]

    while sum(counts) > max_songs:
        index = max(range(len(counts)), key=lambda i: counts[i])
        counts[index] -= 1

    remainders = sorted(
        range(len(raw_counts)),
        key=lambda index: raw_counts[index] - int(raw_counts[index]),
        reverse=True,
    )
    while sum(counts) < max_songs:
        for index in remainders:
            counts[index] += 1
            if sum(counts) == max_songs:
                break

    return counts


def _build_reason(song: Song, stage: PlaylistStage) -> str:
    """Generate a concise metadata-based explanation for a selected song."""
    mood_text = _format_mood_tags(song, stage)
    energy_text = _energy_label(song.energy)
    return (
        f"Selected for its {mood_text} mood tags, {energy_text} energy, "
        f"and strong fit for {song.best_use}."
    )


def _format_mood_tags(song: Song, stage: PlaylistStage) -> str:
    """Prefer stage-relevant mood tags in the reason text."""
    stage_moods = set(stage.target_moods or [stage.target_mood])
    shared = [tag for tag in song.mood_tags if tag in stage_moods]
    tags = shared or song.mood_tags[:2]
    if len(tags) == 1:
        return tags[0]
    return f"{', '.join(tags[:-1])} and {tags[-1]}"


def _energy_label(energy: float) -> str:
    """Map numeric energy to a listener-friendly label."""
    if energy < 0.25:
        return "low"
    if energy < 0.45:
        return "medium-low"
    if energy < 0.65:
        return "medium"
    if energy < 0.80:
        return "medium-high"
    return "high"
