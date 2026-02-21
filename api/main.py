from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, validator
from web3 import Web3
import logging
import re

from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from .config import settings
from .database import init_db, create_tables, close_db, get_db
from .models import FaucetRequest as DBFaucetRequest
from .rate_limiter import RateLimiter
from .faucet_service import FaucetService

if settings.SENTRY_ENABLED and settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        environment=settings.ENVIRONMENT,
    )

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VERCEL_PREVIEW_PATTERNS = [
    re.compile(r"^https://frontend-[a-z0-9]+-ethernalllc-funds-projects\.vercel\.app$"),
    re.compile(r"^https://frontend-git-[a-zA-Z0-9\-]+-ethernalllc-funds-projects\.vercel\.app$"),
]

LOCALHOST_PATTERN = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")

def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in settings.CORS_ORIGINS:
        return True
    for pattern in VERCEL_PREVIEW_PATTERNS:
        if pattern.match(origin):
            return True
    if settings.ENVIRONMENT != "production" and LOCALHOST_PATTERN.match(origin):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    if settings.ENABLE_DB:
        init_db()
        await create_tables()
        logger.info("Database initialized")

    yield

    if settings.ENABLE_DB:
        await close_db()
    logger.info("Application shutdown complete")

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready USDC testnet token distribution",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        allowed = is_origin_allowed(origin)
        if request.method == "OPTIONS":
            if allowed:
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                        "Access-Control-Max-Age": "86400",
                    }
                )
            else:
                logger.warning(f"CORS preflight rejected for origin: {origin}")
                return Response(status_code=403)
        response = await call_next(request)

        if allowed and origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
        
        return response

app.add_middleware(DynamicCORSMiddleware)
faucet_service = FaucetService()
rate_limiter = RateLimiter()

class FaucetRequestModel(BaseModel):
    address: str = Field(..., description="Ethereum address")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile token")

    @validator('address')
    def validate_address(cls, v):
        if not Web3.is_address(v):
            raise ValueError('Invalid Ethereum address')
        return Web3.to_checksum_address(v)

class FaucetResponse(BaseModel):
    success: bool
    message: str
    tx_hash: Optional[str] = None
    amount: Optional[float] = None
    balance: Optional[float] = None
    wait_time: Optional[int] = None

async def verify_admin_key(request: Request):
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin API not configured")
    api_key = request.headers.get(settings.API_KEY_HEADER)
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "network": settings.NETWORK_NAME,
        "chain_id": settings.CHAIN_ID,
        "contract": settings.CONTRACT_ADDRESS,
        "features": {
            "database": settings.ENABLE_DB,
            "redis": settings.ENABLE_REDIS,
            "turnstile": settings.TURNSTILE_ENABLED,
        },
        "endpoints": {
            "faucet": "POST /faucet",
            "balance": "GET /balance/{address}",
            "health": "GET /health",
            "stats": "GET /stats",
            "admin": "GET /admin/*"
        }
    }

@app.get("/health")
async def health_check():
    try:
        is_connected = faucet_service.w3.is_connected()
        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)
        redis_ok = rate_limiter.use_redis
        status = "healthy" if (is_connected and faucet_balance > 0) else "degraded"

        return {
            "status": status,
            "rpc_connected": is_connected,
            "faucet_balance": faucet_balance,
            "redis_available": redis_ok,
            "database_enabled": settings.ENABLE_DB,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/faucet", response_model=FaucetResponse)
async def request_tokens(request: Request, faucet_req: FaucetRequestModel):
    client_ip = request.client.host
    address = faucet_req.address

    try:
        if settings.RATE_LIMIT_ENABLED:
            ip_allowed, ip_wait = rate_limiter.check_ip(client_ip)
            if not ip_allowed:
                return FaucetResponse(
                    success=False,
                    message=f"Rate limit exceeded. Try again in {ip_wait} seconds.",
                    wait_time=ip_wait
                )

            wallet_allowed, wallet_wait = rate_limiter.check_wallet(address)
            if not wallet_allowed:
                return FaucetResponse(
                    success=False,
                    message=f"Wallet already received tokens recently. Try again in {wallet_wait} seconds.",
                    wait_time=wallet_wait
                )

        if settings.TURNSTILE_ENABLED and faucet_req.turnstile_token:
            pass  # TODO: Implement Turnstile verification

        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)
        if faucet_balance < settings.FAUCET_AMOUNT:
            logger.warning(f"Faucet running low: {faucet_balance} USDC")
            raise HTTPException(
                status_code=503,
                detail="Faucet temporarily unavailable - insufficient balance"
            )

        db_request = None
        if settings.ENABLE_DB:
            async with get_db() as db:
                from sqlalchemy import insert
                stmt = insert(DBFaucetRequest).values(
                    wallet_address=address,
                    ip_address=client_ip,
                    amount=settings.FAUCET_AMOUNT,
                    status="processing",
                )
                result = await db.execute(stmt)
                await db.commit()

        tx_hash = faucet_service.send_tokens(address, settings.FAUCET_AMOUNT)
        rate_limiter.record_request(client_ip, address)

        if settings.ENABLE_DB and db_request:
            async with get_db() as db:
                from sqlalchemy import update
                stmt = update(DBFaucetRequest).where(
                    DBFaucetRequest.wallet_address == address
                ).values(
                    status="completed",
                    tx_hash=tx_hash,
                    completed_at=datetime.utcnow()
                )
                await db.execute(stmt)
                await db.commit()

        new_balance = faucet_service.get_balance(address)
        logger.info(
            f"Sent {settings.FAUCET_AMOUNT} USDC to {address} "
            f"(IP: {client_ip}, Tx: {tx_hash})"
        )

        return FaucetResponse(
            success=True,
            message=f"Successfully sent {settings.FAUCET_AMOUNT} USDC",
            tx_hash=tx_hash,
            amount=settings.FAUCET_AMOUNT,
            balance=new_balance
        )

    except Exception as e:
        logger.error(f"Faucet request failed for {address}: {e}")
        if settings.ENABLE_DB:
            try:
                async with get_db() as db:
                    from sqlalchemy import update
                    stmt = update(DBFaucetRequest).where(
                        DBFaucetRequest.wallet_address == address
                    ).values(
                        status="failed",
                        error_message=str(e)
                    )
                    await db.execute(stmt)
                    await db.commit()
            except Exception:
                pass

        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balance/{address}")
async def get_balance(address: str):
    try:
        if not Web3.is_address(address):
            raise HTTPException(status_code=400, detail="Invalid address")
        checksum_address = Web3.to_checksum_address(address)
        balance = faucet_service.get_balance(checksum_address)

        return {
            "address": checksum_address,
            "balance": balance,
            "symbol": "USDC",
            "decimals": 6
        }
    except Exception as e:
        logger.error(f"Balance check failed for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    try:
        stats = rate_limiter.get_stats()
        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)

        return {
            "faucet_balance": faucet_balance,
            "total_requests": stats["total_requests"],
            "unique_wallets": stats["unique_wallets"],
            "unique_ips": stats["unique_ips"],
            "amount_per_request": settings.FAUCET_AMOUNT,
            "using_redis": stats["using_redis"],
            "rate_limits": {
                "per_ip_seconds": settings.RATE_LIMIT_IP_SECONDS,
                "per_wallet_seconds": settings.RATE_LIMIT_WALLET_SECONDS
            }
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/stats", dependencies=[Depends(verify_admin_key)])
async def admin_stats():
    try:
        if not settings.ENABLE_DB:
            raise HTTPException(status_code=501, detail="Database not enabled")
        async with get_db() as db:
            from sqlalchemy import select, func
            stmt = select(func.count(DBFaucetRequest.id))
            result = await db.execute(stmt)
            total = result.scalar()

            stmt = select(
                DBFaucetRequest.status,
                func.count(DBFaucetRequest.id)
            ).group_by(DBFaucetRequest.status)
            result = await db.execute(stmt)
            by_status = dict(result.all())

            return {
                "total_requests": total,
                "by_status": by_status,
                "faucet_balance": faucet_service.get_balance(settings.FAUCET_ADDRESS),
            }
    except Exception as e:
        logger.error(f"Admin stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )