"""Song retrieval and scoring over the local CSV-backed music catalog."""

from .models import ParsedIntent, PlaylistStage, Song


mood_synonyms: dict[str, set[str]] = {
    "anxious": {"restless", "tense", "uneasy", "overwhelmed"},
    "grounded": {"steady", "calm", "centered", "balanced"},
    "hopeful": {"bright", "warm", "uplifting", "optimistic"},
    "reflective": {"introspective", "thoughtful", "quiet", "journaling"},
    "nostalgic": {"memory", "memories", "bittersweet", "warm"},
    "focused": {"steady", "minimal", "instrumental", "study"},
    "cozy": {"warm", "soft", "intimate", "gentle"},
    "calm": {"soft", "peaceful", "gentle", "quiet"},
    "warm": {"romantic", "hopeful", "cozy", "tender"},
    "energized": {"energetic", "upbeat", "confident", "hype"},
    "steady": {"focused", "grounded", "minimal", "calm"},
}


def retrieve_candidates(
    songs: list[Song],
    stage: PlaylistStage,
    intent: ParsedIntent,
    top_k: int = 12,
) -> list[tuple[Song, float]]:
    """Return the top scored local songs for a playlist stage.

    Score components total 1.0:
    - mood match contributes up to 0.40 using exact mood tags and synonyms.
    - energy match contributes up to 0.25 based on distance from target energy.
    - occasion/best_use match contributes up to 0.20.
    - constraints contribute up to 0.15 for lyric and loudness fit.
    """
    scored: list[tuple[Song, float]] = []
    seen_ids: set[int] = set()

    for song in songs:
        if song.id in seen_ids:
            continue
        seen_ids.add(song.id)

        if song.explicit and not intent.allow_explicit:
            continue

        mood_score = _score_mood(song, stage)
        energy_score = _score_energy(song, stage)
        occasion_score = _score_occasion(song, intent)
        constraint_score = _score_constraints(song, intent)

        # Medium/high lyric density is a strong mismatch for instrumental requests.
        if intent.avoid_lyrics and song.lyrics_level in {"medium", "high"}:
            constraint_score *= 0.2

        score = mood_score + energy_score + occasion_score + constraint_score
        scored.append((song, round(min(score, 1.0), 4)))

    return sorted(scored, key=lambda item: (-item[1], item[0].id))[:top_k]


def _score_mood(song: Song, stage: PlaylistStage) -> float:
    """Score exact and synonym mood overlap, capped at 0.40."""
    song_tags = set(song.mood_tags)
    target_mood = stage.target_mood.lower()
    related_moods = mood_synonyms.get(target_mood, set())

    exact_match = target_mood in song_tags
    synonym_overlap = len(song_tags.intersection(related_moods))

    score = 0.0
    if exact_match:
        score += 0.28
    score += min(synonym_overlap * 0.06, 0.12)
    return min(score, 0.40)


def _score_energy(song: Song, stage: PlaylistStage) -> float:
    """Score energy closeness to the stage target, capped at 0.25."""
    distance = abs(song.energy - stage.target_energy)
    normalized_fit = max(0.0, 1.0 - distance)
    return round(normalized_fit * 0.25, 4)


def _score_occasion(song: Song, intent: ParsedIntent) -> float:
    """Score whether the song's best_use matches the user's occasion."""
    occasion = intent.occasion.lower()
    best_use = song.best_use.lower()

    if occasion in {"general", "general listening"}:
        return 0.10
    if occasion in best_use:
        return 0.20
    if _occasion_alias_match(occasion, best_use):
        return 0.16
    return 0.04


def _score_constraints(song: Song, intent: ParsedIntent) -> float:
    """Score clean, lyric, and loudness constraints, capped at 0.15."""
    score = 0.15

    if intent.avoid_lyrics:
        if song.lyrics_level == "none":
            score += 0.0
        elif song.lyrics_level == "low":
            score -= 0.04
        elif song.lyrics_level == "medium":
            score -= 0.11
        else:
            score -= 0.15

    if _has_not_too_loud_constraint(intent) and song.energy > 0.70:
        score -= min((song.energy - 0.70) * 0.5, 0.10)

    return round(max(0.0, min(score, 0.15)), 4)


def _occasion_alias_match(occasion: str, best_use: str) -> bool:
    """Match occasion labels to related best_use values in the catalog."""
    aliases = {
        "coding": {"study", "deep work"},
        "studying": {"study", "deep work"},
        "walking": {"commute", "drive", "morning"},
        "relaxing": {"wind_down", "wind down", "late night"},
        "sleeping": {"sleep", "wind_down", "wind down"},
        "journaling": {"solo listening", "late night", "healing"},
        "dinner": {"dinner", "brunch", "date"},
        "cleaning": {"party", "morning", "commute"},
        "workout": {"workout", "party"},
    }
    return any(alias in best_use for alias in aliases.get(occasion, set()))


def _has_not_too_loud_constraint(intent: ParsedIntent) -> bool:
    """Return True when the user requested a controlled or quiet energy level."""
    constraints = {constraint.lower() for constraint in intent.constraints}
    return "not too loud" in constraints or "lower energy preferred" in constraints
