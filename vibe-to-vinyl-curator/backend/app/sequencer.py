from .models import SongRecommendation


def sequence_stage(songs: list[SongRecommendation]) -> list[SongRecommendation]:
    return sorted(songs, key=lambda rec: (rec.song.energy, rec.song.bpm, rec.song.id))


def flatten_playlist(grouped: dict[str, list[SongRecommendation]]) -> list[SongRecommendation]:
    ordered: list[SongRecommendation] = []
    for stage_songs in grouped.values():
        ordered.extend(stage_songs)
    return ordered
