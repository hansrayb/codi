# Codi
A minimal Telegram bot named Codi for running Codex tasks through regular chat, with an internal orchestrator that selects roles, manages sessions, and enforces basic safety restrictions.

## Features

- Minimal commands: `/start`, `/help`, `/status`, `/devices`, `/done`, `/reset`
- All regular messages are treated as tasks
- Automatic role routing: `builder`, `reviewer`, `debugger`, `ops`, `general`
- Case manager v1: one active work context per user, repo context persists across prompts until `/done`
- Logical sessions per user with idle TTL and a small queue
- Non-interactive Codex execution via `codex exec`, with native resume for stable sessions
- Repo resolver v1: absolute paths, repo names, light fuzzy hints, and active workspace reuse
- Edit with approval: builder/debugger prepares a diff first, then the per-context draft edit persists until `/done`
- Self-update workflow: if the active repo is Codi itself, Codi will compile, test, then auto-restart after apply if verification passes
- Safe desktop actions for explicit intents such as opening installed GUI applications
- Repo watch: Codi can monitor a Git repo and send notifications when branch, HEAD, or working status changes
- Direct host observability: Codi can summarize active desktop apps, important background processes, and recent runtime logs
- Business read-only mode: `business` users can select a business project, read schema/query SQLite read-only, and view candidate business logic files
- Lightweight Git workflow assistance: Codi can summarize local diffs, compose commit messages, PR titles, and PR descriptions based on actual changes
- Multi-device phase 1: the central bot can store a device registry, accept agent heartbeats, and display online/offline devices from Telegram
- Simple auth whitelist and rate limiting

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Minimum required `.env` values:

- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_USER_IDS`
- `CODEX_WORK_DIR`

Recommended option for Telegram UX:

- `CODEX_REASONING_EFFORT=medium`

Additional options for multi-device phase 1:

- `ENABLE_DEVICE_REGISTRY=true`
- `DEVICE_API_SHARED_TOKEN=...`
- `DEVICE_API_HOST=0.0.0.0` if the central bot needs to accept heartbeats from other hosts
- `DEVICE_API_PORT=8787`

Additional options for business read-only access:

- `BUSINESS_USER_IDS=...`
- `BUSINESS_ALLOWED_DIRS=/path/to/business-project`
- `BUSINESS_DATABASE_PATHS=/path/to/business-project/app.sqlite` — explicit; if empty, Codi discovers `*.db`, `*.sqlite`, and `*.sqlite3` in the active project
- `BUSINESS_DATABASE_URLS=postgresql://readonly:...@host:5432/db,mysql://readonly:...@host:3306/db` for PostgreSQL/MySQL; use a read-only database user

Further documentation:

- product roadmap: [ROADMAP.md](./ROADMAP.md)
- secure multi-device architecture: [MULTI_DEVICE_ARCHITECTURE.md](./MULTI_DEVICE_ARCHITECTURE.md)

## Desktop Action

Codi currently supports explicit desktop actions to open GUI applications by name, with dedicated profiles for specific apps such as `LibreOffice Writer` and `Firefox`.

Example prompts:

- `open libreoffice writer`
- `open firefox`
- `open mozilla`
- `open telegram` if Telegram is installed on this desktop
- `run writer`
- `close libreoffice writer`
- `what apps is my laptop running`
- `show latest Codi log`
- `send laptop screenshot now`
- `send laptop screenshot now and summarize the screen`
- `send active monitor screenshot`
- `send active window screenshot now`
- `which devices are online`
- `status of all devices`
- `detail of device laptop-kerja`
- `what is my mode`
- `safe mode`
- `ops mode`
- `admin mode`
- `continue action`
- `cancel action`
- `restart codi`
- `set codex timeout to 600`
- `set local shell timeout to 600`
- `shell: systemctl --user status codex-agent.service`
- `bash: git status --short`
- `pwsh: Get-Process | Select-Object -First 5`
- `pull this repo`
- `check branch of this repo`
- `create branch feature/login in this repo`
- `switch to branch main in this repo`
- `merge branch staging into main in this repo`
- `delete branch feature/login in this repo`
- `rebase branch feature/login onto main in this repo`
- `commit this repo with message "Update payroll flow"`
- `commit all changes in this repo with message "Update payroll flow"`
- `cherry-pick commit a1b2c3d in this repo`
- `rollback last commit in this repo`
- `rollback to tag v1.2.3 in this repo`
- `create tag v1.2.3 in this repo`
- `check health of service codex-agent`
- `check health of all important services`
- `status of service codex-agent`
- `start service payroll`
- `stop service payroll`
- `restart service payroll`
- `view log of service payroll`
- `pm2 status rotasi-front-staging`
- `restart pm2 rotasi-front-staging`
- `view log pm2 rotasi-front-staging`
- `publish payroll frontend build`
- `deploy payroll frontend`
- `publish payroll backend`
- `deploy payroll backend`
- `test payroll backend`
- `build payroll frontend`
- `test repo web-dashboard-payroll`

Notes:

- This feature bypasses Codex and uses local app profiles or desktop entries.
- Firefox/Mozilla uses a `new window` profile, so it is faster and more consistent when the browser is already running.
- The `close` action only applies to app instances that Codi successfully tracked in the same runtime.
- Codi must run inside an active Linux desktop session for GUI apps to actually appear.
- `shell:` and its variants run commands directly on the host machine, not inside the Codex sandbox — use with an intentional prefix and only by trusted users.
- Natural shortcuts like `pull this repo` or `build payroll frontend` are also routed to the local shell, with the target repo inferred from the active context or repo name in the prompt.
- Codi now has a safety layer for sensitive host actions: `safe`/`ops`/`admin` modes, a command allowlist, two-step confirmation via `continue action` or `cancel action`, and a local audit log at `codi-audit.log`.
- For fine-grained settings like `set codex timeout to 600` or `set local shell timeout to 600`, Codi can now update the local `.env` directly without going through the Codex builder flow.
- The `status/start/stop/restart/log/health service ...` shortcuts currently target `systemd --user`, so they work best for services running at the user level.
- The `pm2 status/restart/start/stop/log ...` shortcuts run via the host local shell, so they can access the PM2 instance owned by the user running the Codi service.
- `check health of all important services` reads the list from `IMPORTANT_SERVICES` in `.env`.
- Backend shortcuts try `package.json` scripts, `Makefile` targets, or common Python tooling such as `uv`, `poetry`, and `pytest`.
- `rollback to tag ...` uses `git revert`, which is safer as it does not destructively reset branch history.

## Business Read-Only

The `business` role is designed for reading data and business logic, not host operations or code editing.

Example prompts after selecting a project with `/pilih_project`:

- `business database schema`
- `postgresql database schema`
- `mysql database schema`
- `select id, name from customers limit 10`
- `count orders table`
- `view products table`
- `read business logic of this project`

v1 behavior:

- Supported databases: SQLite (`.db`, `.sqlite`, `.sqlite3`), PostgreSQL, and MySQL.
- PostgreSQL/MySQL are read from `BUSINESS_DATABASE_URLS`; SQLite can be explicit via `BUSINESS_DATABASE_PATHS` or auto-discovered in the active project.
- Database queries are opened with a read-only connection and only accept `SELECT/WITH`; `PRAGMA` schema queries are safe for SQLite only.
- For business logic, Codi scans project files that look like services, models, controllers, routes, workflows, policies, rules, validations, schemas, or migrations.
- Business users can only select projects from `BUSINESS_ALLOWED_DIRS`; sensitive host actions remain unavailable for this role.

## Multi-Device Phase 1

What is available in this phase:

- central bot can accept `register` and `heartbeat` from device agents
- device registry stored in local file `codi-devices.json`
- Telegram can display the list of online/offline devices
- supported natural queries:
  - `which devices are online`
  - `status of all devices`
  - `detail of device laptop-kerja`
  - `/devices`

Running a simple agent on another device:

```bash
export CODI_CENTER_URL=http://IP-OR-DOMAIN-OF-CENTRAL-BOT:8787
export CODI_DEVICE_API_TOKEN=replace_with_shared_secret
export CODI_DEVICE_ID=laptop-kerja
export CODI_DEVICE_LABEL="Work Laptop"
export CODI_DEVICE_TYPE=desktop
export CODI_DEVICE_CAPABILITIES=shell,repo,system_activity,screenshot,desktop,business_readonly,natural_query,repo_readonly
# Only required if this device will run business SQLite queries.
export CODI_BUSINESS_DATABASE_PATHS=/path/to/attendance-project/database/attendance.sqlite3

python -m agent.main
```

Notes:

- phase 1 covers `registry + heartbeat`
- early phase 2 covers explicit device targeting for simple read-only tasks:
  - `on device absen-server, host status`
  - `on device absen-server, business database schema`
  - `on device absen-server, select * from absensi limit 10`
  - `on device absen-server, payroll data this month`

- If a device has an active repo and `repo_readonly` capability, data/repo prompts that do not match a specific shortcut will be sent as a `repo_readonly_query`.
  The agent will use the Claude CLI on that device to read the repo/database read-only, then return a summary to Telegram.
  - `result of task dt-xxxxxxxx`
- early phase 3 covers per-user device context:
  - `use device absen-server`
  - `what is the active device`
  - `on device absen-server, use repo /srv/absen`
  - `use repo /srv/absen` after selecting an active device
  - `context of device absen-server`
- for other hosts, port `DEVICE_API_PORT` must be reachable from the agent
- use a strong secret for `DEVICE_API_SHARED_TOKEN`
- device agents poll outbound to the central bot; non-central devices do not use `TELEGRAM_BOT_TOKEN`

## Commit / PR Assistant

Example prompts:

- `create commit message for changes in this repo`
- `summarize this diff into a PR description`
- `prepare PR title and body for repo web-dashboard-payroll`
- `review this local diff before I commit`

Notes:

- V1 is based on local repos accessible to Codi.
- Codi can read the local Git diff/status and summarize changes in plain language.
- This capability does not mean Codi will `git push` or open a remote PR automatically.

## Repo Watch

Example prompts:

- `watch this repo`
- `watch repo web-dashboard-payroll`
- `stop watching this repo`
- `which repos are being watched`
- `in this repo, fix Codi so /help is clearer`

v1 behavior:

- Codi only watches valid Git repos.
- Notifications are sent when branch changes, HEAD changes, or local working status changes.
- Polling runs in the local background and does not consume Codex tokens.

## Session Persistence

Codex sessions are now retained for normal work paths, so follow-up prompts feel closer to an in-IDE agent experience.

Notes:

- Edit tasks now use a live draft workspace per work context, so follow-up revisions do not always start from a fresh copy.
- A `continue` approval acts as the apply checkpoint; after that, the edit draft and Codex thread for the write path are retained.
- A `cancel` reply discards the last revision and re-syncs the draft to the current repo state.
- For the Codi repo itself, after `continue`, Codi runs `compileall` and `unittest` locally first.
- If verification passes, Codi restarts itself after sending the final response to Telegram.

## Running the Bot

```bash
source .venv/bin/activate
python main.py
```

## Running Tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Directory Structure

- `main.py`: Telegram app bootstrap
- `config.py`: load and validate environment
- `handlers/`: command and message handlers
- `core/`: orchestration, routing, session management
- `models/`: session and payload data models
- `utils/`: executor, formatter, logger
