# ETHERNAL FAUCET API - PRODUCTION SYSTEM
# ========================================

## Stack Tecnológico

- **Backend:** FastAPI 0.109.2 + Python 3.11
- **Database:** PostgreSQL 15 (Supabase)
- **Cache:** Redis 7 (Upstash)  
- **Queue:** Celery 5.3.6
- **Monitoring:** Sentry
- **Anti-Bot:** Cloudflare Turnstile
- **Deployment:** Docker + Render

## Estructura Completa

ethernal-faucet-api/
├── api/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic validation
│   ├── dependencies.py      # Dependency injection
│   │
│   ├── services/
│   │   ├── faucet.py       # Token distribution logic
│   │   ├── rate_limiter.py # Redis-based rate limiting
│   │   ├── turnstile.py    # Cloudflare bot protection
│   │   └── analytics.py    # Statistics & metrics
│   │
│   ├── tasks/
│   │   ├── celery_app.py   # Celery configuration
│   │   └── workers.py      # Background task workers
│   │
│   └── routers/
│       ├── faucet.py       # Faucet API endpoints
│       ├── admin.py        # Admin panel endpoints
│       └── health.py       # Health & monitoring
│
├── migrations/             # Database migrations (Alembic)
├── tests/                  # Unit & integration tests
├── scripts/                # Utility scripts
├── Dockerfile             # Production container
├── docker-compose.yml     # Local development
├── render.yaml            # Render deployment config
└── requirements.txt       # Python dependencies (pinned)

## Features

✅ **Persistent Rate Limiting** - Redis-backed, survives restarts
✅ **Database Tracking** - Full transaction history in PostgreSQL
✅ **Background Jobs** - Celery for async token distribution
✅ **Anti-Bot Protection** - Cloudflare Turnstile integration
✅ **Error Tracking** - Sentry monitoring & alerts
✅ **Admin Dashboard** - Protected endpoints for management
✅ **Health Checks** - Comprehensive service monitoring
✅ **Analytics** - Daily stats & fraud detection
✅ **Docker Support** - Ready for any platform
✅ **Auto-scaling** - Celery workers scale independently

## Deployment Options

1. **Render (Recommended)**
   - Blueprint deployment with render.yaml
   - Auto-deploy on git push
   - Free tier available

2. **Docker Compose (Local/VPS)**
   - Full stack in containers
   - Redis + PostgreSQL included
   - Production-ready with nginx

3. **Kubernetes**
   - Helm charts included
   - Horizontal pod autoscaling
   - Enterprise-grade

## Environment Variables (Render)

Required:
- FAUCET_PRIVATE_KEY
- DATABASE_URL (Supabase)
- REDIS_URL (Upstash)
- TURNSTILE_SECRET_KEY
- SENTRY_DSN

Optional:
- ADMIN_API_KEY
- FAUCET_AMOUNT=100
- RATE_LIMIT_IP_SECONDS=3600
- RATE_LIMIT_WALLET_SECONDS=86400

## Quick Start

1. Install dependencies:
   pip install -r requirements.txt

2. Setup database:
   alembic upgrade head

3. Run locally:
   uvicorn api.main:app --reload

4. Run with Celery:
   celery -A api.tasks.celery_app worker -l info

5. Deploy to Render:
   git push → auto-deploys

## Services Setup

### Supabase (Database)
1. Create project at supabase.com
2. Copy DATABASE_URL from settings
3. Run migrations: alembic upgrade head

### Upstash (Redis)
1. Create database at upstash.com
2. Copy REDIS_URL (with password)
3. Enable TLS connection

### Cloudflare Turnstile
1. Add site at cloudflare.com/turnstile
2. Get secret key
3. Add to TURNSTILE_SECRET_KEY

### Sentry
1. Create project at sentry.io
2. Copy DSN
3. Add to SENTRY_DSN

## Cost Estimate (Monthly)

- Render Web Service: $7 (Starter) or Free
- Supabase: Free tier (500MB)
- Upstash Redis: Free tier (10k commands/day)
- Sentry: Free tier (5k events/month)
- Cloudflare Turnstile: Free

**Total: $0-7/month** for small scale
**Production: ~$25/month** with paid tiers

## Monitoring

- Health: GET /health
- Metrics: GET /admin/stats (requires API key)
- Logs: Sentry dashboard
- Celery: Flower UI at :5555

## Security Features

- Rate limiting (IP + wallet)
- Turnstile verification
- Admin API key protection
- Blacklist system
- SQL injection protection
- CORS restrictions
- Request logging
- Fraud detection scoring

## Performance

- Redis caching: <10ms lookups
- Async DB queries: SQLAlchemy async
- Background processing: Celery
- Connection pooling: 10 connections
- Auto-retry: Failed transactions
- Graceful shutdown: Signal handling

## Testing

pytest                    # All tests
pytest tests/test_faucet.py  # Specific test
pytest --cov             # Coverage report

## Production Checklist

☐ Set all environment variables
☐ Run database migrations
☐ Configure Turnstile domain
☐ Set up Sentry project
☐ Add production CORS origins
☐ Enable rate limiting
☐ Set ADMIN_API_KEY
☐ Test health endpoint
☐ Monitor first 24h closely
☐ Set up balance alerts