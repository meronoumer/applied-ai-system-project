from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LyricsLevel = Literal["none", "low", "medium", "high"]


class Song(BaseModel):
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


class CurateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    max_songs: int = Field(default=12, ge=3, le=24)
    allow_explicit: bool = False


class EvaluateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    song_ids: list[int] = Field(min_length=1, max_length=50)
    allow_explicit: bool = False

    @field_validator("song_ids")
    @classmethod
    def unique_song_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("song_ids must be unique")
        return value


class Intent(BaseModel):
    original_prompt: str
    target_moods: list[str]
    avoided_moods: list[str]
    energy_start: float
    energy_end: float
    arc_type: str
    desired_context: str
    constraints: list[str]


class ArcStage(BaseModel):
    name: str
    goal: str
    target_moods: list[str]
    energy_min: float
    energy_max: float
    song_count: int


class SongRecommendation(BaseModel):
    song: Song
    stage: str
    match_score: float
    explanation: str


class ValidationIssue(BaseModel):
    severity: Literal["info", "warning", "error"]
    message: str


class ValidationReport(BaseModel):
    passed: bool
    issues: list[ValidationIssue]
    metrics: dict[str, Any]


class AgentTraceStep(BaseModel):
    step: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class CurateResponse(BaseModel):
    parsed_intent: Intent
    playlist_arc: list[ArcStage]
    selected_songs_by_stage: dict[str, list[SongRecommendation]]
    validation_report: ValidationReport
    confidence_score: float
    agent_trace: list[AgentTraceStep]


class EvaluateResponse(BaseModel):
    parsed_intent: Intent
    validation_report: ValidationReport
    confidence_score: float
    agent_trace: list[AgentTraceStep]
