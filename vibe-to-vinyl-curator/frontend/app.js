const form = document.querySelector("#curate-form");
const statusEl = document.querySelector("#status");
const resultsEl = document.querySelector("#results");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Curating...";
  resultsEl.innerHTML = "";

  const payload = {
    prompt: document.querySelector("#prompt").value,
    max_songs: Number(document.querySelector("#max-songs").value),
    allow_explicit: document.querySelector("#allow-explicit").checked,
  };

  try {
    const response = await fetch("http://127.0.0.1:8000/curate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    renderResults(data);
    statusEl.textContent = `Confidence ${(data.confidence_score * 100).toFixed(0)}%`;
  } catch (error) {
    statusEl.textContent = `Could not reach the backend: ${error.message}`;
  }
});

function renderResults(data) {
  const moods = data.parsed_intent.target_moods.join(", ");
  const issues = data.validation_report.issues.length
    ? data.validation_report.issues.map((issue) => issue.message).join(" ")
    : "Validation passed.";

  resultsEl.insertAdjacentHTML(
    "beforeend",
    `<section class="panel summary">
      <h2>${escapeHtml(data.parsed_intent.arc_type)} arc</h2>
      <p>Moods: ${escapeHtml(moods)}</p>
      <p>${escapeHtml(issues)}</p>
    </section>`
  );

  for (const stage of data.playlist_arc) {
    const songs = data.selected_songs_by_stage[stage.name] || [];
    const songHtml = songs
      .map(
        (item) => `<article class="song">
          <div>
            <div class="song-title">${escapeHtml(item.song.title)} - ${escapeHtml(item.song.artist)}</div>
            <div class="song-meta">${escapeHtml(item.song.genre)} · ${item.song.bpm} BPM · energy ${item.song.energy.toFixed(2)}</div>
            <div class="explanation">${escapeHtml(item.explanation)}</div>
          </div>
          <div class="score">${Math.round(item.match_score * 100)}%</div>
        </article>`
      )
      .join("");

    resultsEl.insertAdjacentHTML(
      "beforeend",
      `<section class="stage">
        <h2>${escapeHtml(stage.name)}</h2>
        <p>${escapeHtml(stage.goal)}</p>
        ${songHtml}
      </section>`
    );
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
