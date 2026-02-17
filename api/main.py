"""
Ethernal MockUSDC Faucet API
FastAPI backend for automated testnet USDC distribution
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from web3 import Web3
import logging
from datetime import datetime
from typing import Optional

from .faucet_service import FaucetService
from .rate_limiter import RateLimiter
from .config import settings

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Ethernal MockUSDC Faucet",
    description="Automated USDC testnet token distribution",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
faucet_service = FaucetService()
rate_limiter = RateLimiter()


class FaucetRequest(BaseModel):
    address: str
    
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


@app.get("/")
async def root():
    """API root - basic info"""
    return {
        "name": "Ethernal MockUSDC Faucet API",
        "version": "1.0.0",
        "network": settings.NETWORK_NAME,
        "chain_id": settings.CHAIN_ID,
        "contract": settings.CONTRACT_ADDRESS,
        "endpoints": {
            "faucet": "/faucet",
            "balance": "/balance/{address}",
            "health": "/health",
            "stats": "/stats"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check RPC connection
        is_connected = faucet_service.w3.is_connected()
        
        # Check faucet balance
        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)
        
        return {
            "status": "healthy" if is_connected and faucet_balance > 0 else "degraded",
            "rpc_connected": is_connected,
            "faucet_balance": faucet_balance,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/faucet", response_model=FaucetResponse)
async def request_tokens(request: Request, faucet_req: FaucetRequest):
    """
    Request USDC tokens from faucet
    
    Rate limits:
    - Per IP: 1 request per hour
    - Per wallet: 1 request per 24 hours
    """
    client_ip = request.client.host
    address = faucet_req.address
    
    try:
        # Check rate limits
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
        
        # Check faucet balance
        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)
        if faucet_balance < settings.FAUCET_AMOUNT:
            logger.warning(f"Faucet running low: {faucet_balance} USDC")
            raise HTTPException(
                status_code=503,
                detail="Faucet temporarily unavailable - insufficient balance"
            )
        
        # Send tokens
        tx_hash = faucet_service.send_tokens(address, settings.FAUCET_AMOUNT)
        
        # Record in rate limiter
        rate_limiter.record_request(client_ip, address)
        
        # Get new balance
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/balance/{address}")
async def get_balance(address: str):
    """Get USDC balance for an address"""
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
    """Get faucet statistics"""
    try:
        stats = rate_limiter.get_stats()
        faucet_balance = faucet_service.get_balance(settings.FAUCET_ADDRESS)
        
        return {
            "faucet_balance": faucet_balance,
            "total_requests": stats["total_requests"],
            "unique_wallets": stats["unique_wallets"],
            "unique_ips": stats["unique_ips"],
            "amount_per_request": settings.FAUCET_AMOUNT,
            "rate_limits": {
                "per_ip_seconds": settings.RATE_LIMIT_IP_SECONDS,
                "per_wallet_seconds": settings.RATE_LIMIT_WALLET_SECONDS
            }
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )