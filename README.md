# SlopeAPI

SlopeAPI is a small, low-cost, open REST API for ski resorts and conditions.

```
EventBridge (daily) -> poller Lambda -> Postgres <- API Lambda <- API Gateway <- clients
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

List endpoints are paginated with `limit` (default 100, max 500) and `offset`, and return the total in an `X-Total-Count` header. Conditions are the latest reading per resort.

Requests are rate limited per IP (default `60 per minute;1000 per day`); exceeding it returns `429`.

## Run locally

```sh
cd service
pip install -r requirements-dev.txt
python run.py            # http://127.0.0.1:4000/api/v1/
```

Locally the app uses fake sample data (`DATA_SOURCE=mock`). To load it:

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
| `CACHE_MAX_AGE_SECONDS` | `3600` | `Cache-Control` max-age on successful GETs (also sends `ETag`) |
| `DATA_SOURCE` | `mock` locally, `live` in production | `live` = real resorts and weather, `mock` = fake sample data |
| `POLL_BATCH_SIZE` | `4000` | Max resorts refreshed per poll (stalest first) |
| `CONDITIONS_RETENTION_DAYS` | `7` | Older conditions are pruned by the poller |

## Deploying (via Terraform and GitHub Actions)

GitHub Actions deploys on every push to `main` using OIDC, so no AWS keys are stored in GitHub.

The deploy role can only be assumed by `samblake00/slope-api` on `main`, matched by GitHub's immutable OIDC subject (`github_subject_prefix` in `infra/bootstrap/main.tf`). The region is set in `.github/workflows/deploy.yml` (default `us-east-1`).

## Data sources

| Data | Source | How |
|---|---|---|
| Resorts (~3,100: name, coordinates, website where known) | [OpenStreetMap](https://www.openstreetmap.org/copyright) (landuse=winter_sports) | One-time seed from the bundled service/app/data/resorts.json, loaded by the poller on its first run. Rebuild the file with python scripts/fetch_resorts.py; to load new entries into a live database, invoke the poller with {"reseed": true}. |
| Temperature and snow depth | [Open-Meteo](https://open-meteo.com/) | The poller refreshes every resort once a day, paced to stay inside the free tier (600 locations/minute, 10,000/day). |

Open-Meteo's free tier is for non-commercial use. A commercial service needs their paid plan.

Open/closed status, runs open and hours are not available from these sources, so those fields are empty for most resorts. The OpenStreetMap extract also contains some non-downhill entries (cross-country trails, nordic centres).

Attribution: resort data (c) OpenStreetMap contributors, licensed under the [ODbL](https://opendatacommons.org/licenses/odbl/). Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).