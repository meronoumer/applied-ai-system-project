from .models import ArcStage, Intent, Song


def retrieve_candidates(
    songs: list[Song],
    stage: ArcStage,
    intent: Intent,
    allow_explicit: bool,
    limit: int = 12,
) -> list[tuple[Song, float]]:
    scored = []
    for song in songs:
        if song.explicit and not allow_explicit:
            continue
        if "lyrical" in intent.avoided_moods and song.lyrics_level in {"medium", "high"}:
            continue

        mood_overlap = len(set(stage.target_moods).intersection(song.mood_tags))
        prompt_overlap = len(set(intent.target_moods).intersection(song.mood_tags))
        energy_fit = 1 - min(abs(_midpoint(stage) - song.energy), 1)
        context_fit = 1 if intent.desired_context in song.best_use.lower() else 0
        score = (0.42 * mood_overlap) + (0.22 * prompt_overlap) + (0.28 * energy_fit) + (0.08 * context_fit)
        if stage.energy_min <= song.energy <= stage.energy_max:
            score += 0.25
        scored.append((song, round(score, 4)))

    return sorted(scored, key=lambda item: (-item[1], item[0].energy, item[0].id))[:limit]


def _midpoint(stage: ArcStage) -> float:
    return (stage.energy_min + stage.energy_max) / 2
