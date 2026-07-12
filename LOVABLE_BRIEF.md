# Sebastian — Arbitration Outcome Prediction (Frontend Brief)

Build a clean, professional legal-tech web app called **Sebastian**. It predicts arbitration outcomes by running an AI tribunal simulation. The backend already exists — build ONLY the frontend against the API below. Do not mock endpoints that exist; call them directly.

## Backend

- Base URL: `https://seb-vug4.onrender.com` (make it a single config constant)
- CORS is enabled for all origins; no auth.
- Every response is wrapped in an envelope: `{ "success": true, "data": {...} }` or `{ "success": false, "error": "message" }`. Always check `success`.
- Send header `Accept-Language: en` on every request.
- **Cold starts:** the backend is on a free tier and may take up to ~60s to wake on the first request. Wrap the first call in a friendly "Waking up the tribunal…" state with retries; timeouts should be generous (120s+ for POSTs, the ontology call can take 2–5 minutes).
- Poll-heavy app: status endpoints are polled every 2–3 seconds.

## User flow (single wizard, 5 stages)

### Stage 1 — Case intake
Form: case name, case description / what to predict (textarea, required), governing law (optional text), relief sought (optional text), file upload (PDF/MD/TXT, multiple, optional — description alone is enough if detailed).

Submit as `multipart/form-data`:

```
POST /api/graph/ontology/generate
  files: <file>... (repeatable, optional)
  simulation_requirement: <case description>   (required)
  project_name: <case name>
  additional_context: <anything extra>
  governing_law: <text>
  relief_sought: <text>
```

Response `data`: `{ project_id, ontology: { entity_types, edge_types, analysis_summary }, files, total_text_length }`.
This call is slow (LLM analysis) — show a progress state. Display `analysis_summary` when done.

### Stage 2 — Build the case knowledge graph
```
POST /api/graph/build          { "project_id": "..." }   → data: { task_id }
GET  /api/graph/task/<task_id>                            → data: { status, progress, message }
```
Poll the task until `status` is `"completed"` (or `"failed"` → show `message`). Show progress bar.

### Stage 3 — Assemble the tribunal (create + prepare simulation)
```
POST /api/simulation/create
  { "project_id": "...", "enable_twitter": false, "enable_reddit": true }
  → data: { simulation_id }

POST /api/simulation/prepare   { "simulation_id": "..." }
  → data: { task_id?, already_prepared }

POST /api/simulation/prepare/status
  { "task_id": "...", "simulation_id": "..." }
  → data: { status, progress, message, already_prepared }
```
Poll prepare/status until `status` is `"ready"` or `"completed"`. This generates the arbitrator/counsel agent profiles — label it "Assembling tribunal panel…".

### Stage 4 — Run the hearing
```
POST /api/simulation/start
  { "simulation_id": "...", "platform": "parallel", "force": true,
    "enable_graph_memory_update": true }
  → data: { process_pid, ... }
```

Then poll two endpoints:

```
GET /api/simulation/<simulation_id>/run-status        (every 2s)
  → data: { runner_status, total_rounds, reddit_current_round,
            reddit_running, reddit_completed, reddit_actions_count, ... }

GET /api/simulation/<simulation_id>/run-status/detail (every 3s)
  → data: { all_actions: [ { agent_name, action_type, action_args: { content, ... },
                             round_num, timestamp, platform } ] }
```

UI: a live hearing transcript. Show round progress (`reddit_current_round / total_rounds`). Render `all_actions` as a chat-like feed (append new ones only — dedupe by `timestamp + agent_name + action_type`). Show the speaker's role as a badge derived from `agent_name` (contains "arbitrator"/"presiding" → Arbitrator; "claimant" → Claimant Counsel; "respondent" → Respondent Counsel). Entries whose `action_args.content` starts with `PROCEDURAL` are tribunal notices — style them as centered italic system messages. Only render actions with meaningful content (`CREATE_POST`, `CREATE_COMMENT`); others can be ignored.

The hearing is complete when `runner_status` is `"completed"` or `"stopped"`, or `reddit_completed` is `true`.
**Important: warn the user not to close the tab during the hearing** (polling keeps the free-tier server awake).

### Stage 5 — Verdict & report
After completion:

```
POST /api/simulation/<simulation_id>/verdict    (extracts the tribunal's votes; slow, ~1–2 min)
GET  /api/simulation/<simulation_id>/verdict    (returns cached verdict if already extracted; 404 if none)
```
Try GET first; if 404, POST to extract. Render the verdict `data` as the hero result (it contains the aggregated outcome prediction and per-arbitrator votes — render whatever fields come back, nicely).

Full written report:
```
POST /api/report/generate      { "simulation_id": "...", "force_regenerate": false }
  → data: { report_id }
GET  /api/report/<report_id>/progress   → data: { status, progress, message, completed_sections }
GET  /api/report/<report_id>            → data: { status, markdown_content, ... }
```
Poll progress until `status` is `"completed"`, then fetch the report and render `markdown_content` as formatted markdown.

## Extra pages
- **Dashboard (home):** list past cases via `GET /api/simulation/history` and `GET /api/report/list`; clicking a completed case shows its verdict/report (via the GET endpoints above).
- Design: serious legal aesthetic — deep navy/charcoal, serif display headings, generous whitespace. Think "prediction engine for disputes", not social media.

## Error handling
- On any `success: false`, surface `error` in a toast and allow retry of the current stage.
- Network failures during polling: keep polling silently (transient free-tier hiccups are normal); only surface an error after ~10 consecutive failures.
