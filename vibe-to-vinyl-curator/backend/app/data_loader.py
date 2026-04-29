"""Data loading utilities for the local song catalog."""

from functools import lru_cache
from pathlib import Path
from typing import Final

import pandas as pd
from pydantic import ValidationError

from .models import Song


DATA_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "data" / "songs.csv"

REQUIRED_COLUMNS: Final[set[str]] = {
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


class SongDataError(RuntimeError):
    """Raised when the local song catalog cannot be loaded safely."""


def get_all_songs() -> list[Song]:
    """Return every song in the local CSV catalog as validated Song objects."""
    return _load_songs_cached()


def get_song_by_id(song_id: int) -> Song | None:
    """Return one song by id, or None when the id is not in the catalog."""
    return next((song for song in get_all_songs() if song.id == song_id), None)


@lru_cache(maxsize=1)
def _load_songs_cached() -> list[Song]:
    """Load and validate songs once per process."""
    if not DATA_PATH.exists():
        raise SongDataError(
            f"Song database is missing. Expected CSV file at: {DATA_PATH}"
        )

    try:
        frame = pd.read_csv(DATA_PATH)
    except Exception as exc:
        raise SongDataError(f"Could not read song database CSV: {exc}") from exc

    _validate_columns(frame)

    songs: list[Song] = []
    for row_number, row in frame.iterrows():
        try:
            songs.append(_row_to_song(row))
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            csv_line = row_number + 2
            raise SongDataError(
                f"Malformed song record on CSV line {csv_line}: {exc}"
            ) from exc

    _validate_unique_ids(songs)
    return songs


def _validate_columns(frame: pd.DataFrame) -> None:
    """Ensure the CSV contains every required column."""
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise SongDataError(
            f"Song database is missing required column(s): {', '.join(sorted(missing))}"
        )


def _validate_unique_ids(songs: list[Song]) -> None:
    """Ensure each song id appears once."""
    ids = [song.id for song in songs]
    if len(ids) != len(set(ids)):
        raise SongDataError("Song database contains duplicate song ids.")


def _row_to_song(row: pd.Series) -> Song:
    """Convert one pandas row into a validated Song model."""
    payload = row.to_dict()
    payload["mood_tags"] = _parse_mood_tags(payload["mood_tags"])
    payload["explicit"] = _parse_bool(payload["explicit"])
    payload["id"] = int(payload["id"])
    payload["duration_seconds"] = int(payload["duration_seconds"])
    payload["bpm"] = int(payload["bpm"])
    payload["energy"] = float(payload["energy"])
    return Song(**payload)


def _parse_mood_tags(value: object) -> list[str]:
    """Parse pipe-separated mood tags into normalized lowercase strings."""
    tags = [tag.strip().lower() for tag in str(value).split("|") if tag.strip()]
    if not tags:
        raise ValueError("mood_tags must contain at least one tag")
    return tags


def _parse_bool(value: object) -> bool:
    """Parse common CSV boolean encodings."""
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value for explicit: {value!r}")


# Backward-compatible name used by the initial deterministic modules.
load_songs = get_all_songs
