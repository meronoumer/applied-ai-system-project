from .models import ArcStage, Intent


def plan_arc(intent: Intent, max_songs: int) -> list[ArcStage]:
    counts = _stage_counts(max_songs)
    low = min(intent.energy_start, intent.energy_end)
    high = max(intent.energy_start, intent.energy_end)

    if intent.arc_type == "cooldown":
        return [
            ArcStage(name="Arrive", goal="Start with presence and warmth", target_moods=intent.target_moods, energy_min=0.35, energy_max=0.65, song_count=counts[0]),
            ArcStage(name="Soften", goal="Lower stimulation while keeping emotional color", target_moods=["calm", "reflective", *intent.target_moods], energy_min=0.2, energy_max=0.5, song_count=counts[1]),
            ArcStage(name="Release", goal="End spacious and settled", target_moods=["calm", "dreamy"], energy_min=0.0, energy_max=0.35, song_count=counts[2]),
        ]

    if intent.arc_type == "rising":
        return [
            ArcStage(name="Ignite", goal="Open with an inviting pulse", target_moods=["hopeful", *intent.target_moods], energy_min=0.2, energy_max=0.5, song_count=counts[0]),
            ArcStage(name="Lift", goal="Build momentum and emotional brightness", target_moods=intent.target_moods, energy_min=0.45, energy_max=0.75, song_count=counts[1]),
            ArcStage(name="Peak", goal="Finish with confidence and motion", target_moods=["energized", "confident", *intent.target_moods], energy_min=0.65, energy_max=1.0, song_count=counts[2]),
        ]

    if intent.arc_type == "healing":
        return [
            ArcStage(name="Name It", goal="Meet the feeling honestly", target_moods=["melancholic", "reflective"], energy_min=0.15, energy_max=0.45, song_count=counts[0]),
            ArcStage(name="Hold It", goal="Add tenderness and clarity", target_moods=["reflective", *intent.target_moods], energy_min=0.3, energy_max=0.6, song_count=counts[1]),
            ArcStage(name="Move Through", goal="Close with hope and forward motion", target_moods=["hopeful", "calm"], energy_min=0.45, energy_max=0.75, song_count=counts[2]),
        ]

    return [
        ArcStage(name="Ground", goal="Establish the emotional palette", target_moods=intent.target_moods, energy_min=max(0, low - 0.15), energy_max=min(1, low + 0.2), song_count=counts[0]),
        ArcStage(name="Deepen", goal="Lean into the core vibe", target_moods=intent.target_moods, energy_min=0.35, energy_max=0.7, song_count=counts[1]),
        ArcStage(name="Resolve", goal="Leave the listener with a clear landing", target_moods=["hopeful", "calm", *intent.target_moods], energy_min=max(0, high - 0.2), energy_max=min(1, high + 0.15), song_count=counts[2]),
    ]


def _stage_counts(max_songs: int) -> list[int]:
    base = max_songs // 3
    remainder = max_songs % 3
    return [base + (1 if index < remainder else 0) for index in range(3)]
