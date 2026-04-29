# Model Card: Vibe-to-Vinyl Curator v0.1

## System Type

Deterministic applied AI simulation for agentic music recommendation. This version does not call external APIs or generative models.

## Intended Use

The system is intended for coursework, prototyping, and local demonstrations of an agentic recommendation workflow. It maps emotional listening goals to a staged playlist using a curated local song database.

## Inputs

- Natural language playlist prompt.
- Optional maximum song count.
- Optional explicit-content allowance.

## Outputs

- Parsed intent.
- Playlist arc stages.
- Songs grouped by stage.
- Song-level explanations.
- Validation report.
- Confidence score.
- Agent trace.

## Data

The starter dataset is `backend/data/songs.csv`, a hand-authored sample catalog with mood tags, energy, tempo, lyric density, and usage notes.

## Reliability And Guardrails

Current checks include duplicate detection, explicit content filtering, stage completeness, requested mood coverage, transition spike detection, and bounded request validation through Pydantic.

## Limitations

- Keyword parsing is simple and may miss nuanced prompts.
- Retrieval uses hand-authored tags rather than audio features or embeddings.
- Confidence is a deterministic heuristic, not calibrated against user satisfaction.
- The dataset is small and not representative of global music taste.

## Ethical Notes

The system should not infer sensitive mental health states or present recommendations as therapeutic care. Emotional language is treated as a playlist preference only.
