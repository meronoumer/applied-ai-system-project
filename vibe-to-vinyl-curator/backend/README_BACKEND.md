# Vibe-to-Vinyl Curator Backend

FastAPI backend for a deterministic agentic music recommendation system.

## Run Locally

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API docs.

## Endpoints

- `GET /health` returns service status.
- `GET /songs` returns the local song database.
- `POST /curate` parses a natural language prompt and returns a staged playlist with an agent trace.
- `POST /evaluate` evaluates supplied song ids against a prompt-derived arc.

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/curate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"clean reflective music that slowly becomes hopeful\",\"max_songs\":9}"
```

## Architecture

The backend is intentionally modular:

- `parser.py` converts natural language into structured intent.
- `planner.py` creates the emotional playlist arc.
- `retriever.py` scores songs from `data/songs.csv`.
- `selector.py` chooses diverse stage songs.
- `sequencer.py` orders songs inside stages.
- `validator.py` provides guardrails and confidence scoring.
- `agent.py` orchestrates the workflow and emits trace steps.
