# Conditor — Discord Server Foundry (Example)

This is a runnable example of the Conditor system (minimal scaffold).

Quick start

1. Create a `.env` file next to the repository with your bot token (or set environment variable `CONDITOR_TOKEN`). Optionally set `CONDITOR_GUILD_ID` to a development guild ID to register slash commands only there for faster iteration; omit it to register commands globally (available to everyone).

2. Create a virtual env and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Run the bot (from repo root):

Windows PowerShell:

```powershell
python -m src.conditor
```

Linux / macOS:

```bash
python3 -m src.conditor
```

Files included in this example:
- `src/conditor/bot.py` — bot bootstrap
- `src/conditor/cogs/builder.py` — `BuilderCog` and build pipeline
- `src/conditor/cogs/backup.py` — `BackupCog` for export/restore
- `data/templates/example_template.json` — example template
- `data/questionnaire/sample_questionnaire.json` — sample questions
- `data/locales/en.json` — minimal localization bundle
 - `requirements.txt` — Python requirements

Notes

 - This scaffold is a minimal, runnable starting point. The build pipeline is simplified for clarity.
 - For a production Conditor you should add robust localization loaders, persistent template storage, retries, metrics, and test harnesses.

Usage notes (for everyone)

- To make application (slash) commands available to all guilds, do not set `CONDITOR_GUILD_ID` — the bot will sync commands globally on startup. This may take up to an hour to propagate across Discord. For fast development, set `CONDITOR_GUILD_ID` to your test guild ID and commands will appear instantly in that guild.
- When running for multiple users or hosting publicly, secure your `CONDITOR_TOKEN` (do not commit `.env` to source control). Consider using a secrets manager or host platform env variables.

Deployment

- Install dependencies and run as above, or use your preferred host (Render, Heroku, Fly, Docker). Ensure the environment contains `CONDITOR_TOKEN` and any optional `CONDITOR_GUILD_ID`.
- Using Render (recommended quick deploy)

	1. Push this repository to GitHub (or connect your repo to Render).
	2. In the Render dashboard, create a new **Background Worker** (not Web Service) or a **Private Service**.
	3. Choose to deploy from the repository and branch containing this project.
	4. Build command (if not using Dockerfile):

		 ```bash
		 pip install -r requirements.txt
		 ```

		 Start command:

		 ```bash
		 python -m src.conditor
		 ```

	5. Alternatively, use the provided `Dockerfile` — Render will detect and build it automatically. The container runs the bot via the package entrypoint.
	6. Add environment variables in the Render service settings:

		 - `CONDITOR_TOKEN` = your bot token (set as a secret)
		 - Optional: `CONDITOR_GUILD_ID` = your dev guild ID (for fast per-guild slash command registration)

	7. Deploy the service. The bot will start and keep running as a background worker.

- Docker / other hosts

	- Build locally or in CI:

		```bash
		docker build -t conditor:latest .
		docker run -e CONDITOR_TOKEN="<token>" conditor:latest
		```

Security note

- Keep `CONDITOR_TOKEN` secret. Use Render's secret environment variables or your platform's secret manager; do NOT commit `.env`.

Contributing

- This repository is intended as an example foundation for everyone. Please open issues or PRs to improve templates, localization, or the build pipeline.

Persistence & BuildPlans
------------------------

Conditor can snapshot a guild's structure as a replayable `BuildPlan` and export/import plans as JSON.

- `C!plan_preview <template>`: compile a `BuildPlan` from available templates and preview steps.
- `C!plan_run_sample <template>`: run a sample (noop) execution of the compiled plan locally.
- `C!conditor_build <template>`: compile a `BuildPlan` and enqueue it for execution; the build worker will execute steps against the bot's guilds.

Advanced persistence

- Use `src.conditor.core.persistence.backup.snapshot_guild_to_plan_async(guild)` (async) to create a deep backup that includes role colors, channel permission overwrites, channel types, and recent message history (captured as replayed `POST_MESSAGE` steps using webhooks when possible).
- Export and import plans using `export_plan(plan, path)` and `import_plan(path)` (both in `src.conditor.core.persistence.backup`).

Testing
-------

Run the included pytest suite:

```bash
pip install -r requirements.txt
pytest -q
```