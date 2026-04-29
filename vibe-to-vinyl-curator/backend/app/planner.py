"""Planner agent for creating a three-stage emotional playlist arc."""

from .models import ParsedIntent, PlaylistStage


DEFAULT_DURATION_SHARES = (0.33, 0.34, 0.33)

ENERGY_GROUPS: dict[str, tuple[float, set[str]]] = {
    "medium": (0.55, {"anxious", "restless", "overwhelmed"}),
    "low-medium": (0.35, {"calm", "soft", "reflective", "grounded"}),
    "medium-high": (0.65, {"hopeful", "warm", "joyful", "upbeat"}),
    "steady-medium": (0.50, {"focused", "steady", "coding"}),
    "low": (0.20, {"sleep", "sleeping", "relaxing", "peaceful", "dreamy"}),
    "high": (0.80, {"workout", "energetic", "energized"}),
}

STAGE_DESCRIPTIONS = {
    "opening": "Matches the user's starting emotional state without intensifying it.",
    "middle": "Introduces steadier textures and calmer pacing.",
    "closing": "Ends with a warmer emotional tone and a sense of forward motion.",
}

MOOD_TITLES = {
    "anxious": "Restless but contained",
    "grounded": "Grounding the room",
    "hopeful": "Hopeful release",
    "focused": "Clean focus",
    "steady": "Settled momentum",
    "warm": "Warm arrival",
    "cozy": "Intimate glow",
    "nostalgic": "Nostalgic landing",
    "calm": "Calm entry",
    "soft": "Softening the edges",
    "peaceful": "Peaceful landing",
    "energized": "Energized lift",
    "confident": "Confident stride",
    "uplifted": "Uplifted finish",
    "reflective": "Reflective opening",
    "introspective": "Inner focus",
}


def create_playlist_plan(intent: ParsedIntent) -> list[PlaylistStage]:
    """Create a polished three-stage emotional playlist plan."""
    stage_specs = [
        ("Opening", intent.start_mood, STAGE_DESCRIPTIONS["opening"], DEFAULT_DURATION_SHARES[0]),
        ("Middle", intent.middle_mood, STAGE_DESCRIPTIONS["middle"], DEFAULT_DURATION_SHARES[1]),
        ("Closing", intent.end_mood, STAGE_DESCRIPTIONS["closing"], DEFAULT_DURATION_SHARES[2]),
    ]

    stages = [
        _build_stage(
            prefix=prefix,
            mood=mood,
            description=description,
            duration_share=duration_share,
        )
        for prefix, mood, description, duration_share in stage_specs
    ]
    _ensure_duration_sum(stages)
    return stages


def plan_arc(intent: ParsedIntent, max_songs: int) -> list[PlaylistStage]:
    """Compatibility wrapper that adds song counts for the retrieval pipeline."""
    stages = create_playlist_plan(intent)
    counts = _stage_counts(max_songs)
    for index, stage in enumerate(stages):
        stage.song_count = counts[index]
        stage.target_moods = _stage_target_moods(stage.target_mood, intent)
        stage.energy_min, stage.energy_max = _energy_window(stage.target_energy)
        stage.goal = stage.description
    return stages


def infer_target_energy(mood: str) -> float:
    """Infer target energy from a mood or occasion keyword."""
    normalized = mood.strip().lower()
    for target_energy, keywords in ENERGY_GROUPS.values():
        if normalized in keywords:
            return target_energy
    return 0.50


def create_stage_name(prefix: str, mood: str) -> str:
    """Create a product-friendly stage name for a mood."""
    title = MOOD_TITLES.get(mood, mood.replace("_", " ").title())
    return f"{prefix}: {title}"


def _build_stage(
    prefix: str,
    mood: str,
    description: str,
    duration_share: float,
) -> PlaylistStage:
    """Build a PlaylistStage with both public and retrieval compatibility fields."""
    target_energy = infer_target_energy(mood)
    energy_min, energy_max = _energy_window(target_energy)
    return PlaylistStage(
        name=create_stage_name(prefix, mood),
        target_mood=mood,
        target_energy=target_energy,
        description=description,
        duration_share=duration_share,
        goal=description,
        target_moods=[mood],
        energy_min=energy_min,
        energy_max=energy_max,
        song_count=3,
    )


def _energy_window(target_energy: float) -> tuple[float, float]:
    """Create a bounded retrieval window around a target energy."""
    return max(0.0, round(target_energy - 0.18, 2)), min(1.0, round(target_energy + 0.18, 2))


def _stage_target_moods(stage_mood: str, intent: ParsedIntent) -> list[str]:
    """Expand a stage mood with the full parsed arc for retrieval recall."""
    return _dedupe_preserve_order([stage_mood, *intent.target_moods])


def _stage_counts(max_songs: int) -> list[int]:
    """Split the requested song count across three stages."""
    base = max_songs // 3
    remainder = max_songs % 3
    return [base + (1 if index < remainder else 0) for index in range(3)]


def _ensure_duration_sum(stages: list[PlaylistStage]) -> None:
    """Adjust final stage share so total duration share is exactly 1.0."""
    total_except_last = sum(stage.duration_share for stage in stages[:-1])
    stages[-1].duration_share = round(1.0 - total_except_last, 2)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicate mood labels while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
