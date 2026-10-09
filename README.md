# SlopeAPI

SlopeAPI is a small, low-cost, open REST API for ski resorts and conditions.

```
EventBridge (every 30 min) -> poller Lambda -> Postgres <- API Lambda <- API Gateway <- clients
```

Data is collected on a schedule and served from our own database, so API traffic never causes upstream calls and idle cost is close to zero. See [docs/architecture.md](docs/architecture.md).

## Repo layout

| Path | What it is |
|---|---|
| `service/` | The Flask app: routes, models, providers, config, local `run.py`, `requirements.txt` (runtime) and `requirements-dev.txt` |
| `lambdas/` | AWS Lambda entry points (API and poller) that wrap the service |
| `infra/` | Terraform for all AWS resources; `infra/bootstrap/` is one-time setup |
| `.github/workflows/` | CI/CD (`deploy.yml` deploys on push to `main`) |
| `scripts/` | `package.sh` builds the Lambda bundle; `export_openapi.py` regenerates the spec |
| `docs/` | `architecture.md` and the generated `openapi.json` |

## API

Base path `/api/v1`. Interactive docs at `/api/v1/`, spec at `docs/openapi.json`.

- `GET /ski/resorts` (optional `name`)
- `GET /ski/resorts/{id}`
- `GET /ski/conditions` (optional `resort_id`)
- `GET /ski/conditions/{resort_id}`

Requests are rate limited per IP (default `60 per minute;1000 per day`); exceeding it returns `429`.

## Run locally

```sh
cd service
pip install -r requirements-dev.txt
python run.py            # http://127.0.0.1:4000/api/v1/
```

Seed data with the mock provider:

```py
from app import create_app
from app.tasks import poll_providers
app = create_app()
with app.app_context():
    poll_providers()
```

Regenerate the OpenAPI spec after changing endpoints: `python scripts/export_openapi.py`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `APP_CONFIG` | `config.DevelopmentConfig` | Config class (Lambda uses `config.ProductionConfig`) |
| `DATABASE_URL` | `sqlite:///dev.db` | Postgres URL in production |
| `RATELIMIT_DEFAULT` | `60 per minute;1000 per day` | Per-IP limit |
| `RATELIMIT_STORAGE_URI` | `memory://` | Redis URL for shared counters |
| `CACHE_MAX_AGE_SECONDS` | `300` | `Cache-Control` max-age on successful GETs (also sends `ETag`) |
| CONDITIONS_RETENTION_DAYS` | `7` | Older conditions are pruned by the poller |

## Deploying (via Terraform and GitHub Actions)

GitHub Actions deploys on every push to `main` using OIDC, so no AWS keys are stored in GitHub.
