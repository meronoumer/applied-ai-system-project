"""FastAPI entrypoint for the Vibe-to-Vinyl Curator backend."""

import logging
import time
from statistics import mean
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .agent import curate_playlist
from .data_loader import SongDataError, load_songs
from .logger_config import configure_logging
from .models import (
    CurateRequest,
    CurateResponse,
    EvaluationRequest,
    EvaluationResult,
    PromptEvaluationResult,
    Song,
)

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vibe-to-Vinyl Curator API",
    description="Deterministic agentic AI music recommendation backend.",
    version="0.1.0",
)

# Development CORS:
# This project is intended to run locally during the final project demo.
# The frontend may be served from VS Code Live Preview, Live Server, Vite,
# Next.js, or a browser file-preview origin. During local development, allow
# all origins so the frontend can reliably call the FastAPI backend.
#
# For production, replace allow_origins=["*"] with a specific deployed frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    """Log each HTTP request with method, path, status, and latency."""
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_failed method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/")
def root() -> dict[str, Any]:
    """Return project metadata and available endpoints."""
    return {
        "name": "Vibe-to-Vinyl Curator",
        "description": "Agentic deterministic playlist curation backend",
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "songs": "GET /songs",
            "curate": "POST /curate",
            "evaluate": "POST /evaluate",
            "docs": "GET /docs",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Return backend health status."""
    return {
        "status": "ok",
        "message": "Vibe-to-Vinyl Curator backend is running",
    }


@app.get("/songs", response_model=list[Song])
def songs() -> list[Song]:
    """Return all songs loaded from the local CSV database."""
    try:
        return load_songs()
    except SongDataError as exc:
        logger.exception("song_load_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("unexpected_song_load_failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to load songs from the local database.",
        ) from exc


@app.post("/curate", response_model=CurateResponse)
def curate(request: CurateRequest) -> CurateResponse:
    """Curate a playlist arc from one natural language request."""
    try:
        song_catalog = load_songs()
        return curate_playlist(request, song_catalog)
    except SongDataError as exc:
        logger.exception("curation_song_load_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        logger.exception("curation_bad_request")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("curation_failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to curate playlist. Check backend logs for details.",
        ) from exc


@app.post("/evaluate", response_model=EvaluationResult, response_model_exclude_none=True)
def evaluate(request: EvaluationRequest) -> EvaluationResult:
    """Run the curator over a list of test prompts and summarize quality."""
    try:
        if not request.prompts:
            raise HTTPException(
                status_code=400,
                detail="/evaluate expects a non-empty 'prompts' list.",
            )

        song_catalog = load_songs()
        results: list[PromptEvaluationResult] = []

        for prompt in request.prompts:
            curate_request = CurateRequest(
                prompt=prompt,
                target_duration_minutes=request.target_duration_minutes,
                allow_explicit=request.allow_explicit,
                max_songs=request.max_songs,
            )
            response = curate_playlist(curate_request, song_catalog)
            report = response.validation_report

            results.append(
                PromptEvaluationResult(
                    prompt=prompt,
                    overall_confidence=report.overall_confidence,
                    passed=report.passed,
                    warnings=report.warnings,
                )
            )

        average_confidence = round(
            mean(result.overall_confidence for result in results), 3
        )
        pass_rate = round(
            sum(result.passed for result in results) / len(results), 3
        )

        return EvaluationResult(
            results=results,
            average_confidence=average_confidence,
            pass_rate=pass_rate,
        )

    except HTTPException:
        raise
    except SongDataError as exc:
        logger.exception("evaluation_song_load_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("evaluation_failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to evaluate prompts. Check backend logs for details.",
        ) from exc