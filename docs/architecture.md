Conditor — Architecture Overview

Core idea

Conditor is a pipeline that separates decision-making from execution. The pipeline stages are:

1. Intent — capture "what the user wants" as neutral data (ServerSpec).
2. Planner — compile the ServerSpec into an ordered BuildPlan of atomic steps.
3. Executor — rate-limit-aware worker that serializes and executes BuildPlan steps.
4. Verification & Safety — validate state after each phase, apply sanity rules.
5. Persistence — backup and restore as replayable plans.

Mapping to code (initial scaffolding)

- `src/conditor/core/intent` — `ServerSpec` model, questionnaire/template loaders, merging logic.
- `src/conditor/core/planner` — compiler producing `BuildPlan` (list of small steps).
- `src/conditor/core/executor` — single worker, durable queue, retry and rate-limit handling.
- `src/conditor/core/safety` — verification, permission sanity, content rules.
- `src/conditor/core/persistence` — snapshotting and replay (export/import as plans).

Intended workflow

- Commands feed the intent layer; the planner generates a BuildPlan; the executor runs it; verification checks results; persistence stores snapshots.

Next steps

- Flesh out `ServerSpec` and a minimal questionnaire/template loader.
- Add planner API surface and executor worker skeleton.
