from app.agent import curate_playlist, evaluate_playlist
from app.data_loader import load_songs
from app.models import CurateRequest, EvaluateRequest


def test_curate_returns_agentic_playlist():
    response = curate_playlist(
        CurateRequest(
            prompt="I want a clean reflective playlist that starts calm and becomes hopeful.",
            max_songs=9,
        ),
        load_songs(),
    )

    assert response.parsed_intent.target_moods
    assert len(response.playlist_arc) == 3
    assert response.validation_report.passed
    assert response.confidence_score > 0
    assert {"parser", "planner", "retriever", "selector", "critic", "revision"}.issubset(
        {step.step for step in response.agent_trace}
    )


def test_evaluate_rejects_unknown_song_id():
    response = evaluate_playlist(
        EvaluateRequest(prompt="calm focused study music", song_ids=[999])
    )

    assert not response.validation_report.passed
    assert response.confidence_score == 0
