# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

MoveMap is a personal-use tool that lets users (mainly Japanese 50-60s pre-retirement) compare all 47 prefectures across 7 indicators, with ARIMA/Prophet AI forecasts at 3/5/10-year horizons. Streamlit UI + DuckDB + monthly batch ETL from 6 public Japanese data sources. The tool is **personal/individual use only** (DEC-005) — no auth, no multi-tenant code paths.

Disclaimer (`INV-BIZ-005`) MUST always be visible on the MAP screens. Don't refactor it away.

## Common commands

All commands use `uv` and assume the repo root as cwd. `python -m uv` is the explicit form used in docs; `uv` alone also works.

```sh
# Install deps (first time / after pyproject changes)
python -m uv sync --extra dev

# Init DuckDB schema + master seeds (idempotent)
python -m uv run python scripts/seed.py

# Init schema + 24 months of synthetic history for the 4 predictable indicators
# (enables full pipeline + UI demo with no API keys)
python -m uv run python scripts/seed.py --with-synthetic-history

# Fetch the Japan prefecture GeoJSON (~3.2MB, required for choropleth)
python -m uv run python scripts/fetch_geojson.py

# Run the Streamlit app → http://localhost:8501
python -m uv run streamlit run app/main.py

# Monthly batch (ETL + retrain + predict). Without API keys: returns 'partial'.
python -m uv run python scripts/run_batch.py

# DB snapshot (retention 12) / restore
python -m uv run python scripts/snapshot.py
python -m uv run python scripts/restore.py
```

### Tests

```sh
# Default: excludes 'slow' marker (configured in pyproject.toml addopts)
python -m uv run pytest tests/ -v

# Single category
python -m uv run pytest tests/unit -v
python -m uv run pytest tests/integration -v
python -m uv run pytest tests/smoke -v             # Streamlit AppTest, slower

# A single test file or test
python -m uv run pytest tests/unit/test_arima_model.py -v
python -m uv run pytest tests/unit/test_arima_model.py::test_fit_returns_predictions -v

# Slow tests (E2E with ARIMA training) — explicitly opt-in
python -m uv run pytest -m slow
```

`tests/conftest.py` provides two fixtures: `db` (in-memory DuckDB + DDL + minimal masters) and `db_with_history` (adds 24mo × 3 prefs × 4 indicators of synthetic history for prediction tests). Use them — do NOT create new in-memory DBs ad-hoc.

### Lint / type check

```sh
python -m uv run ruff check . --fix
python -m uv run mypy app/        # mypy is non-strict, CI has continue-on-error
```

## Architecture (read before changing structure)

**Pattern: Vertical Slice Architecture (VSA)** — code under `app/features/<feature>/usecases/<use_case>.py`. One file per SF (System Function from Phase 4). Don't introduce a service/repository layer between usecases and `app/shared/db.py`.

```
app/
├── main.py                              # Streamlit entrypoint, composes tabs
├── domain/                              # Pure data classes (no I/O)
├── shared/                              # Cross-feature: config, db, logger, http_client, ui_theme, geo
│   ├── db.py                            # DuckDB connect/DDL/transaction + HistoryProtectedConnection
│   ├── http_client.py                   # httpx + truststore (corp SSL) + tenacity retries
│   └── config.py                        # Config dataclass, .env loaded via python-dotenv
└── features/
    ├── map_view/                        # UI feature (read-only)
    │   ├── data_provider.py             # DB → dummy fallback facade for UI
    │   ├── dummy.py                     # Deterministic synthetic data (hash-based)
    │   ├── components/                  # heatmap, status_panel
    │   └── usecases/                    # show_map, show_ranking, show_comparison, switch_indicator, ...
    ├── data_pipeline/                   # ETL + forecasting feature (mutation)
    │   ├── sources/                     # One adapter per external API (e-Stat, MLIT, ...)
    │   ├── models/                      # arima.py, prophet_model.py
    │   └── usecases/                    # run_batch (orchestrator) + fetch/normalize/upsert/append/retrain/...
    └── compliance/                      # Disclaimer + data source list (small feature for INV-BIZ-005)
```

### Data flow

1. UI (`app/main.py`) calls `map_view/usecases/*` which call `map_view/data_provider.py`.
2. `data_provider` connects to DuckDB read-only; if file missing or table empty, returns `dummy.py` synthetic values with `DataAvailability(source="dummy")`. The UI surfaces this distinction via the status panel.
3. `scripts/run_batch.py` → `data_pipeline/usecases/run_batch.py` orchestrates the monthly ETL pipeline: `fetch → normalize → upsert + append-history → retrain → evaluate → predict → apply_fallback → log_batch_outcome`.
4. GitHub Actions cron (`.github/workflows/monthly-batch.yml`) triggers `run_batch.py` monthly at 02:00 JST.

### Invariants — 18 total, in `outputs/baseline.md`

The codebase enforces 18 invariants (INV-BIZ × 5, INV-DATA × 8, INV-EXT × 3, INV-IDEM × 2). Some are physical (DB CHECK/FK constraints in `app/shared/db.py`), some are runtime-enforced (e.g. `HistoryProtectedConnection` blocks UPDATE/DELETE/TRUNCATE on `historical_values` — **INV-DATA-007**). When touching the data pipeline or DB layer, check `outputs/baseline.md` and avoid weakening these.

Notable:
- **INV-DATA-007** (`historical_values` is append-only) is enforced by `HistoryProtectedConnection` in `app/shared/db.py`. To bypass for legitimate DDL/admin work, use `connect(protect_history=False)`.
- **INV-EXT-001**: External API failures keep previous values (no writes). `run_batch.py` records the failure but continues — partial status is the norm, not an error.
- **INV-BIZ-003**: A model with R² < 0.6 must produce `quality_status='no_prediction'`. `apply_fallback` handles this.
- **INV-IDEM-001**: `run_batch` must be re-runnable in the same month with identical results — implemented via upsert + append-only history.

### Indicators

- **7 indicators total**: `price_index`, `land_price`, `rent_index`, `birth_count`, `air_quality`, `disaster_risk`, `transport_access`.
- **Only 4 are predictable** (`is_predictable=true`): the first four. The remaining three are static lookups. Don't predict on non-predictable indicators (**INV-DATA-004**). The frozenset `PREDICTABLE_INDICATORS` in `app/features/map_view/dummy.py` is the canonical list for UI; seeds/indicators.csv is the canonical DB.

## Operating modes

| Mode | API keys | DB state | Effect |
|---|---|---|---|
| Demo | none | empty | UI shows 🟡 dummy everywhere |
| Synthetic history | none | `seed.py --with-synthetic-history` ran | History real; current 🟡 dummy; predictions 🔵 from models |
| Production | reinfolib/e-Stat keys in `.env` + `run_batch.py` | populated | All 🔵 real data |

The UI displays the source badge (DB vs dummy) via `DataAvailability` — do not remove this signal when refactoring.

## Conventions specific to this codebase

- **Japanese comments + docstrings.** The codebase comments are largely in Japanese (matching the domain). Match the existing language when editing.
- **SF-XXX / INV-* identifiers** in docstrings and commit messages refer to Phase 4 system functions and invariants in `outputs/`. Preserve them when refactoring — they are traced.
- **No new top-level abstractions without a phase doc.** Architecture decisions live in `outputs/05_architecture.md` and `outputs/06_system_design/`. If you're tempted to add a service/repo/factory layer, that's outside the VSA pattern this project committed to.
- **Use `connect()` from `app/shared/db.py`**, not raw `duckdb.connect()` — the protection wrapper is the point.
- **Config via `load_config()`**, not direct `os.getenv` reads.
- **Logger**: use `from app.shared.logger import get_logger; logger = get_logger(__name__)`. Logs go to `logs/` (rotated).
- **truststore is intentional** for corporate SSL environments — don't remove `truststore.inject_into_ssl()` from `http_client.py`.

## Where to look first

- New external data source? → `app/features/data_pipeline/sources/_base.py` + an existing adapter (e.g. `estat.py`).
- New indicator? → `seeds/indicators.csv` + `dummy.py` ranges + (if predictable) verify the retrain/evaluate path handles it.
- UI change? → `app/main.py` for layout; `app/features/map_view/usecases/` for tab content; `app/shared/ui_theme.py` for global CSS (50-60s-targeted readability tweaks).
- Pipeline change? → `app/features/data_pipeline/usecases/run_batch.py` is the orchestrator, the others are step usecases.
- Design rationale? → `outputs/00_problem.md` through `outputs/99_review.md` (Phase 0-8). `STARTUP.md` for setup details.
