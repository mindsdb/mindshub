<a name="readme-top"></a>

<div align="center">

# MindsHub Cowork

**The unified workspace where open-source agents get work done for you.**

_Delegate anything. It comes back done._

[![Release](https://img.shields.io/github/v/release/mindsdb/minds?logo=github&label=release)](https://github.com/mindsdb/minds/releases)
[![Stars](https://img.shields.io/github/stars/mindsdb/minds?logo=github)](https://github.com/mindsdb/minds/stargazers)
[![License: MIT](https://img.shields.io/github/license/mindsdb/minds)](#-license)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20–%203.13-brightgreen.svg)](https://www.python.org/downloads/)

[Website](https://mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Docs](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Web app](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Pricing](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Discord](https://mindshub.ai/discord)

<p align="center">
  <sub>Read this in: <a href="README.zh.md">中文</a> · <a href="README.es.md">Español</a> · <a href="README.pt.md">Português</a> · <a href="README.hi.md">हिन्दी</a></sub>
</p>

</div>

<p align="center">
  <img alt="MindsHub Cowork — the unified workspace" width="100%" src="https://github.com/user-attachments/assets/769e6463-0a9d-45ae-83d1-ef9e234775d3" />
</p>

**MindsHub Cowork** is the unified workspace where you delegate entire tasks — research, analysis, reporting, scheduled operations — and collect finished, shareable results. Connect your data, route each step to the right model, run open-source agents, and turn their output into artifacts you can publish. It's open source and runs anywhere — your machine, your VPC, or the hosted app.

This repository is the **platform superproject**: it pulls together the desktop/web app, the agent backend, and the data engine so you can build and run the whole stack from source.

## Get started

Pick whichever fits:

- **Web — nothing to install.** Open **[console.mindshub.ai](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)** and sign in.
- **macOS.** [Download the desktop app](https://downloads.mindsdb.com/mindshub-cowork/mac/mindshub-cowork-latest.pkg) (`.pkg`).
- **Windows.** [Download the desktop app](https://downloads.mindsdb.com/mindshub-cowork/windows/mindshub-cowork-latest.exe) (`.exe`).
- **Run it open source.** [Build from source](#build-from-source) — see below.

Free to start. Pro adds all frontier models and private artifacts — see [pricing](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## What you can do

For every knowledge worker — creators, strategists, and operators:

- **Automate** repetitive, multi-step work that involves reading and writing: reports, monitoring, recurring workflows, and scheduled operations.
- **Build** internal AI tools and artifacts — apps, dashboards, decks, docs, analyses — without engineering, and publish them to a live URL to share with your team.

## What's inside

- **Connected data.** A secure vault links systems like BigQuery, Postgres, Gmail, Drive, HubSpot, Notion, and Linear. Credentials stay scoped per connection — agents never see raw keys.
- **Model Router.** Switch between frontier models (Claude, GPT, Gemini) and open models (DeepSeek, Qwen, Kimi) without wiring up a key for each provider.
- **Open agents.** Run interchangeable open-source harnesses — Anton (default) and Hermes — swappable from a dropdown.
- **Artifacts.** Turn agent output into documents, dashboards, apps, and code, and publish to a live URL.
- **Memory, skills & scheduling.** Cross-session memory, a reusable skill library, and tasks that run on a schedule.

## Build from source

**1. Clone the repository**

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds.git
cd minds
```

**2. Install dependencies**

```bash
make setup
```

**3. Run**

| Mode | Command |
|---|---|
| Desktop app (Electron) with hot reload | `make dev` or `make watch` |
| Web app in browser with hot reload | `make dev-web` |
| Production build | `make build` |
| Package for macOS | `make dist-mac` |
| Package for Windows | `make dist-win` |
| Build macOS `.app` from local uncommitted source | `make pack-local` |
| Wipe all local installs + data (fresh start) | `make flush` |

> **Fresh start:** `make flush` removes the local runtime (the `cowork-server` uv tool and the `backend/*/.venv`s) and deletes app state in `~/.anton` (provider keys) and `~/.cowork` (database, hermes, projects). Use it to test the from-scratch install flow or recover from a broken install. It prompts for confirmation — pass `FORCE=1` to skip. The next `make setup` or app launch reinstalls everything. ⚠️ This deletes your conversations and saved keys.

### Working on feature branches (submodules)

This repo is a superproject that pins each module (`frontend`, `backend/core_api`, `backend/core_agent`, `backend/data-vault`) to a commit. To work on module branches without polluting `git status` or fighting over pins:

**1. Pick your branches** in a gitignored `dev.env` (copy the template):

```bash
cp dev.env.example dev.env      # then set REF=feat/my-thing (or per-module API_REF=…)
```

**2. `make` follows it** — one knob, both run paths:

| Command | What it does |
|---|---|
| `make use` | check out your `dev.env` refs across all submodules |
| `make dev` / `make watch` | run the Electron app with live reload against local source |
| `make dev-web` | run the web SPA with live reload against local source |
| `make server` + `make app` | (re)install the desktop server from the configured branch, then launch |
| `make server-local` + `make app-local` | install the desktop server from **local uncommitted source**, then launch |
| `make pack-local` | build the macOS `.app` from local uncommitted source (no push needed) |
| `make refs` | show which refs the next run will use |
| `make baseline` | reset submodules to the pinned commits |
| `make pin` | record the current submodule commits as the superproject's pins (one deliberate commit) |

Submodules are configured with `ignore = all`, so your branch work never shows up as superproject changes — the parent `git status` stays clean. Pins move **only** via `make pin`. See [`CLAUDE.md`](CLAUDE.md) for the full workflow.

## Deploy anywhere

Cowork is built for flexible deployment — **cloud, VPC, on-prem, air-gapped, and hybrid** infrastructure — so you keep full control over your infrastructure, models, permissions, and data.

## Help & support

- **Ask a question** — join the [Discord community](https://mindshub.ai/discord).
- **Report a bug** — open a [GitHub issue](https://github.com/mindsdb/minds/issues) with reproduction steps.
- **Read the docs** — guides, setup, and the API at [docs.mindshub.ai](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).
- **Enterprise SLAs or custom deployments** — [contact the team](https://mindshub.ai/contact?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme).

## 🤝 Contribute

Cowork is open source and contributions are welcome — code, integrations, docs, bug reports, and feature ideas. Read the [docs](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) to get set up, browse [open issues](https://github.com/mindsdb/minds/issues), and say hi on [Discord](https://mindshub.ai/discord).

## 🔒 Security

Found a security vulnerability? Please **don't** open a public issue. Report it privately through our [security policy](https://github.com/mindsdb/minds/security).

## 📚 Resources

- [Documentation](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Blog](https://mindshub.ai/blog?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Brand guidelines & press kit](https://mindshub.ai/press-kit?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Discord community](https://mindshub.ai/discord)

## 📄 License

This repository is released under the [MIT License](LICENSE). Bundled components are governed by their own licenses — see each submodule's repository for details.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
