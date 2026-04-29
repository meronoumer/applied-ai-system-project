"""Deterministic keyword parser for natural language playlist requests."""

import re
from typing import Optional

from .models import ParsedIntent


OCCASION_KEYWORDS: dict[str, set[str]] = {
    "coding": {"coding", "code", "programming", "debugging", "developer"},
    "studying": {"studying", "study", "homework", "reading", "exam"},
    "walking": {"walking", "walk", "stroll", "commute"},
    "dinner": {"dinner", "cooking", "date night", "hosting", "meal"},
    "relaxing": {"relaxing", "relax", "unwind", "wind down", "chill"},
    "cleaning": {"cleaning", "clean", "chores", "tidying", "laundry"},
    "workout": {"workout", "gym", "run", "running", "training", "exercise"},
    "sleeping": {"sleeping", "sleep", "bedtime", "nap", "fall asleep"},
    "journaling": {"journaling", "journal", "writing", "reflecting"},
}

KNOWN_MOODS: set[str] = {
    "anxious",
    "bittersweet",
    "calm",
    "confident",
    "cozy",
    "dreamy",
    "energized",
    "focused",
    "gentle",
    "grounded",
    "happy",
    "hopeful",
    "introspective",
    "melancholic",
    "nostalgic",
    "peaceful",
    "reflective",
    "romantic",
    "sad",
    "soft",
    "steady",
    "uplifted",
    "warm",
}

OCCASION_DEFAULTS: dict[str, tuple[str, str, str]] = {
    "coding": ("focused", "steady", "focused"),
    "studying": ("focused", "steady", "focused"),
    "walking": ("calm", "steady", "hopeful"),
    "dinner": ("warm", "cozy", "nostalgic"),
    "relaxing": ("calm", "soft", "peaceful"),
    "cleaning": ("energized", "upbeat", "satisfied"),
    "workout": ("energized", "confident", "uplifted"),
    "sleeping": ("calm", "dreamy", "peaceful"),
    "journaling": ("reflective", "introspective", "hopeful"),
    "general": ("reflective", "steady", "hopeful"),
}

LOW_ENERGY_PATTERNS = {
    "not too loud",
    "quiet",
    "calm",
    "gentle",
    "soft",
    "mellow",
    "low energy",
    "relaxing",
}

HIGH_ENERGY_PATTERNS = {
    "energetic",
    "upbeat",
    "hype",
    "pump",
    "workout",
    "gym",
    "dance",
    "high energy",
}

AVOID_LYRICS_PATTERNS = {
    "no lyrics",
    "instrumental",
    "without words",
    "no words",
    "wordless",
    "less lyrics",
}


def parse_user_prompt(
    prompt: str,
    target_duration_minutes: Optional[int],
    allow_explicit: bool,
) -> ParsedIntent:
    """Parse a playlist request into a deterministic structured intent."""
    normalized = normalize_text(prompt)
    occasion = detect_occasion(normalized)
    duration = target_duration_minutes or extract_duration_minutes(normalized)
    avoid_lyrics = detect_avoid_lyrics(normalized)
    constraints = extract_constraints(normalized, avoid_lyrics, allow_explicit)
    preferred_energy = detect_preferred_energy(normalized, occasion)
    start_mood, middle_mood, end_mood = detect_mood_arc(normalized, occasion)
    energy_start, energy_end, arc_type = derive_agent_energy_fields(
        preferred_energy, start_mood, end_mood
    )
    target_moods = dedupe_preserve_order([start_mood, middle_mood, end_mood])
    avoided_moods = ["lyrical"] if avoid_lyrics else []

    return ParsedIntent(
        occasion=occasion,
        start_mood=start_mood,
        middle_mood=middle_mood,
        end_mood=end_mood,
        target_duration_minutes=duration,
        constraints=constraints,
        preferred_energy=preferred_energy,
        avoid_lyrics=avoid_lyrics,
        allow_explicit=allow_explicit,
        original_prompt=prompt,
        target_moods=target_moods,
        avoided_moods=avoided_moods,
        energy_start=energy_start,
        energy_end=energy_end,
        arc_type=arc_type,
        desired_context=occasion,
    )


def parse_intent(prompt: str) -> ParsedIntent:
    """Backward-compatible wrapper used by the initial agent scaffold."""
    return parse_user_prompt(
        prompt=prompt,
        target_duration_minutes=None,
        allow_explicit=False,
    )


def normalize_text(prompt: str) -> str:
    """Normalize prompt text for deterministic keyword matching."""
    return re.sub(r"\s+", " ", prompt.lower()).strip()


def detect_occasion(text: str) -> str:
    """Detect the listening occasion from keyword matches."""
    for occasion, keywords in OCCASION_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return occasion
    return "general"


def extract_duration_minutes(text: str) -> int | None:
    """Extract a target duration such as '30-minute' or '45 min'."""
    match = re.search(r"\b(\d{1,3})\s*(?:-| )?(?:minute|minutes|min|mins)\b", text)
    if not match:
        return None
    minutes = int(match.group(1))
    return minutes if 1 <= minutes <= 240 else None


def detect_avoid_lyrics(text: str) -> bool:
    """Return True when the prompt asks for instrumental or wordless music."""
    return any(pattern in text for pattern in AVOID_LYRICS_PATTERNS)


def detect_preferred_energy(text: str, occasion: str) -> str:
    """Infer a categorical energy preference from prompt and occasion."""
    has_low = any(pattern in text for pattern in LOW_ENERGY_PATTERNS)
    has_high = any(pattern in text for pattern in HIGH_ENERGY_PATTERNS)

    if has_low and has_high:
        return "medium"
    if has_low:
        return "medium-low"
    if has_high or occasion in {"workout", "cleaning"}:
        return "high"
    if occasion in {"coding", "studying", "walking"}:
        return "medium"
    if occasion in {"sleeping", "relaxing", "journaling", "dinner"}:
        return "medium-low"
    return "medium"


def extract_constraints(text: str, avoid_lyrics: bool, allow_explicit: bool) -> list[str]:
    """Extract user constraints as short human-readable labels."""
    constraints: list[str] = []
    if "not too loud" in text:
        constraints.append("not too loud")
    if any(word in text for word in {"calm", "gentle", "soft", "quiet"}):
        constraints.append("lower energy preferred")
    if avoid_lyrics:
        constraints.append("avoid lyrics")
    if "clean" in text or "no explicit" in text or not allow_explicit:
        constraints.append("explicit content not allowed")
    elif allow_explicit:
        constraints.append("explicit content allowed")
    return dedupe_preserve_order(constraints)


def detect_mood_arc(text: str, occasion: str) -> tuple[str, str, str]:
    """Detect start, middle, and end moods with sensible occasion defaults."""
    default_start, default_middle, default_end = OCCASION_DEFAULTS[occasion]
    start_mood = extract_mood_after(text, ["starts", "start"]) or default_start
    middle_mood = (
        extract_mood_after(text, ["becomes", "turns into", "moves into", "then"])
        or default_middle
    )
    end_mood = extract_mood_after(text, ["ends", "end", "finishes", "lands"]) or default_end

    mentioned = find_known_moods(text)
    if mentioned:
        start_mood = start_mood if explicit_start_present(text) else mentioned[0]
        if len(mentioned) >= 2 and not explicit_middle_present(text):
            end_mood = end_mood if explicit_end_present(text) else mentioned[-1]
            middle_mood = infer_middle_mood(start_mood, end_mood, occasion)
        if len(mentioned) >= 3 and not explicit_middle_present(text):
            middle_mood = mentioned[1]

    if "cozy dinner" in text and not explicit_middle_present(text):
        middle_mood = "cozy"

    return start_mood, middle_mood, end_mood


def extract_mood_after(text: str, markers: list[str]) -> str | None:
    """Find a known mood appearing soon after one of the supplied markers."""
    mood_pattern = "|".join(sorted(KNOWN_MOODS, key=len, reverse=True))
    marker_pattern = "|".join(re.escape(marker) for marker in markers)
    pattern = rf"(?:{marker_pattern})(?:\s+(?:off|out))?\s+(?:feeling\s+|as\s+|with\s+)?({mood_pattern})"
    match = re.search(pattern, text)
    return match.group(1) if match else None


def find_known_moods(text: str) -> list[str]:
    """Return known moods in the order they appear in the prompt."""
    matches: list[tuple[int, str]] = []
    for mood in KNOWN_MOODS:
        match = re.search(rf"\b{re.escape(mood)}\b", text)
        if match:
            matches.append((match.start(), mood))
    return [mood for _, mood in sorted(matches)]


def infer_middle_mood(start_mood: str, end_mood: str, occasion: str) -> str:
    """Choose a stable middle mood when only start and end are explicit."""
    if occasion == "dinner":
        return "cozy"
    if start_mood == end_mood:
        return "steady"
    if end_mood in {"hopeful", "uplifted", "confident"}:
        return "grounded"
    if start_mood in {"warm", "romantic"}:
        return "cozy"
    return OCCASION_DEFAULTS[occasion][1]


def explicit_start_present(text: str) -> bool:
    """Return True when the prompt explicitly specifies a starting mood."""
    return any(marker in text for marker in {"starts", "start"})


def explicit_middle_present(text: str) -> bool:
    """Return True when the prompt explicitly specifies a middle transition."""
    return any(marker in text for marker in {"becomes", "turns into", "moves into"})


def explicit_end_present(text: str) -> bool:
    """Return True when the prompt explicitly specifies an ending mood."""
    return any(marker in text for marker in {"ends", "end", "finishes", "lands"})


def derive_agent_energy_fields(
    preferred_energy: str,
    start_mood: str,
    end_mood: str,
) -> tuple[float, float, str]:
    """Map parser labels into numeric fields used by the deterministic agent."""
    if preferred_energy == "high":
        return 0.55, 0.85, "rising"
    if preferred_energy == "medium-low":
        return 0.4, 0.3, "cooldown"
    if start_mood in {"anxious", "sad", "melancholic"} and end_mood in {
        "hopeful",
        "grounded",
        "peaceful",
    }:
        return 0.35, 0.65, "healing"
    return 0.4, 0.65, "balanced"


def dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicates while preserving first appearance order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
