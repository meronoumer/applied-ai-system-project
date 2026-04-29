from backend.app.models import ParsedIntent, PlaylistStage, Song
from backend.app.retriever import retrieve_candidates


def _song(song_id: int, lyrics_level: str) -> Song:
    return Song(
        id=song_id,
        title=f"Focus Track {song_id}",
        artist="Test Artist",
        genre="ambient",
        duration_seconds=180,
        bpm=90,
        energy=0.48,
        mood_tags=["focused", "steady", "minimal"],
        lyrics_level=lyrics_level,
        explicit=False,
        best_use="study",
        description="Synthetic test song.",
    )


def test_retriever_penalizes_medium_high_lyrics_when_avoid_lyrics_is_true():
    intent = ParsedIntent(
        occasion="coding",
        start_mood="focused",
        middle_mood="steady",
        end_mood="focused",
        avoid_lyrics=True,
        allow_explicit=False,
        constraints=["avoid lyrics"],
    )
    stage = PlaylistStage(
        name="Opening: Clean focus",
        target_mood="focused",
        target_energy=0.50,
        duration_share=0.33,
    )
    songs = [_song(1, "none"), _song(2, "high"), _song(3, "medium")]

    candidates = retrieve_candidates(songs, stage, intent, top_k=3)
    scores = {song.id: score for song, score in candidates}

    assert scores[1] > scores[2]
    assert scores[1] > scores[3]


def test_retriever_filters_explicit_songs_when_not_allowed():
    clean = _song(1, "none")
    explicit = _song(2, "none").model_copy(update={"explicit": True})
    intent = ParsedIntent(occasion="coding", allow_explicit=False)
    stage = PlaylistStage(name="Opening: Clean focus", target_mood="focused")

    candidates = retrieve_candidates([clean, explicit], stage, intent, top_k=5)

    assert [song.id for song, _ in candidates] == [1]
