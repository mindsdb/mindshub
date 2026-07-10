# Minds Platform

## Submodules

This repo has 4 submodules:

| Path | Repo | Tracking |
|---|---|---|
| `frontend` | `mindsdb/cowork` | tag-pinned |
| `backend/core_api` | `mindsdb/cowork-server` | tag-pinned |
| `backend/core_agent` | `mindsdb/anton` | tag-pinned |
| `backend/data-vault` | `mindsdb/data-vault` | `main` branch |

### Clone (fresh)

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds-platform
```

### Initialize after cloning without submodules

```bash
git submodule update --init --recursive
```

### Pull — sync to what the parent repo pins (default)

```bash
git submodule update --recursive
```

### Pull — advance all submodules to latest `main`

Only do this if you intend to develop across all repos. You'll need to commit the updated pointers in the parent repo afterward.

```bash
git submodule foreach 'git checkout main && git pull origin main'
```

### Make changes and push inside a submodule

1. Go into the submodule and get on a real branch first (all submodules start in detached HEAD):

```bash
cd backend/data-vault   # or whichever submodule
git checkout main       # or: git checkout -b your-feature-branch
```

2. Make your changes, commit, and push:

```bash
git add .
git commit -m "your message"
git push origin main
```

3. Back in the parent repo, stage and commit the updated submodule pointer:

```bash
cd ../..
git add backend/data-vault
git commit -m "bump data-vault to latest"
git push
```

> The parent repo stores a commit SHA pointer to each submodule, not the code itself. Always push from inside the submodule first, then update the pointer in the parent.

## Working on module branches (multi-developer)

The superproject pins each submodule to a commit. To let everyone develop on
their own module branches without fighting over pins or drowning in `git status`
noise, the workflow is:

**1. `.gitmodules` sets `ignore = all` on every submodule.** Day-to-day branch
work in a submodule never shows up as a superproject change — `git status` in the
parent stays clean no matter what branch each module is on. (This is the only
setting that silences "new commits in `<module>`"; `ignore = dirty` does not.)

**2. Pick your branches in `dev.env`** (gitignored — copy from `dev.env.example`):

```bash
cp dev.env.example dev.env
# REF=feat/my-thing            # all modules on one branch…
# API_REF=feat/server-thing    # …or override per module
```

**3. `make` is the single source of truth for refs** — both run paths follow `dev.env`:

| Command | What it does |
|---|---|
| `make refs` | print the refs the next run will use |
| `make use` | check out those refs across all submodules |
| `make dev` / `make dev-web` | run the **local submodule source** (`--reload`) — follows the checked-out branch |
| `make server` | (re)install the **Electron desktop server** from `API_REF`/`AGENT_REF` |
| `make server-local` | install Electron desktop server **from local uncommitted source** (no push needed) |
| `make app` | run the Electron desktop app (auto-update disabled so it can't revert your branch) |
| `make app-local` | run the Electron desktop app **against local uncommitted source** (runs `server-local` first) |
| `make pack-local` | build macOS `.app` from local uncommitted source, iCloud-safe (no DMG, `/tmp` build) |
| `make watch` | live reload — Electron app + Python `--reload` (alias for `make dev`) |
| `make baseline` | snap every submodule back to the superproject's pinned commits |
| `make pin` | record the submodules' current commits as the superproject pins (a deliberate commit) |

> Two run paths, same refs: `make dev`/`dev-web` execute the local source, so they
> follow whatever `make use` checked out. The desktop app runs a `uv`-tool-installed
> server keyed by `COWORK_SERVER_REF`/`ANTON_REF` (see
> `frontend/src/main/server-source.ts`); `make server`/`make app` set those from the
> same `dev.env`. Keep both on the same ref — they share `~/.cowork/cowork.db`, so a
> migration applied by one must exist in the other (else the app crashes on startup
> with `Can't locate revision …`). `make flush` resets when they drift.

> **Developing with uncommitted changes in the Electron app**: `make dev`/`dev-web`
> already pick up uncommitted source changes on-the-fly. For the Electron desktop path,
> `make app-local` installs cowork-server directly from `backend/core_api/` (no commit
> needed) and then launches the app. `COWORK_SERVER_DISABLE_AUTOUPDATE=1` is set
> automatically so the installer won't re-download from git. To also develop `core_agent`
> without committing: update `[tool.uv.sources] anton-agent` in
> `backend/core_api/pyproject.toml` to `{ path = "../../core_agent" }`, then re-run
> `make app-local`. (Restore the git source before pushing.)

**4. Bumping pins is deliberate.** Because submodules are ignored, the *only* way a
pin changes is `make pin` (after a submodule PR merges and you push the submodule).
Pushing from inside the submodule first still applies — `make pin` just records the
new SHA in the superproject as one reviewable commit.

**5. Snap back to baselines** when you're *not* developing a module: `make baseline`
(`git submodule update --init --recursive`). With `ignore = all`, `git status` won't
remind you a teammate's pin bump left a module behind — run `make baseline` after
pulling the superproject to align.

## Branch naming

Linear is connected to GitHub (`mindsdb` org). Every branch must include a Linear issue ID so the PR is automatically linked to the ticket.

**Format:** `<issue-id>-<short-description>` — copy it directly from the issue in Linear (branch icon on any issue card).

```
eng-123-fix-sso-no-credits
eng-456-add-attachment-thumbnails
```

- The team prefix is **`ENG`** (lowercase in branch names: `eng-`)
- Linear generates the full branch name for you — always use that, don't invent one
- PRs opened from a correctly named branch auto-attach to the Linear issue; no manual linking needed
- Hotfixes that don't have a ticket yet: create the ticket first, then branch from it

## Running locally (web browser mode)

After initializing submodules, start the full stack with:

```bash
cd frontend
npm install
npm run dev:web
```

Open `http://localhost:5173/`. The FastAPI backend starts automatically on `http://127.0.0.1:26866`.

### Skip Keycloak auth (required for local dev)

By default the web app redirects to MindsHub SSO on first load. To bypass this locally, create `frontend/src/renderer/.env` (Vite's root is `src/renderer`, not `frontend/`):

```bash
echo "VITE_SKIP_AUTH=true" > frontend/src/renderer/.env
```

Then restart `npm run dev:web`. The Keycloak redirect will be skipped and the app loads the onboarding screen directly where you can enter a BYOK API key.

### First-time symlink fix

The `dev:web` script expects the `uv`-installed tool at `~/.local/share/uv/tools/anton/`, but it may be installed as `anton-agent`. If you see "Anton Python interpreter not found", run:

```bash
ln -s ~/.local/share/uv/tools/anton-agent ~/.local/share/uv/tools/anton
```

## Flushing local installs (fresh start)

`make flush` wipes every local install **and** all app state, returning the machine to a pre-install condition. Use it to test the from-scratch install flow or to recover from a broken/half-installed environment.

```bash
make flush          # prompts before deleting
make flush FORCE=1  # skip the prompt (CI / scripts)
```

It removes:

| Removed | What it is |
|---|---|
| `cowork-server` uv tool (+ legacy `anton-agent`) | the runtime the **Electron app** installs via `uv tool install` |
| `backend/core_api/.venv`, `backend/core_agent/.venv` | the venvs the **Makefile** dev flow builds via `uv sync` |
| `~/.anton` | provider keys / `.env` |
| `~/.cowork` | database, `hermes`, `projects` |

> ⚠️ Destructive — deletes conversations and saved provider keys, no undo. After flushing, the next `make setup` (or app launch) reinstalls everything from scratch.

> It deliberately leaves `uv` itself and uv-managed Python runtimes alone (shared infrastructure, not part of the anton/cowork install).
