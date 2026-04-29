from .models import ArcStage, Song, SongRecommendation


def select_songs(
    stage: ArcStage,
    candidates: list[tuple[Song, float]],
    used_song_ids: set[int],
) -> list[SongRecommendation]:
    selected: list[SongRecommendation] = []
    used_artists: set[str] = set()

    for song, score in candidates:
        if song.id in used_song_ids:
            continue
        artist_key = song.artist.lower()
        if artist_key in used_artists and len(selected) < stage.song_count - 1:
            continue
        selected.append(
            SongRecommendation(
                song=song,
                stage=stage.name,
                match_score=round(min(score / 2.0, 1.0), 3),
                explanation=_explain(song, stage, score),
            )
        )
        used_song_ids.add(song.id)
        used_artists.add(artist_key)
        if len(selected) == stage.song_count:
            break

    if len(selected) < stage.song_count:
        for song, score in candidates:
            if song.id in used_song_ids:
                continue
            selected.append(
                SongRecommendation(
                    song=song,
                    stage=stage.name,
                    match_score=round(min(score / 2.0, 1.0), 3),
                    explanation=_explain(song, stage, score),
                )
            )
            used_song_ids.add(song.id)
            if len(selected) == stage.song_count:
                break

    return selected


def _explain(song: Song, stage: ArcStage, score: float) -> str:
    shared = sorted(set(song.mood_tags).intersection(stage.target_moods))
    mood_text = ", ".join(shared) if shared else "adjacent emotional texture"
    return (
        f"Fits '{stage.name}' because it brings {mood_text}, "
        f"energy {song.energy:.2f}, and a {song.best_use} use case."
    )
