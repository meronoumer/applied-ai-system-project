from backend.app.models import ParsedIntent, PlaylistStage, Song, SongRecommendation
from backend.app.validator import needs_revision, validate_playlist


def test_validator_penalizes_explicit_content_when_not_allowed():
    song = Song(
        id=10,
        title="Explicit Test",
        artist="Test Artist",
        genre="pop",
        duration_seconds=210,
        bpm=100,
        energy=0.50,
        mood_tags=["hopeful"],
        lyrics_level="medium",
        explicit=True,
        best_use="general",
        description="Synthetic explicit song.",
    )
    stage = PlaylistStage(
        name="Closing: Hopeful release",
        target_mood="hopeful",
        target_energy=0.65,
        duration_share=1.0,
    )
    rec = SongRecommendation(
        song=song,
        stage_name=stage.name,
        match_score=0.90,
        reason="Synthetic recommendation.",
    )
    intent = ParsedIntent(
        end_mood="hopeful",
        allow_explicit=False,
        target_duration_minutes=None,
    )

    report = validate_playlist([rec], intent, [stage])

    assert report.constraint_satisfaction < 1.0
    assert any("Explicit songs" in warning for warning in report.warnings)
    assert needs_revision(report) is True
