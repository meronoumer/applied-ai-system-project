import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import curate_playlist, evaluate_playlist
from .data_loader import load_songs
from .logger_config import configure_logging
from .models import CurateRequest, CurateResponse, EvaluateRequest, EvaluateResponse, Song

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vibe-to-Vinyl Curator API",
    description="Deterministic agentic AI music recommendation backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/songs", response_model=list[Song])
def songs() -> list[Song]:
    try:
        return load_songs()
    except Exception as exc:
        logger.exception("song_load_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/curate", response_model=CurateResponse)
def curate(request: CurateRequest) -> CurateResponse:
    try:
        return curate_playlist(request, load_songs())
    except Exception as exc:
        logger.exception("curation_failed")
        raise HTTPException(status_code=500, detail="Unable to curate playlist.") from exc


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    try:
        return evaluate_playlist(request)
    except Exception as exc:
        logger.exception("evaluation_failed")
        raise HTTPException(status_code=500, detail="Unable to evaluate playlist.") from exc
