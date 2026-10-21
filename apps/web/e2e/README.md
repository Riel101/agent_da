# Web smoke harness

Drives the first-agenda flow and the plan index through a real headless Chrome
against a live API and Vite. It proves the wizard renders in every state and the
index lists what the account has created, writes the screenshots the review loop
reads, and fails loudly when a state does not appear.

It is a **smoke test**, not a pixel test: assertions check that a state is the
right state and that the plan timeline actually drew, not that any pixel is a
particular colour.

## One command

```bash
cd apps/web
npm run e2e:all
```

That boots a throwaway API on its own SQLite file, starts Vite if one is not
already running, runs every phase, writes the artifacts, and tears both down.
Exit code is non-zero if any check fails.

Individual phases:

```bash
npm run e2e:capture    # desktop, review, clarify, mobile, approved, …
npm run e2e:today      # the daily surface: empty, checked off, persisted
npm run e2e:plans      # the plan index: populated, filtered, empty
npm run e2e:planning   # the card mid-generation (needs AGENT_AUTOSTART=false)
npm run e2e:failed     # the failure notice
npm run e2e:focus      # keyboard-focus states
npm run e2e:snap       # HTML snapshots for the URL detector
```

`npm run e2e` is the same as `npm run e2e:all`.

## Running against servers you started

If you already have `npm run dev:all` (or your own servers) running:

```bash
E2E_NO_SERVER=1 npm run e2e:all
```

In this mode the harness never starts or stops anything. Note that `planning`
needs the API to run with `AGENT_AUTOSTART=false`; if your server always
autostarts, run that phase with a managed server instead.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `E2E_API` | `http://127.0.0.1:8000/api/v1` | API root, version prefix included |
| `E2E_WEB` | `http://localhost:5173` | Vite dev server |
| `E2E_OUT` | `<repo>/.impeccable/review` | Where screenshots land |
| `E2E_SNAP` | `<tmp>/agentda-e2e-snap` | Where HTML snapshots land |
| `E2E_DB` | `<tmp>/agentda-e2e-<pid>.db` | Throwaway SQLite file |
| `E2E_KEEP_DB` | unset | Keep the database after the run |
| `E2E_START_DATE` | today, `Africa/Lagos` | Fixed agenda start date |
| `E2E_NO_SERVER` | unset | Attach to running servers |
| `CHROME` | auto-detected | Chrome/Chromium executable |
| `E2E_PYTHON` / `DEV_PYTHON` | unset | Ready interpreter that can `import uvicorn` (skips venv bootstrap) |

## Requirements

- **Chrome or Chromium.** Auto-detected at the usual paths; override with
  `CHROME=/path/to/chrome`. `puppeteer-core` ships no browser.
- **API dependencies.** The managed server reuses `apps/api/.venv`. If no
  interpreter can import `uvicorn` and `pydantic_core`, it runs
  `scripts/ensure-api-venv.sh`, which creates the venv and installs
  `apps/api/requirements.txt`. Set `E2E_PYTHON` / `DEV_PYTHON` to skip that
  bootstrap and use a ready interpreter instead. `apps/api/.pylibs` is no
  longer used.

## Outputs

- Screenshots: `.impeccable/review/*.png` — `desktop`, `mobile`, `planning`,
  `clarify`, `review`, `review-top`, `mobile-review`, `mobile-review-top`,
  `approved`, `failed`, `focus-field`, `focus-tab`, `today`, `today-empty`,
  `today-mobile`, `plans`, `plans-filtered`, `plans-mobile`, `plans-empty`,
  `plans-delete-armed`, `plans-deleted`.
- HTML snapshots: `E2E_SNAP/*.html` — `capture`, `capture-mobile`, `review`,
  `review-mobile`.

Screenshots are read by the Impeccable review loop. The HTML snapshots feed the
URL detector; serve their directory and point the detector at each file:

```bash
python3 -m http.server 8788 --directory "$E2E_SNAP"
```

## Layout

| File | Role |
| --- | --- |
| `harness.mjs` | Config, Chrome lookup, API client, `shot`/`dumpHtml`, probes |
| `capture.mjs` | The happy path, as one growing sheet |
| `plans.mjs` | The plan index: populated, filtered, mobile and empty |
| `planning.mjs` | Mid-generation, before the draft lands |
| `failed.mjs` | Flips the draft row to `failed` and captures the notice |
| `focus.mjs` | The two keyboard-focus states |
| `snap.mjs` | HTML snapshots for the detector |
| `run.mjs` | Orchestrator: server lifecycle + phase dispatch |
