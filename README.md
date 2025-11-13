# Nichifier Business Intelligence Platform

Nichifier is a cloneable business intelligence platform for curating industry-specific newsletters and periodical reports powered by AI-assisted content generation. The platform enables administrators to manage global appearance and cadence, niche administrators to tailor content for individual industries, and subscribers to consume curated insights.

## Features

- Multi-role access control (platform admins, niche admins, subscribers, anonymous visitors).
- Configurable AI-powered content generation guidelines per niche (style, tone, depth).
- Newsletter and report scheduling for daily, weekly, monthly, and quarterly cadences.
- Customisable themes, splash screen, and dashboard experiences.
- Secure authentication with JWT-backed session cookies and password hashing.
- Modular FastAPI backend with SQLAlchemy ORM and Pydantic schemas.
- Responsive UI using Bootstrap 5 with custom theming.
- End-to-end monetisation controls including curator subscription plans, Stripe key storage, and automatic platform fee splits.
- Comprehensive logging for debugging and monitoring.

## Repository Layout

```
app/
  config.py                # Application configuration management.
  database.py              # Database engine and session handling utilities.
  logger.py                # Structured logging setup.
  models.py                # SQLAlchemy ORM models.
  schemas.py               # Pydantic request/response schemas.
  security.py              # Authentication, password hashing, and JWT utilities.
  routers/                 # FastAPI routers by domain (auth, niches, admin, subscriptions).
  services/                # Business logic modules (newsletter generation, etc.).
  templates/               # Jinja2 HTML templates.
  static/                  # CSS, JS, and image assets.
nichifier_platform_server.py  # FastAPI application entrypoint.
pyproject.toml            # Project dependencies.
scripts/                  # Helper scripts for environment setup.
```

## Prerequisites

- Python 3.11 or later
- SQLite (bundled with Python standard library) – the async driver `aiosqlite` is
  installed automatically when you run `pip install -e .`

## Setup Instructions

### Linux / macOS / Raspberry Pi OS

```bash
# 1. Clone the repository
 git clone https://github.com/your-org/nichifier.git
 cd nichifier

# 2. Create and activate a virtual environment
 python3 -m venv .venv
 source .venv/bin/activate

# 3. Upgrade pip and install dependencies
 pip install --upgrade pip
 pip install -e .

# 4. Initialise the database (creates SQLite file and tables)
 python nichifier_platform_server.py --init-db

# 5. Promote yourself to niche admin so you can curate content
 python nichifier_platform_server.py --promote-user you@example.com --role niche_admin

# 6. Run the development server on a chosen port (default 8000)
 python nichifier_platform_server.py --host 0.0.0.0 --port 8080 --reload
```

### Windows PowerShell

```powershell
# 1. Clone the repository
 git clone https://github.com/your-org/nichifier.git
 Set-Location nichifier

# 2. Create and activate a virtual environment
 py -3 -m venv .venv
 .venv\Scripts\Activate.ps1

# 3. Upgrade pip and install dependencies
 python -m pip install --upgrade pip
 python -m pip install -e .

# 4. Initialise the database
 python nichifier_platform_server.py --init-db

# 5. Promote yourself to niche admin
 python nichifier_platform_server.py --promote-user you@example.com --role niche_admin

# 6. Run the development server
 python nichifier_platform_server.py --host 0.0.0.0 --port 8080 --reload
```

## Helper Scripts

- `scripts/setup_environment.sh` – Automates virtual environment creation and dependency installation on Linux/macOS.
- `scripts/setup_environment.ps1` – PowerShell equivalent for Windows.

Run the scripts with execution permission (Linux/macOS: `chmod +x scripts/setup_environment.sh && ./scripts/setup_environment.sh`). On Windows, ensure script execution is permitted (`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`).

## Operator CLI workflow

To unlock the niche editor or full admin dashboard for your own account, run the exact promotion command after registering your user:

```bash
python nichifier_platform_server.py --promote-user you@example.com --role niche_admin
```

Replace `you@example.com` with the email address you registered. Use `--role admin` if you require full platform administration; both roles automatically mark the account as premium for feature access.

## Usage Overview

1. Visit `http://localhost:8080` to view the public splash page listing all niches.
2. Create an account and sign in to access dashboards.
3. Platform admins can configure themes, cadences, and manage users.
4. Niche admins can curate niche pages, adjust AI tone/style, and schedule newsletters.
5. Subscribers can manage subscriptions and access premium reports with transparent billing summaries.

### Monetisation controls

- Platform administrators can access the hidden monetisation laboratory at `/admin/monetisation` (requires admin login).
- Use the “Platform fee configuration” form to set the revenue share and Stripe keys.
- Define curator plans (free, basic, pro, etc.) to control monthly pricing, niche limits, and platform fee discounts.
- Creators see these plans on their dashboard, and subscriber billing automatically applies the configured platform fees with the minimum charge enforced each cycle.

On-screen instructions across the app guide users; the README is primarily for operators and developers.

## Debugging

- Logs are emitted to the console with structured context via the `app.logger` module.
- Use the `--log-level` argument when starting the server to adjust verbosity.
- SQLAlchemy echoes can be toggled with the `DATABASE_ECHO` environment variable.

## Security Considerations

- Passwords are hashed using `argon2-cffi` with Argon2id parameters tuned for interactive logins.
- JWT tokens are signed and stored in HttpOnly cookies to mitigate XSS risks.
- Role-based dependency checks ensure sensitive routes are protected.
- All external API calls (e.g., news aggregation) time out quickly and validate responses.

## Testing

Install optional development dependencies and run tests with `pytest`.

```bash
pip install -e .[dev]
pytest
```

## License

MIT License. See `LICENSE` if provided.
