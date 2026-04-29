from functools import lru_cache
from pathlib import Path

import pandas as pd

from .models import Song


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "songs.csv"


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _row_to_song(row: pd.Series) -> Song:
    payload = row.to_dict()
    payload["mood_tags"] = [
        tag.strip().lower()
        for tag in str(payload.get("mood_tags", "")).split("|")
        if tag.strip()
    ]
    payload["explicit"] = _parse_bool(payload.get("explicit"))
    payload["energy"] = float(payload["energy"])
    payload["duration_seconds"] = int(payload["duration_seconds"])
    payload["bpm"] = int(payload["bpm"])
    payload["id"] = int(payload["id"])
    return Song(**payload)


@lru_cache(maxsize=1)
def load_songs() -> list[Song]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Song database not found at {DATA_PATH}")

    frame = pd.read_csv(DATA_PATH)
    required = {
        "id",
        "title",
        "artist",
        "genre",
        "duration_seconds",
        "bpm",
        "energy",
        "mood_tags",
        "lyrics_level",
        "explicit",
        "best_use",
        "description",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"songs.csv is missing required columns: {sorted(missing)}")

    songs = [_row_to_song(row) for _, row in frame.iterrows()]
    ids = [song.id for song in songs]
    if len(ids) != len(set(ids)):
        raise ValueError("songs.csv contains duplicate song ids")
    return songs


def get_song_by_id(song_id: int) -> Song | None:
    return next((song for song in load_songs() if song.id == song_id), None)
