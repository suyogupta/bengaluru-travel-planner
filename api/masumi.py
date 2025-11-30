"""
Masumi Payment Service Integration
Handles escrow-based payments via Masumi protocol
"""

import os
import ssl
import uuid
import hashlib
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

# Masumi Payment Service configuration
MASUMI_API_URL = os.getenv("MASUMI_API_URL", "http://localhost:3001")
MASUMI_API_KEY = os.getenv("MASUMI_API_KEY", "test-admin-api-key")

# Your registered agent ID
AGENT_IDENTIFIER = os.getenv("MASUMI_AGENT_ID", "")

# SSL context for HTTPS calls
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


@dataclass
class MasumiPaymentRequest:
    """Payment request created via Masumi"""
    payment_id: str
    blockchain_identifier: str
    amount_lovelace: int
    status: str
    seller_address: str = ""
    error: Optional[str] = None


@dataclass
class MasumiPaymentStatus:
    """Status of a Masumi payment"""
    payment_id: str
    status: str  # WaitingForExternalAction, PaymentConfirmed, etc.
    amount_lovelace: int
    is_paid: bool
    on_chain_state: Optional[str] = None
    error: Optional[str] = None


def generate_input_hash(data: dict) -> str:
    """Generate SHA256 hash of input data in hex format"""
    import json
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


def generate_purchaser_id() -> str:
    """Generate a unique purchaser identifier (14-26 hex chars)"""
    return uuid.uuid4().hex[:20]


async def create_masumi_payment(input_data: dict, amount_lovelace: int = 2_000_000) -> MasumiPaymentRequest:
    """
    Create a payment request via Masumi escrow.

    This creates an escrow payment where the user pays to a smart contract.
    The payment is held until the agent completes work and we call complete_payment.
    """
    headers = {
        "Content-Type": "application/json",
        "token": MASUMI_API_KEY
    }

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Generate required identifiers
            input_hash = generate_input_hash(input_data)
            purchaser_id = generate_purchaser_id()

            # Calculate time windows
            now = datetime.utcnow()
            pay_by_time = (now + timedelta(hours=12)).isoformat() + "Z"
            submit_result_time = (now + timedelta(hours=24)).isoformat() + "Z"

            # Create payment request via Masumi API
            url = f"{MASUMI_API_URL}/api/v1/payment"
            payload = {
                "agentIdentifier": AGENT_IDENTIFIER,
                "network": "Preprod",
                "inputHash": input_hash,
                "identifierFromPurchaser": purchaser_id,
                "payByTime": pay_by_time,
                "submitResultTime": submit_result_time
            }

            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200 and resp.status != 201:
                    error_text = await resp.text()
                    return MasumiPaymentRequest(
                        payment_id="",
                        blockchain_identifier="",
                        amount_lovelace=amount_lovelace,
                        status="error",
                        error=f"Masumi API error: {resp.status} - {error_text}"
                    )

                data = await resp.json()
                payment_data = data.get("data", data)

                return MasumiPaymentRequest(
                    payment_id=payment_data.get("id", ""),
                    blockchain_identifier=payment_data.get("blockchainIdentifier", ""),
                    amount_lovelace=amount_lovelace,
                    status="created",
                    seller_address=payment_data.get("SmartContractWallet", {}).get("walletAddress", ""),
                    error=None
                )

        except aiohttp.ClientError as e:
            return MasumiPaymentRequest(
                payment_id="",
                blockchain_identifier="",
                amount_lovelace=amount_lovelace,
                status="error",
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            return MasumiPaymentRequest(
                payment_id="",
                blockchain_identifier="",
                amount_lovelace=amount_lovelace,
                status="error",
                error=f"Error: {str(e)}"
            )


async def check_masumi_payment(payment_id: str) -> MasumiPaymentStatus:
    """
    Check the status of a Masumi payment.
    """
    headers = {
        "Content-Type": "application/json",
        "token": MASUMI_API_KEY
    }

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # Query payments with network param - the API uses GET with query params
            url = f"{MASUMI_API_URL}/api/v1/payment"
            params = {"network": "Preprod", "limit": 100}

            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return MasumiPaymentStatus(
                        payment_id=payment_id,
                        status="error",
                        amount_lovelace=0,
                        is_paid=False,
                        error=f"Masumi API error: {resp.status} - {error_text}"
                    )

                data = await resp.json()
                payments = data.get("data", {}).get("Payments", [])

                # Find the specific payment by ID
                payment_data = None
                for p in payments:
                    if p.get("id") == payment_id:
                        payment_data = p
                        break

                if not payment_data:
                    return MasumiPaymentStatus(
                        payment_id=payment_id,
                        status="not_found",
                        amount_lovelace=0,
                        is_paid=False,
                        error="Payment not found"
                    )

                # Get the next action status
                next_action = payment_data.get("NextAction", {})
                requested_action = next_action.get("requestedAction", "unknown")
                on_chain_state = payment_data.get("onChainState")

                # Determine if payment is confirmed based on on-chain state
                is_paid = on_chain_state in ["FundsLocked", "ResultSubmitted", "Completed"]

                # Get requested amount
                requested_funds = payment_data.get("RequestedFunds", [])
                amount = 0
                for fund in requested_funds:
                    if fund.get("unit") == "" or fund.get("unit") == "lovelace":
                        amount = int(fund.get("amount", 0))
                        break

                return MasumiPaymentStatus(
                    payment_id=payment_id,
                    status=requested_action,
                    amount_lovelace=amount,
                    is_paid=is_paid,
                    on_chain_state=on_chain_state,
                    error=None
                )

        except Exception as e:
            return MasumiPaymentStatus(
                payment_id=payment_id,
                status="error",
                amount_lovelace=0,
                is_paid=False,
                error=f"Error: {str(e)}"
            )


async def complete_masumi_payment(payment_id: str, result_hash: str = "") -> bool:
    """
    Mark a Masumi payment as complete.

    This signals that the agent has completed work and releases the escrow.
    """
    headers = {
        "Content-Type": "application/json",
        "token": MASUMI_API_KEY
    }

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            url = f"{MASUMI_API_URL}/api/v1/payment/{payment_id}/complete"
            payload = {
                "resultHash": result_hash or "itinerary-generated"
            }

            async with session.post(url, json=payload, headers=headers) as resp:
                return resp.status == 200 or resp.status == 201

        except Exception:
            return False


def get_masumi_info() -> dict:
    """Get Masumi integration info"""
    return {
        "enabled": bool(AGENT_IDENTIFIER),
        "agent_identifier": AGENT_IDENTIFIER,
        "api_url": MASUMI_API_URL,
        "network": "Preprod",
        "description": "Masumi escrow-based payments with buyer protection"
    }