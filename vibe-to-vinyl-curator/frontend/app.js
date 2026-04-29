const API_BASE_URL = "http://127.0.0.1:8000";

const form = document.querySelector("#curate-form");
const statusEl = document.querySelector("#status");
const resultsEl = document.querySelector("#results");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const promptInput = document.querySelector("#prompt");
  const maxSongsInput = document.querySelector("#max-songs");
  const allowExplicitInput = document.querySelector("#allow-explicit");

  const prompt = promptInput.value.trim();
  const maxSongs = Number(maxSongsInput.value || 9);
  const allowExplicit = allowExplicitInput.checked;

  if (!prompt) {
    statusEl.textContent = "Please describe the emotional playlist you want.";
    resultsEl.innerHTML = "";
    return;
  }

  const payload = {
    prompt: prompt,
    max_songs: maxSongs,
    allow_explicit: allowExplicit,
  };

  statusEl.textContent = "Curating your emotional playlist arc...";
  resultsEl.innerHTML = "";

  try {
    const response = await fetch(`${API_BASE_URL}/curate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend returned ${response.status}: ${errorText}`);
    }

    const data = await response.json();

    console.log("Curate response:", data);

    renderResults(data);

    const confidence = Number(data.confidence_score ?? data.validation_report?.overall_confidence ?? 0);

    statusEl.textContent = `Curated successfully. Confidence ${(confidence * 100).toFixed(0)}%.`;
  } catch (error) {
    console.error("Frontend fetch error:", error);
    statusEl.textContent = `Could not reach the backend: ${error.message}`;
  }
});

function renderResults(data) {
  resultsEl.innerHTML = "";

  const parsedIntent = data.parsed_intent || {};
  const validation = data.validation_report || {};

  const arcType = parsedIntent.arc_type || "emotional";
  const startMood = parsedIntent.start_mood || "";
  const middleMood = parsedIntent.middle_mood || "";
  const endMood = parsedIntent.end_mood || "";

  const targetMoods = Array.isArray(parsedIntent.target_moods)
    ? parsedIntent.target_moods
    : [];

  const moodText =
    targetMoods.length > 0
      ? targetMoods.join(", ")
      : [startMood, middleMood, endMood].filter(Boolean).join(" → ") || "Custom emotional arc";

  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  const issues = Array.isArray(validation.issues) ? validation.issues : [];

  const issueText =
    issues.length > 0
      ? issues.map((issue) => issue.message || issue).join(" ")
      : warnings.length > 0
        ? warnings.map((warning) => warning.message || warning).join(" ")
        : "Validation passed.";

  const confidence = Number(data.confidence_score ?? validation.overall_confidence ?? 0);

  resultsEl.insertAdjacentHTML(
    "beforeend",
    `<section class="panel summary">
      <p class="eyebrow">Generated Playlist Arc</p>
      <h2>${escapeHtml(titleCase(arcType))} Arc</h2>
      <p><strong>Mood journey:</strong> ${escapeHtml(moodText)}</p>
      <p><strong>Confidence:</strong> ${(confidence * 100).toFixed(0)}%</p>
      <p><strong>Status:</strong> ${escapeHtml(issueText)}</p>
    </section>`
  );

  renderValidation(validation);

  const playlistArc = Array.isArray(data.playlist_arc) ? data.playlist_arc : [];
  const songsByStage = data.selected_songs_by_stage || {};

  if (playlistArc.length === 0) {
    resultsEl.insertAdjacentHTML(
      "beforeend",
      `<section class="panel">
        <h2>No playlist arc returned</h2>
        <p>The backend responded, but it did not return playlist stages.</p>
      </section>`
    );
    return;
  }

  for (const stage of playlistArc) {
    const stageName = stage.name || "Playlist Stage";
    const songs = Array.isArray(songsByStage[stageName])
      ? songsByStage[stageName]
      : [];

    const songHtml =
      songs.length > 0
        ? songs.map(renderSong).join("")
        : `<p class="empty-stage">No songs were selected for this stage.</p>`;

    resultsEl.insertAdjacentHTML(
      "beforeend",
      `<section class="stage">
        <div class="stage-header">
          <p class="eyebrow">${escapeHtml(stage.target_mood || "Mood stage")}</p>
          <h2>${escapeHtml(stageName)}</h2>
          <p>${escapeHtml(stage.goal || stage.description || "Designed as part of the emotional transition.")}</p>
        </div>
        <div class="song-list">
          ${songHtml}
        </div>
      </section>`
    );
  }

  renderAgentTrace(data.agent_trace);
}

function renderSong(item) {
  const song = item.song || {};

  const title = song.title || "Untitled";
  const artist = song.artist || "Unknown artist";
  const genre = song.genre || "Unknown genre";
  const bpm = song.bpm ?? "N/A";
  const energy = Number(song.energy ?? 0);
  const matchScore = Number(item.match_score ?? 0);

  const explanation =
    item.explanation ||
    item.reason ||
    "Selected because its metadata matched this stage of the requested playlist arc.";

  const moodTags = Array.isArray(song.mood_tags)
    ? song.mood_tags.join(", ")
    : song.mood_tags || "";

  return `<article class="song">
    <div>
      <div class="song-title">${escapeHtml(title)} - ${escapeHtml(artist)}</div>
      <div class="song-meta">
        ${escapeHtml(genre)} · ${escapeHtml(bpm)} BPM · energy ${energy.toFixed(2)}
      </div>
      ${
        moodTags
          ? `<div class="song-meta">moods: ${escapeHtml(moodTags)}</div>`
          : ""
      }
      <div class="explanation">${escapeHtml(explanation)}</div>
    </div>
    <div class="score">${Math.round(matchScore * 100)}%</div>
  </article>`;
}

function renderValidation(validation) {
  if (!validation || Object.keys(validation).length === 0) {
    return;
  }

  const moodMatch = Number(validation.mood_match ?? 0);
  const transitionSmoothness = Number(validation.transition_smoothness ?? 0);
  const durationAccuracy = Number(validation.duration_accuracy ?? 0);
  const constraintSatisfaction = Number(validation.constraint_satisfaction ?? 0);
  const overallConfidence = Number(validation.overall_confidence ?? 0);

  const rows = [
    ["Mood match", moodMatch],
    ["Transition smoothness", transitionSmoothness],
    ["Duration accuracy", durationAccuracy],
    ["Constraint satisfaction", constraintSatisfaction],
    ["Overall confidence", overallConfidence],
  ];

  const metricHtml = rows
    .map(([label, value]) => {
      const percent = Math.round(value * 100);
      return `<div class="metric">
        <div class="metric-label">
          <span>${escapeHtml(label)}</span>
          <span>${percent}%</span>
        </div>
        <div class="metric-bar">
          <div class="metric-fill" style="width: ${clamp(percent, 0, 100)}%"></div>
        </div>
      </div>`;
    })
    .join("");

  resultsEl.insertAdjacentHTML(
    "beforeend",
    `<section class="panel validation">
      <p class="eyebrow">Reliability Check</p>
      <h2>Validation Report</h2>
      ${metricHtml}
    </section>`
  );
}

function renderAgentTrace(agentTrace) {
  if (!Array.isArray(agentTrace) || agentTrace.length === 0) {
    return;
  }

  const traceHtml = agentTrace
    .map((step) => {
      const stepName = step.step || "agent-step";
      const summary = step.summary || "";
      const details = step.details || "";

      return `<li>
        <strong>${escapeHtml(titleCase(stepName))}</strong>
        <span>${escapeHtml(summary)}</span>
        ${details ? `<small>${escapeHtml(details)}</small>` : ""}
      </li>`;
    })
    .join("");

  resultsEl.insertAdjacentHTML(
    "beforeend",
    `<section class="panel agent-trace">
      <p class="eyebrow">Agentic Workflow</p>
      <h2>Agent Trace</h2>
      <ul>${traceHtml}</ul>
    </section>`
  );
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function titleCase(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\w\S*/g, (word) => {
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    });
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}