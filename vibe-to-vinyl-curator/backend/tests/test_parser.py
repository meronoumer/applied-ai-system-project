from backend.app.parser import parse_user_prompt


def test_parser_extracts_duration_mood_arc_and_constraints():
    intent = parse_user_prompt(
        "Make me a 30-minute playlist that starts anxious, becomes grounded, "
        "and ends hopeful. Not too loud.",
        target_duration_minutes=None,
        allow_explicit=False,
    )

    assert intent.target_duration_minutes == 30
    assert intent.start_mood == "anxious"
    assert intent.middle_mood == "grounded"
    assert intent.end_mood == "hopeful"
    assert "not too loud" in intent.constraints


def test_parser_detects_no_lyrics_and_coding_occasion():
    intent = parse_user_prompt(
        "I want background music for coding with no lyrics",
        target_duration_minutes=None,
        allow_explicit=False,
    )

    assert intent.avoid_lyrics is True
    assert intent.occasion == "coding"
    assert intent.start_mood == "focused"
    assert intent.middle_mood == "steady"
    assert intent.end_mood == "focused"
