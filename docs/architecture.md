# SlopeAPI Architecture

```
                     +-------------------+
 EventBridge  ------>|  poller Lambda    |---writes--->+------------+
 (rate 30 min)       | poll + prune      |             |  Postgres  |
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
1. EventBridge triggers the poller every 30 minutes.
2. The poller upserts resorts, inserts a conditions row per resort, and deletes conditions older than `CONDITIONS_RETENTION_DAYS`.
3. API requests read the latest rows from Postgres.

## Adding a data provider
Implement the interface in `service/app/providers/base.py`, then call it from `poll_providers` in `service/app/tasks.py`.
