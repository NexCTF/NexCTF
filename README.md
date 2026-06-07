# NexCTF

A self-hosted, extensible Capture The Flag platform with multi-question challenges, team-based scoring, sequential prerequisites, real-time scoreboard, TOTP 2FA, OAuth2/OIDC, custom fields, a job scheduler, and a plugin system for custom challenge/solution types.

[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Screenshots
<table>
  <tr>
    <td align="center"><img src="img/challenges.png" alt="Challenges"/><br/><sub>Challenges</sub></td>
    <td align="center"><img src="img/challenge_details.png" alt="Challenge details"/><br/><sub>Challenge details</sub></td>
    <td align="center"><img src="img/scoreboard.png" alt="Scoreboard"/><br/><sub>Scoreboard</sub></td>
  </tr>
</table>

### Admin
<table>
  <tr>
    <td align="center"><img src="img/admin_dashboard.png" alt="Dashboard"/><br/><sub>Dashboard</sub></td>
    <td align="center"><img src="img/admin_challenge_edit.png" alt="Challenge editor"/><br/><sub>Challenge editor</sub></td>
    <td align="center"><img src="img/admin_submissions.png" alt="Submissions"/><br/><sub>Submission log</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="img/admin_user_details.png" alt="User details"/><br/><sub>User details</sub></td>
    <td align="center"><img src="img/admin_team_details.png" alt="Team details"/><br/><sub>Team details</sub></td>
    <td align="center"><img src="img/admin_plugins.png" alt="Plugin management"/><br/><sub>Plugin management</sub></td>
  </tr>
</table>

## Quick Start

```bash
# Download the compose.yml
curl -O https://raw.githubusercontent.com/nexctf/nexctf/main/compose.yml

# Add /etc/hosts entry
echo "127.0.0.1 nexctf.local s3.nexctf.local" | sudo tee -a /etc/hosts

# Start the docker stack
docker compose up -d
```

The app is available at **https://nexctf.local:8443**.

## Features
### 🎯 Challenges & Scoring
- Sequential challenges with prerequisite enforcement
- Multi-question challenges with per-question scoring, categories, tags, S3 attachments
- Multiple solution types: text, code editor, multiple choice, long text
- Hints with configurable point costs and title
- Team-based scoring with configurable max team size
- Per-question points and wrong-answer penalties
- Manual score adjustments (bonuses/penalties) with reason tracking
- Live scoreboard with caching and SSE

### 👥 Users & Teams
- Roles: admin, moderator, user
- Custom fields on users and teams (string, integer, boolean, URL)
- Registration and team creation can be enabled/disabled, optional CAPTCHA
- **Security** — TOTP 2FA, multiple API tokens per user
  - OAuth2 / OpenID Connect login with configurable providers
  - Built-in OAuth2/OIDC server

### 🛠️ Administration
- Dashboard with audit log and statistics
- Competition settings (name, logo, colors, start/end times, rate limits)
- Full CRUD for challenges, questions, categories, hints, solutions, and tags
- File manager and notification broadcast (global or per-team)
- Scheduler — one-shot or cron-based jobs
- Custom Markdown pages
- **Plugins** — register custom challenge types, solution strategies, scheduler jobs, and frontend components
  - Plugins own their DB tables with Alembic migrations
  - Plugin-scoped config keys auto-prefixed and merged with core config

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python 3.14 + FastAPI + SQLAlchemy 2 (async) |
| Frontend | React 19 + TanStack Router/Query + Tailwind CSS 4 + shadcn |
| Database | PostgreSQL 18+ |
| Cache | Valkey 9 (Redis-compatible) |
| Storage | Maxio (S3-compatible) |

## Development
```bash
task dev:infra:up       # Start dev infrastructure (db, cache, s3)
task dev:infra:down     # Stop dev infrastructure
task dev:backend:       # Start the dev backend
task dev:backend:test   # Run backend tests
task dev:frontend:      # Start the dev frontend
```

### AI transparency disclosure
AI-assisted contributions are accepted. Disclosure is required on all AI-assisted PRs.

The same quality and security bar applies regardless of how code was written. Transparency about AI use helps keep its role in this project bounded — there is a wide spectrum between thoughtful autocomplete
and unchecked generation, and this project sits firmly at the former end.

Architectural and security decisions remain 100% human.
