# Expenses

A small, personal expense tracker built with **FastAPI**, **SQLite** and **Jinja2**.
Log expenses and see where your money goes — by month and by year.

## Stack

| Layer     | Choice                                   |
| --------- | ---------------------------------------- |
| Backend   | FastAPI + Uvicorn                        |
| Templates | Jinja2 (server-rendered)                 |
| Styling   | Tailwind CSS via CDN                     |
| Database  | SQLite + SQLAlchemy 2.0                  |
| Migrations| Alembic (applied automatically on start) |
| Tests     | pytest + FastAPI TestClient              |

## Quick start

PowerShell, from the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m app.main
```

Then open <http://127.0.0.1:8000>.

> If PowerShell blocks the activation script, either allow it for this session with
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or skip activation and use
> `.\.venv\Scripts\python.exe -m ...` for each command.

The database is created automatically at `data/expenses.db`, migrations are applied on
startup, and a set of default categories is seeded.

## Everyday commands

```powershell
# Run with auto-reload (reads HOST / PORT / DEBUG from .env)
python -m app.main

# Tests
pytest

# Lint
ruff check .

# Apply migrations manually
alembic upgrade head

# Create a migration after changing models
alembic revision --autogenerate -m "add something"
```

For auto-reload while developing, set `DEBUG=true` in `.env`.

## Project layout

```
app/
  main.py            FastAPI app, lifespan (migrate + seed), static mount
  config.py          Settings from environment / .env
  db.py              Engine, SessionLocal, get_db dependency
  models.py          Category and Expense ORM models
  services.py        Month/year totals, category breakdown, trends
  templating.py      Jinja2 env, money/month filters
  seed.py            Default category seeding
  routers/
    dashboard.py     GET /
    expenses.py      GET/POST /expenses, POST /expenses/{id}/delete
  templates/         base.html, dashboard, expense list + form
  static/css/        small style additions

migrations/          Alembic environment + versions
tests/               Smoke tests and amount parsing tests
data/                SQLite database (gitignored)
```

## Data model

- **Category** — name (unique) and a display color.
- **Expense** — date, description, amount (`NUMERIC(12, 2)`), optional category, payment
  method and notes.

Amounts are stored as decimals, never floats. The display currency is set with `CURRENCY`
in `.env` (`USD` by default).

## Notes

- The UI is in Spanish (`lang="es"`), including month names, dates and validation
  messages. Code, comments, identifiers, database columns and stored payment-method
  values remain in English. Category names are seeded in Spanish; migration `0002`
  renames the original English defaults.
- Tailwind is loaded from the CDN for zero build tooling. When you outgrow that, switch to
  the Tailwind CLI and a compiled stylesheet.
- The app is designed for a single local user. Before exposing it on a network, add
  authentication and put it behind a reverse proxy.

## Next steps

- [ ] Edit existing expenses
- [ ] Manage categories (add/rename/recolor) from the UI
- [ ] Budgets per category with progress warnings
- [ ] CSV import/export
- [ ] Recurring expenses
- [ ] Charts (e.g. Chart.js) for category and month comparisons
