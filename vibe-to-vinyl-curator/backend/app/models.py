"""Pydantic data contracts for the Vibe-to-Vinyl Curator backend."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


LyricsLevel = Literal["none", "low", "medium", "high"]
IssueSeverity = Literal["info", "warning", "error"]


class CurateRequest(BaseModel):
    """Request body for creating a new playlist arc from natural language."""

    prompt: str = Field(min_length=3, max_length=1000)
    target_duration_minutes: int | None = Field(default=None, ge=5, le=240)
    allow_explicit: bool = False
    max_songs: int = Field(default=10, ge=3, le=24)


class ParsedIntent(BaseModel):
    """Structured interpretation of the user's emotional playlist request."""

    occasion: str = "general listening"
    start_mood: str = "reflective"
    middle_mood: str = "focused"
    end_mood: str = "hopeful"
    target_duration_minutes: int | None = None
    constraints: list[str] = Field(default_factory=list)
    preferred_energy: str = "medium"
    avoid_lyrics: bool = False
    allow_explicit: bool = False

    # Compatibility fields used by the deterministic v0 agent modules.
    original_prompt: str = ""
    target_moods: list[str] = Field(default_factory=list)
    avoided_moods: list[str] = Field(default_factory=list)
    energy_start: float = Field(default=0.35, ge=0, le=1)
    energy_end: float = Field(default=0.65, ge=0, le=1)
    arc_type: str = "balanced"
    desired_context: str = "general listening"


class PlaylistStage(BaseModel):
    """One phase in the emotional playlist journey."""

    name: str
    target_mood: str = "reflective"
    target_energy: float = Field(default=0.5, ge=0, le=1)
    description: str = ""
    duration_share: float = Field(default=0.33, ge=0, le=1)

    # Compatibility fields used by the deterministic v0 agent modules.
    goal: str = ""
    target_moods: list[str] = Field(default_factory=list)
    energy_min: float = Field(default=0.0, ge=0, le=1)
    energy_max: float = Field(default=1.0, ge=0, le=1)
    song_count: int = Field(default=3, ge=1, le=24)


class Song(BaseModel):
    """A normalized song record loaded from the local CSV catalog."""

    id: int
    title: str
    artist: str
    genre: str
    duration_seconds: int = Field(gt=0)
    bpm: int = Field(gt=0)
    energy: float = Field(ge=0, le=1)
    mood_tags: list[str]
    lyrics_level: LyricsLevel
    explicit: bool
    best_use: str
    description: str


class SongRecommendation(BaseModel):
    """A selected song with its stage assignment and deterministic rationale."""

    song: Song
    stage_name: str = ""
    match_score: float = Field(ge=0, le=1)
    reason: str = ""

    # Compatibility fields used by the initial deterministic modules.
    stage: str = ""
    explanation: str = ""

    @model_validator(mode="after")
    def sync_compatibility_fields(self) -> "SongRecommendation":
        """Keep new and legacy field names aligned."""
        if not self.stage_name and self.stage:
            self.stage_name = self.stage
        if not self.stage and self.stage_name:
            self.stage = self.stage_name
        if not self.reason and self.explanation:
            self.reason = self.explanation
        if not self.explanation and self.reason:
            self.explanation = self.reason
        return self


class ValidationIssue(BaseModel):
    """A single validation warning or failure emitted by the critic step."""

    severity: IssueSeverity
    message: str


class ValidationReport(BaseModel):
    """Guardrail and quality metrics for a generated or supplied playlist."""

    mood_match: float = Field(default=0.0, ge=0, le=1)
    transition_smoothness: float = Field(default=0.0, ge=0, le=1)
    duration_accuracy: float = Field(default=0.0, ge=0, le=1)
    constraint_satisfaction: float = Field(default=0.0, ge=0, le=1)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    passed: bool = False

    # Compatibility fields used by the deterministic v0 agent modules.
    issues: list[ValidationIssue] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentTraceStep(BaseModel):
    """One auditable step in the agentic curation workflow."""

    step: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class CurateResponse(BaseModel):
    """Response body returned by the curation endpoint."""

    parsed_intent: ParsedIntent
    playlist_arc: list[PlaylistStage]
    selected_songs_by_stage: dict[str, list[SongRecommendation]]
    validation_report: ValidationReport
    confidence_score: float = Field(ge=0, le=1)
    agent_trace: list[AgentTraceStep]


class EvaluationRequest(BaseModel):
    """Request body for validating a user-supplied playlist against a prompt."""

    prompt: str = Field(min_length=3, max_length=1000)
    song_ids: list[int] = Field(min_length=1, max_length=50)
    allow_explicit: bool = False

    @field_validator("song_ids")
    @classmethod
    def unique_song_ids(cls, value: list[int]) -> list[int]:
        """Reject duplicated song ids before evaluation."""
        if len(value) != len(set(value)):
            raise ValueError("song_ids must be unique")
        return value


class EvaluationResult(BaseModel):
    """Result returned by the playlist evaluation endpoint."""

    parsed_intent: ParsedIntent
    validation_report: ValidationReport
    confidence_score: float = Field(ge=0, le=1)
    agent_trace: list[AgentTraceStep]


# Backward-compatible aliases for the initial deterministic modules.
Intent = ParsedIntent
ArcStage = PlaylistStage
EvaluateRequest = EvaluationRequest
EvaluateResponse = EvaluationResult
