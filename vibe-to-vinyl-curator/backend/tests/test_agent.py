from backend.app.agent import curate_playlist
from backend.app.data_loader import load_songs
from backend.app.main import evaluate
from backend.app.models import CurateRequest, EvaluationRequest


def test_agent_curate_returns_complete_agentic_response():
    response = curate_playlist(
        CurateRequest(
            prompt="I want a clean reflective playlist that starts calm and becomes hopeful.",
            max_songs=9,
        ),
        load_songs(),
    )

    all_recommendations = [
        rec
        for stage_recommendations in response.selected_songs_by_stage.values()
        for rec in stage_recommendations
    ]

    assert all_recommendations
    assert len(response.playlist_arc) == 3
    assert response.validation_report is not None
    assert {"parser", "planner", "retriever", "selector", "critic"}.issubset(
        {step.step for step in response.agent_trace}
    )


def test_evaluate_batch_calculates_pass_rate_and_average_confidence():
    request = EvaluationRequest(
        prompts=[
            "I want background music for coding with no lyrics",
            "Make a cozy dinner playlist that starts warm and ends nostalgic",
        ],
        max_songs=6,
    )

    result = evaluate(request)

    assert len(result.results) == 2
    expected_pass_rate = round(
        sum(prompt_result.passed for prompt_result in result.results)
        / len(result.results),
        3,
    )
    expected_average_confidence = round(
        sum(prompt_result.overall_confidence for prompt_result in result.results)
        / len(result.results),
        3,
    )
    assert result.pass_rate == expected_pass_rate
    assert result.average_confidence == expected_average_confidence
