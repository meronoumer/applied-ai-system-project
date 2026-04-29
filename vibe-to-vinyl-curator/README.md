# Vibe-to-Vinyl Curator

Vibe-to-Vinyl Curator is an applied AI music recommendation scaffold that turns an emotional intention into a structured playlist arc.

The first implementation is deterministic and local-first: it parses a user's prompt, plans an emotional journey, retrieves songs from a CSV database, selects and sequences songs, validates the result, and returns confidence plus an agent trace.

## What Is Included

- FastAPI backend with `GET /health`, `GET /songs`, `POST /curate`, and `POST /evaluate`.
- Modular recommendation pipeline in `backend/app`.
- Local song database with 45 sample songs.
- Deterministic guardrails for duplicates, explicit content, stage completeness, mood coverage, and transition spikes.
- Basic tests for curation and evaluation.
- Lightweight static frontend that calls the local API.
- Starter model card for documenting limitations and intended use.

## Quick Start

```bash
cd vibe-to-vinyl-curator/backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

- API docs: `http://127.0.0.1:8000/docs`
- Frontend: `vibe-to-vinyl-curator/frontend/index.html`

## Run Tests

```bash
cd vibe-to-vinyl-curator/backend
pytest
```

## Agent Workflow

1. Parser converts natural language into structured intent.
2. Planner creates three emotional stages.
3. Retriever scores local songs against each stage.
4. Selector chooses diverse songs and explanations.
5. Sequencer orders songs by energy and tempo.
6. Critic validates the output and produces confidence.
7. Revision step records whether warnings require follow-up.

## Next Milestones

- Add persistent run logs and playlist export.
- Replace keyword retrieval with embeddings while keeping local fallback.
- Add richer frontend state views for trace and validation reports.
- Expand tests around edge cases and malformed data.
- Complete course-specific documentation and evaluation rubric mapping.
