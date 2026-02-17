import json
import os
from pathlib import Path
from web3 import Web3
from web3.exceptions import ContractLogicError
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class FaucetService:
    def __init__(self):
        self.rpc_url = os.getenv("RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")

        self.private_key = os.getenv("FAUCET_PRIVATE_KEY")
        if not self.private_key:
            raise ValueError("FAUCET_PRIVATE_KEY not found in environment")
        
        self.account = self.w3.eth.account.from_key(self.private_key)
        logger.info(f"Faucet wallet: {self.account.address}")

        self.contract_address = os.getenv("CONTRACT_ADDRESS")
        if not self.contract_address:
            deployed_path = Path(__file__).parent.parent / "out" / "deployed_address.json"
            if deployed_path.exists():
                with open(deployed_path) as f:
                    data = json.load(f)
                    self.contract_address = data["contract_address"]
            else:
                raise ValueError("CONTRACT_ADDRESS not configured")

        abi_path = Path(__file__).parent.parent / "out" / "MockUSDC.json"
        if not abi_path.exists():
            raise FileNotFoundError(f"ABI not found at {abi_path}")
        
        with open(abi_path) as f:
            self.abi = json.load(f)
        
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=self.abi
        )
        
        logger.info(f"Contract loaded: {self.contract_address}")
    
    def get_balance(self, address: str) -> float:
        try:
            balance = self.contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()
            decimals = self.contract.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            logger.error(f"Balance check failed for {address}: {e}")
            raise
    
    def send_tokens(self, to_address: str, amount: float) -> str:
        try:
            to_address = Web3.to_checksum_address(to_address)
            decimals = self.contract.functions.decimals().call()
            amount_wei = int(amount * (10 ** decimals))

            max_faucet = self.contract.functions.getFaucetMax().call()
            if amount_wei > max_faucet:
                logger.warning(
                    f"Amount {amount_wei} exceeds max {max_faucet}, adjusting"
                )
                amount_wei = max_faucet

            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = self.w3.to_wei(0.1, 'gwei')
            max_fee_per_gas = base_fee * 2 + max_priority_fee
            
            tx = self.contract.functions.faucet(
                to_address,
                amount_wei
            ).build_transaction({
                'chainId': int(os.getenv("CHAIN_ID", "421614")),
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            
            logger.info(f"Sent {amount} USDC to {to_address}, tx: {tx_hash.hex()}")

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt.status != 1:
                raise Exception("Transaction failed")
            
            return tx_hash.hex()
            
        except ContractLogicError as e:
            logger.error(f"Contract error sending to {to_address}: {e}")
            raise Exception(f"Contract error: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending to {to_address}: {e}")
            raise