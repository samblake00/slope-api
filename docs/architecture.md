# SlopeAPI Architecture

```
                     +-------------------+
 EventBridge  ------>|  poller Lambda    |---writes--->+------------+
 (rate 1 day)        | poll + prune      |             |  Postgres  |
                     +-------------------+             | (Neon/     |
                                                       |  Supabase) |
 Clients --> API Gateway (HTTP API) --> API Lambda --reads-->+------------+
            global throttle             Flask + per-IP limiter
```

## Principles
- **Reads never hit upstream.** The poller is the only thing that talks to data providers; the API only reads our database.
- **Pay for use.** Lambda, API Gateway and EventBridge cost nothing when idle; Postgres is a free tier.
- **Bounded cost.** Rate limiting at two layers, an optional Lambda concurrency cap, and pruning of old data.

## Components
| Component | Code | Notes |
|---|---|---|
| Flask app | `service/app/` | `modules/ski` holds the routes, `models.py` the schema, `providers/` the data sources, `tasks.py` the poll and prune logic |
| API Lambda | `lambdas/lambda_handlers.py:api_handler` | Adapts API Gateway HTTP API (v2) events to the Flask WSGI app via `apig-wsgi` |
| Poller Lambda | `lambdas/lambda_handlers.py:poller_handler` | Creates tables, runs `poll_providers`, then `prune_conditions` |
| Infra | `infra/main.tf` | Lambdas, HTTP API, throttle, EventBridge rule, log groups, IAM |
| Bootstrap | `infra/bootstrap/main.tf` | State bucket, GitHub OIDC provider, deploy role (run once by hand) |
| CI/CD | `.github/workflows/deploy.yml` | Package, `terraform apply` on push to `main` |

## Rate limiting
1. **API Gateway throttle** (`throttle_rate_limit`, `throttle_burst_limit`): hard global cap shared by all containers.
2. **Flask-Limiter** per IP (`RATELIMIT_DEFAULT`): friendly `429` responses. Counters are per Lambda container unless `RATELIMIT_STORAGE_URI` points at Redis.

## Caching
Successful GETs carry Cache-Control: public, max-age=300 and an ETag, so a CDN (e.g. Cloudflare free tier) can absorb most reads.

## Data flow
1. EventBridge triggers the poller once a day.
2. On its first run the poller seeds ~3,100 resorts from the bundled OpenStreetMap extract (service/app/data/resorts.json). Every run it fetches weather from Open-Meteo for the resorts with the oldest conditions (up to POLL_BATCH_SIZE), paced under the free-tier limit of 600 locations/minute, then deletes conditions older than CONDITIONS_RETENTION_DAYS. A full refresh takes about 6 minutes.
3. API requests read the latest rows from Postgres.

## Adding a data provider
Implement the interface in `service/app/providers/base.py` (see `osm.py` and `openmeteo.py`), then call it from `seed_resorts` / `poll_conditions` in `service/app/tasks.py`.
