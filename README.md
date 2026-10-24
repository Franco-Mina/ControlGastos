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

# Tests (also measures coverage; fails below 80%)
pytest

# Coverage report from the last run
coverage report -m

# Lint
ruff check .

# Apply migrations manually
alembic upgrade head

# Create a migration after changing models
alembic revision --autogenerate -m "add something"
```

For auto-reload while developing, set `DEBUG=true` in `.env`.

The test command measures Python coverage and fails if global coverage drops below
**80%**. The threshold and source package live under `[tool.coverage.*]` in
`pyproject.toml`; templates and migrations are not counted as Python statements.

## Project layout

```
app/
  main.py            FastAPI app, lifespan (migrate + seed), static mount
  config.py          Settings from environment / .env
  db.py              Engine, SessionLocal, get_db dependency
  models.py          Category, Expense, Income and ExchangeRate ORM models
  currencies.py      Currency registry and base-currency helpers
  exchange.py        DolarAPI provider, daily rate cache and conversion
  money.py           Per-currency display helpers for totals and charts
  services.py        Per-currency totals, category breakdown, trends, balances
  templating.py      Jinja2 env, money/month filters
  seed.py            Default category seeding
  routers/
    dashboard.py     GET /
    balance.py       GET /balance (income vs expenses)
    expenses.py      GET/POST /expenses, POST /expenses/{id}/delete
    incomes.py       GET/POST /incomes, POST /incomes/{id}/delete
  parsing.py         Shared amount parsing for forms
  templates/         dashboard, balance, expense/income lists and forms
    partials/        month picker, currency toggle, amount rendering macros
  static/css/        small style additions

migrations/          Alembic environment + versions
tests/               Smoke, currency and amount parsing tests
data/                SQLite database (gitignored)
```

## Data model

- **Category** — name (unique) and a display color.
- **Expense** — date, description, amount (`NUMERIC(12, 2)`), currency, optional category,
  payment method and notes.
- **Income** — date, description, amount, currency, optional source and notes.
- **ExchangeRate** — a daily cache of one rate per currency (`currency`, `rate`, `rate_date`,
  `source`).

Amounts are stored as decimals, never floats. Every expense and income keeps the currency it
was entered in.

## Multi-currency

`CURRENCY` in `.env` sets the **base currency** (ARS by default). Rates are stored as *units
of the base currency per one unit of the foreign currency*: with ARS as the base, a USD rate
of `1550` means `1 USD = 1,550 ARS`.

- USD rates are fetched from
  [dolarapi.com](https://dolarapi.com/v1/dolares/oficial) using the `venta` field.
- The rate is cached in the `exchange_rates` table, one row per currency and date. A new
  value is only fetched when there is no row for the current date.
- If the provider fails, the most recent stored rate is used and marked as outdated in the
  UI. If no rate exists at all, the app falls back to showing each currency separately
  instead of dropping amounts.
- The dashboard and balance pages have a **Mostrar montos en** toggle: `Ambas` shows each
  currency on its own line and chart, while `ARS` or `USD` converts every amount. The choice
  is saved in the `currency_view` cookie and can be overridden per request with `?view=ARS`,
  `?view=USD` or `?view=both`.
- Expense and income lists always show the original amounts, with the currency under each
  total.

To add a currency:

1. Add a `Currency(code, symbol, name)` entry to `CURRENCIES` in `app/currencies.py`.
2. If its rate can be fetched automatically, register a provider in `PROVIDERS` in
   `app/exchange.py`. Otherwise insert rates manually in `exchange_rates`.

No schema change is needed: new records simply store the new code.

Cached rates are quoted against the configured base currency, so if you change `CURRENCY`
after they exist, clear the `exchange_rates` table to have them fetched again.

## Notes

- The UI defaults to a dark theme. Use the sun/moon button in the header to switch to the
  light theme; the choice is saved in the browser (`localStorage`).
- The UI is in Spanish (`lang="es"`), including month names, dates and validation
  messages. Code, comments, identifiers, database columns and stored payment-method
  values remain in English. Category names are seeded in Spanish; migration `0002`
  renames the original English defaults.
- Tailwind is loaded from the CDN for zero build tooling. When you outgrow that, switch to
  the Tailwind CLI and a compiled stylesheet.
- The app is designed for a single local user. Before exposing it on a network, add
  authentication and put it behind a reverse proxy.

## Next steps

- [ ] Edit existing expenses and incomes
- [ ] Manage categories (add/rename/recolor) from the UI
- [ ] Budgets per category with progress warnings
- [ ] CSV import/export
- [ ] Recurring expenses and incomes
- [ ] More currencies and automatic rate providers
- [ ] Charts (e.g. Chart.js) for category and month comparisons
