import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Network
    NETWORK_NAME: str = os.getenv("NETWORK_NAME", "Arbitrum Sepolia")
    CHAIN_ID: int = int(os.getenv("CHAIN_ID", "421614"))
    RPC_URL: str = os.getenv("RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc")

    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")
    FAUCET_ADDRESS: str = os.getenv("FAUCET_ADDRESS", "")
 
    FAUCET_AMOUNT: float = float(os.getenv("FAUCET_AMOUNT", "100"))

    RATE_LIMIT_IP_SECONDS: int = int(os.getenv("RATE_LIMIT_IP_SECONDS", "3600"))
    RATE_LIMIT_WALLET_SECONDS: int = int(os.getenv("RATE_LIMIT_WALLET_SECONDS", "86400"))

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # Production domains - uncomment and update
        # "https://your-app.vercel.app",
        # "https://ethernal.finance",
    ]
    
    # API - Render uses PORT env var
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))  # Render compatibility
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
