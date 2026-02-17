import time
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        # Storage: {ip: timestamp, wallet: timestamp}
        self.ip_requests = {}
        self.wallet_requests = {}
        
        # Stats
        self.total_requests = 0
        self.unique_ips = set()
        self.unique_wallets = set()
        
        # Rate limits (in seconds)
        self.ip_cooldown = 3600  # 1 hour
        self.wallet_cooldown = 86400  # 24 hours
    
    def check_ip(self, ip: str) -> tuple[bool, int]:
        if ip not in self.ip_requests:
            return True, 0
        
        last_request = self.ip_requests[ip]
        elapsed = time.time() - last_request
        
        if elapsed >= self.ip_cooldown:
            return True, 0
        
        wait_time = int(self.ip_cooldown - elapsed)
        logger.info(f"IP {ip} rate limited, wait {wait_time}s")
        return False, wait_time
    
    def check_wallet(self, wallet: str) -> tuple[bool, int]:
        wallet_lower = wallet.lower()
        
        if wallet_lower not in self.wallet_requests:
            return True, 0
        
        last_request = self.wallet_requests[wallet_lower]
        elapsed = time.time() - last_request
        
        if elapsed >= self.wallet_cooldown:
            return True, 0
        
        wait_time = int(self.wallet_cooldown - elapsed)
        logger.info(f"Wallet {wallet} rate limited, wait {wait_time}s")
        return False, wait_time
    
    def record_request(self, ip: str, wallet: str):
        now = time.time()
        
        self.ip_requests[ip] = now
        self.wallet_requests[wallet.lower()] = now
        self.total_requests += 1
        self.unique_ips.add(ip)
        self.unique_wallets.add(wallet.lower())
        
        logger.info(
            f"Recorded request - IP: {ip}, Wallet: {wallet}, "
            f"Total: {self.total_requests}"
        )
    
    def get_stats(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "unique_ips": len(self.unique_ips),
            "unique_wallets": len(self.unique_wallets),
            "active_ip_limits": len(self.ip_requests),
            "active_wallet_limits": len(self.wallet_requests)
        }
    
    def cleanup_old_entries(self):
        now = time.time()

        expired_ips = [
            ip for ip, ts in self.ip_requests.items()
            if now - ts > self.ip_cooldown
        ]
        for ip in expired_ips:
            del self.ip_requests[ip]
        
        # Cleanup wallets
        expired_wallets = [
            wallet for wallet, ts in self.wallet_requests.items()
            if now - ts > self.wallet_cooldown
        ]
        for wallet in expired_wallets:
            del self.wallet_requests[wallet]
        if expired_ips or expired_wallets:
            logger.info(
                f"Cleaned up {len(expired_ips)} IPs, "
                f"{len(expired_wallets)} wallets"
            )