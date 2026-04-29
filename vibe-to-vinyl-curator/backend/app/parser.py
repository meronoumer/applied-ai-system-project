import re

from .models import Intent


MOOD_KEYWORDS = {
    "calm": {"calm", "peaceful", "soft", "gentle", "quiet", "soothing"},
    "reflective": {"reflective", "introspective", "thinking", "deep", "journaling"},
    "nostalgic": {"nostalgic", "memory", "memories", "old", "bittersweet"},
    "hopeful": {"hopeful", "optimistic", "bright", "uplifting", "healing"},
    "energized": {"energized", "energy", "hype", "pump", "moving", "workout"},
    "romantic": {"romantic", "love", "date", "tender", "crush"},
    "melancholic": {"melancholic", "sad", "blue", "lonely", "heartbreak"},
    "focused": {"focused", "study", "work", "coding", "concentrate"},
    "dreamy": {"dreamy", "float", "ethereal", "ambient"},
    "confident": {"confident", "bold", "powerful", "swagger"},
}

CONTEXT_KEYWORDS = {
    "study": {"study", "homework", "reading", "coding", "focus", "work"},
    "dinner": {"dinner", "cooking", "date", "hosting"},
    "workout": {"workout", "run", "gym", "training"},
    "wind_down": {"sleep", "wind down", "bed", "night", "late"},
    "commute": {"drive", "commute", "walk", "train"},
}


def parse_intent(prompt: str) -> Intent:
    text = prompt.lower()
    tokens = set(re.findall(r"[a-z']+", text))

    target_moods: list[str] = []
    for mood, keywords in MOOD_KEYWORDS.items():
        if keywords.intersection(tokens) or any(keyword in text for keyword in keywords if " " in keyword):
            target_moods.append(mood)

    if not target_moods:
        target_moods = ["reflective", "hopeful"]

    avoided = []
    if "not sad" in text or "avoid sad" in text:
        avoided.append("melancholic")
    if "no lyrics" in text or "instrumental" in text:
        avoided.append("lyrical")

    if any(word in tokens for word in {"build", "rise", "climb", "energize", "hype"}):
        energy_start, energy_end, arc_type = 0.3, 0.85, "rising"
    elif any(word in tokens for word in {"calm", "relax", "sleep", "settle", "soft"}):
        energy_start, energy_end, arc_type = 0.55, 0.25, "cooldown"
    elif any(word in tokens for word in {"sad", "grief", "heartbreak", "healing"}):
        energy_start, energy_end, arc_type = 0.35, 0.65, "healing"
    else:
        energy_start, energy_end, arc_type = 0.4, 0.7, "balanced"

    desired_context = "general listening"
    for context, keywords in CONTEXT_KEYWORDS.items():
        if keywords.intersection(tokens) or any(keyword in text for keyword in keywords if " " in keyword):
            desired_context = context
            break

    constraints = []
    if "clean" in tokens or "no explicit" in text:
        constraints.append("clean lyrics preferred")
    if "instrumental" in tokens or "no lyrics" in text:
        constraints.append("low lyric density preferred")

    return Intent(
        original_prompt=prompt,
        target_moods=target_moods,
        avoided_moods=avoided,
        energy_start=energy_start,
        energy_end=energy_end,
        arc_type=arc_type,
        desired_context=desired_context,
        constraints=constraints,
    )
