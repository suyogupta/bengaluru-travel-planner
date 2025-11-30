"""
Payment Verification Service using Blockfrost
Verifies 2 ADA payments on Cardano Preprod
"""

import os
import ssl
import aiohttp
from typing import Optional
from dataclasses import dataclass

# SSL context for macOS compatibility
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Configuration
BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_API_KEY", "")
BLOCKFROST_BASE_URL = "https://cardano-preprod.blockfrost.io/api/v0"

# Your selling wallet address (where users send 2 ADA)
PAYMENT_WALLET_ADDRESS = "addr_test1qrdcyfry5wzlefwzaqlrj8x6epzce6rhunwdntpg39ds0tlal6a39g8umszr36axxktf787x90wfk3ahwgt2c4efpdjq5tuzn6"

# Required payment amount (2 ADA = 2,000,000 lovelace)
REQUIRED_PAYMENT_LOVELACE = 2_000_000


@dataclass
class PaymentVerification:
    """Result of payment verification"""
    is_valid: bool
    tx_hash: str
    amount_lovelace: int
    sender_address: Optional[str]
    error: Optional[str] = None


async def verify_payment(tx_hash: str) -> PaymentVerification:
    """
    Verify a payment transaction on Cardano Preprod.

    Checks:
    1. Transaction exists and is confirmed
    2. Payment was sent to our wallet
    3. Amount is at least 2 ADA (2,000,000 lovelace)

    Args:
        tx_hash: The Cardano transaction hash

    Returns:
        PaymentVerification with verification result
    """
    if not BLOCKFROST_API_KEY:
        return PaymentVerification(
            is_valid=False,
            tx_hash=tx_hash,
            amount_lovelace=0,
            sender_address=None,
            error="Blockfrost API key not configured"
        )

    headers = {"project_id": BLOCKFROST_API_KEY}
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Get transaction details
            tx_url = f"{BLOCKFROST_BASE_URL}/txs/{tx_hash}"
            async with session.get(tx_url, headers=headers) as resp:
                if resp.status == 404:
                    return PaymentVerification(
                        is_valid=False,
                        tx_hash=tx_hash,
                        amount_lovelace=0,
                        sender_address=None,
                        error="Transaction not found. Please wait for confirmation."
                    )
                if resp.status != 200:
                    return PaymentVerification(
                        is_valid=False,
                        tx_hash=tx_hash,
                        amount_lovelace=0,
                        sender_address=None,
                        error=f"Blockfrost error: {resp.status}"
                    )
                tx_data = await resp.json()

            # Get transaction UTXOs to check outputs
            utxo_url = f"{BLOCKFROST_BASE_URL}/txs/{tx_hash}/utxos"
            async with session.get(utxo_url, headers=headers) as resp:
                if resp.status != 200:
                    return PaymentVerification(
                        is_valid=False,
                        tx_hash=tx_hash,
                        amount_lovelace=0,
                        sender_address=None,
                        error="Failed to get transaction outputs"
                    )
                utxo_data = await resp.json()

            # Check if any output goes to our payment wallet
            payment_amount = 0
            sender_address = None

            # Get sender from inputs
            if utxo_data.get("inputs"):
                sender_address = utxo_data["inputs"][0].get("address")

            # Check outputs for payment to our wallet
            for output in utxo_data.get("outputs", []):
                if output.get("address") == PAYMENT_WALLET_ADDRESS:
                    # Sum up all lovelace sent to our address
                    for amount in output.get("amount", []):
                        if amount.get("unit") == "lovelace":
                            payment_amount += int(amount.get("quantity", 0))

            # Verify payment amount
            if payment_amount >= REQUIRED_PAYMENT_LOVELACE:
                return PaymentVerification(
                    is_valid=True,
                    tx_hash=tx_hash,
                    amount_lovelace=payment_amount,
                    sender_address=sender_address,
                    error=None
                )
            elif payment_amount > 0:
                return PaymentVerification(
                    is_valid=False,
                    tx_hash=tx_hash,
                    amount_lovelace=payment_amount,
                    sender_address=sender_address,
                    error=f"Insufficient payment. Received {payment_amount/1_000_000:.2f} ADA, required 2 ADA"
                )
            else:
                return PaymentVerification(
                    is_valid=False,
                    tx_hash=tx_hash,
                    amount_lovelace=0,
                    sender_address=sender_address,
                    error="No payment found to our wallet address"
                )

        except aiohttp.ClientError as e:
            return PaymentVerification(
                is_valid=False,
                tx_hash=tx_hash,
                amount_lovelace=0,
                sender_address=None,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            return PaymentVerification(
                is_valid=False,
                tx_hash=tx_hash,
                amount_lovelace=0,
                sender_address=None,
                error=f"Verification error: {str(e)}"
            )


# Store verified payments to prevent double-spending
verified_payments: set = set()


async def is_payment_already_used(tx_hash: str) -> bool:
    """Check if a payment has already been used for a job"""
    return tx_hash in verified_payments


def mark_payment_as_used(tx_hash: str):
    """Mark a payment as used"""
    verified_payments.add(tx_hash)


def get_payment_info() -> dict:
    """Get payment information for users"""
    return {
        "wallet_address": PAYMENT_WALLET_ADDRESS,
        "amount_ada": REQUIRED_PAYMENT_LOVELACE / 1_000_000,
        "amount_lovelace": REQUIRED_PAYMENT_LOVELACE,
        "network": "Preprod",
        "instructions": [
            "1. Open your Cardano wallet (Nami, Eternl, etc.)",
            "2. Send exactly 2 ADA to the wallet address above",
            "3. Wait for transaction confirmation (1-2 minutes)",
            "4. Copy your transaction hash",
            "5. Submit the transaction hash to verify payment"
        ]
    }