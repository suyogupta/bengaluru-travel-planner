"""
Cardano Metadata Module
Stores diary entry metadata on Cardano blockchain via Blockfrost
"""

import os
import json
import hashlib
import aiohttp
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

# Blockfrost configuration
BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_API_KEY", "")
BLOCKFROST_NETWORK = os.getenv("BLOCKFROST_NETWORK", "preprod")

# API URLs by network
BLOCKFROST_URLS = {
    "preprod": "https://cardano-preprod.blockfrost.io/api/v0",
    "preview": "https://cardano-preview.blockfrost.io/api/v0",
    "mainnet": "https://cardano-mainnet.blockfrost.io/api/v0"
}

# Cardanoscan URLs for viewing transactions
CARDANOSCAN_URLS = {
    "preprod": "https://preprod.cardanoscan.io",
    "preview": "https://preview.cardanoscan.io",
    "mainnet": "https://cardanoscan.io"
}

# Metadata label for our diary entries (pick a unique number)
# Using 1987 as our app-specific label
DIARY_METADATA_LABEL = 1987


@dataclass
class DiaryMetadata:
    """Metadata structure for diary entry stored on-chain"""
    app: str  # "bengaluru-travel-diary"
    version: str  # "1.0"
    entry_id: str
    title: str
    location: str
    content_hash: str  # SHA256 of content
    image_ipfs: Optional[str]  # IPFS CID
    score: float
    rewarded: bool
    wallet: str
    timestamp: str


@dataclass
class OnChainResult:
    """Result of on-chain operation"""
    success: bool
    tx_hash: Optional[str]
    cardanoscan_url: Optional[str]
    metadata: Optional[dict]
    error: Optional[str]


def get_blockfrost_headers() -> dict:
    """Get headers for Blockfrost API"""
    return {
        "project_id": BLOCKFROST_API_KEY,
        "Content-Type": "application/json"
    }


def get_blockfrost_url() -> str:
    """Get Blockfrost API URL for current network"""
    return BLOCKFROST_URLS.get(BLOCKFROST_NETWORK, BLOCKFROST_URLS["preprod"])


def get_cardanoscan_url() -> str:
    """Get Cardanoscan URL for current network"""
    return CARDANOSCAN_URLS.get(BLOCKFROST_NETWORK, CARDANOSCAN_URLS["preprod"])


def create_diary_metadata(
    entry_id: str,
    title: str,
    location: str,
    content: str,
    image_ipfs_hash: Optional[str],
    quality_score: float,
    is_rewarded: bool,
    wallet_address: str
) -> dict:
    """
    Create metadata structure for diary entry.
    Follows Cardano metadata standards (max 64 bytes per string field).
    """
    # Hash the content (full content can't fit in metadata)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Truncate fields to fit Cardano metadata limits (64 bytes)
    def truncate(s: str, max_len: int = 60) -> str:
        return s[:max_len] if len(s) > max_len else s

    metadata = {
        "app": "blr-travel-diary",
        "v": "1.0",
        "id": truncate(entry_id, 20),
        "title": truncate(title, 60),
        "loc": truncate(location, 40),
        "hash": content_hash[:32],  # First 32 chars of SHA256
        "score": round(quality_score, 1),
        "reward": 1 if is_rewarded else 0,
        "ts": datetime.utcnow().strftime("%Y%m%d%H%M%S")
    }

    # Add IPFS hash if available
    if image_ipfs_hash:
        metadata["ipfs"] = truncate(image_ipfs_hash, 60)

    # Add truncated wallet (for verification)
    metadata["wallet"] = truncate(wallet_address, 40)

    return metadata


async def submit_metadata_tx(
    metadata: dict,
    sender_address: str,
    amount_lovelace: int = 1_500_000  # Min UTxO + fees
) -> OnChainResult:
    """
    Submit a transaction with metadata to the blockchain.

    Note: This is a simplified version. In production, you would:
    1. Use cardano-cli or a wallet SDK to build and sign transactions
    2. Have proper key management
    3. Handle UTxO selection

    For hackathon, we'll use Blockfrost's tx submit endpoint with a pre-signed tx,
    or simulate the metadata storage.
    """

    # For hackathon demo, we'll create a "virtual" on-chain record
    # In production, you'd build and submit an actual transaction

    # Generate a mock tx hash based on metadata
    metadata_str = json.dumps(metadata, sort_keys=True)
    mock_tx_hash = hashlib.sha256(metadata_str.encode()).hexdigest()

    # Store the metadata in our records (simulated chain storage)
    # In production, this would be an actual blockchain transaction

    return OnChainResult(
        success=True,
        tx_hash=mock_tx_hash,
        cardanoscan_url=f"{get_cardanoscan_url()}/transaction/{mock_tx_hash}",
        metadata=metadata,
        error=None
    )


async def get_tx_metadata(tx_hash: str) -> Optional[dict]:
    """
    Fetch metadata from a transaction on Cardano.
    """
    if not BLOCKFROST_API_KEY:
        return None

    url = f"{get_blockfrost_url()}/txs/{tx_hash}/metadata"
    headers = get_blockfrost_headers()

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Find our diary metadata by label
                    for item in data:
                        if item.get("label") == str(DIARY_METADATA_LABEL):
                            return item.get("json_metadata")
                    return None
                else:
                    return None
        except Exception:
            return None


async def verify_diary_on_chain(tx_hash: str, content_hash: str) -> bool:
    """
    Verify that a diary entry exists on-chain with matching content hash.
    """
    metadata = await get_tx_metadata(tx_hash)
    if not metadata:
        return False

    stored_hash = metadata.get("hash", "")
    return content_hash.startswith(stored_hash)


def is_cardano_configured() -> bool:
    """Check if Cardano/Blockfrost is configured"""
    return bool(BLOCKFROST_API_KEY)


def get_explorer_url(tx_hash: str) -> str:
    """Get block explorer URL for a transaction"""
    return f"{get_cardanoscan_url()}/transaction/{tx_hash}"


# Metadata format documentation
METADATA_FORMAT = """
Cardano Metadata Format for Travel Diary (Label: 1987)

{
    "app": "blr-travel-diary",   // Application identifier
    "v": "1.0",                   // Version
    "id": "abc123...",            // Entry ID (20 chars)
    "title": "Amazing Day...",    // Title (60 chars max)
    "loc": "Cubbon Park",         // Location (40 chars max)
    "hash": "sha256...",          // Content hash (32 chars)
    "ipfs": "Qm...",              // IPFS CID for image (optional)
    "score": 8.5,                 // AI quality score
    "reward": 1,                  // 1=rewarded, 0=not rewarded
    "wallet": "addr_test1...",    // Wallet address (40 chars)
    "ts": "20241130123456"        // Timestamp (YYYYMMDDHHmmss)
}

Total size: ~400 bytes (well under 16KB limit)
"""