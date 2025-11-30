"""
IPFS Storage Module
Stores images and diary data on IPFS via Pinata
"""

import os
import json
import base64
import hashlib
import ssl
import aiohttp
import certifi
from typing import Optional
from dataclasses import dataclass

# Pinata API configuration
# Get free API keys from https://app.pinata.cloud/
PINATA_API_KEY = os.getenv("PINATA_API_KEY", "")
PINATA_SECRET_KEY = os.getenv("PINATA_SECRET_KEY", "")
PINATA_JWT = os.getenv("PINATA_JWT", "")

PINATA_API_URL = "https://api.pinata.cloud"
IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"


@dataclass
class IPFSUploadResult:
    """Result of IPFS upload"""
    success: bool
    ipfs_hash: Optional[str]  # CID
    ipfs_url: Optional[str]
    size: int
    error: Optional[str]


def get_pinata_headers() -> dict:
    """Get headers for Pinata API"""
    if PINATA_JWT:
        return {
            "Authorization": f"Bearer {PINATA_JWT}",
            "Content-Type": "application/json"
        }
    else:
        return {
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_KEY,
            "Content-Type": "application/json"
        }


async def upload_image_to_ipfs(image_base64: str, filename: str = "travel_photo.jpg") -> IPFSUploadResult:
    """
    Upload a base64 encoded image to IPFS via Pinata.
    Returns the IPFS hash (CID) and gateway URL.
    """
    if not PINATA_JWT and not (PINATA_API_KEY and PINATA_SECRET_KEY):
        return IPFSUploadResult(
            success=False,
            ipfs_hash=None,
            ipfs_url=None,
            size=0,
            error="Pinata API credentials not configured. Set PINATA_JWT or PINATA_API_KEY/PINATA_SECRET_KEY"
        )

    try:
        # Decode base64 image
        image_data = base64.b64decode(image_base64)

        # Create form data for file upload
        headers = {}
        if PINATA_JWT:
            headers["Authorization"] = f"Bearer {PINATA_JWT}"
        else:
            headers["pinata_api_key"] = PINATA_API_KEY
            headers["pinata_secret_api_key"] = PINATA_SECRET_KEY

        # Create multipart form data
        form = aiohttp.FormData()
        form.add_field(
            'file',
            image_data,
            filename=filename,
            content_type='image/jpeg'
        )

        # Add pinata options (optional metadata)
        pinata_options = json.dumps({
            "cidVersion": 1
        })
        form.add_field('pinataOptions', pinata_options)

        pinata_metadata = json.dumps({
            "name": filename,
            "keyvalues": {
                "app": "bengaluru-travel-diary",
                "type": "travel-photo"
            }
        })
        form.add_field('pinataMetadata', pinata_metadata)

        # Create SSL context with certifi certificates (fixes macOS SSL issues)
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                f"{PINATA_API_URL}/pinning/pinFileToIPFS",
                headers=headers,
                data=form
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ipfs_hash = data.get("IpfsHash")
                    size = data.get("PinSize", len(image_data))

                    return IPFSUploadResult(
                        success=True,
                        ipfs_hash=ipfs_hash,
                        ipfs_url=f"{IPFS_GATEWAY}/{ipfs_hash}",
                        size=size,
                        error=None
                    )
                else:
                    error_text = await resp.text()
                    return IPFSUploadResult(
                        success=False,
                        ipfs_hash=None,
                        ipfs_url=None,
                        size=0,
                        error=f"Pinata API error: {resp.status} - {error_text}"
                    )

    except Exception as e:
        return IPFSUploadResult(
            success=False,
            ipfs_hash=None,
            ipfs_url=None,
            size=0,
            error=f"Error uploading to IPFS: {str(e)}"
        )


async def upload_json_to_ipfs(data: dict, name: str = "diary_entry.json") -> IPFSUploadResult:
    """
    Upload JSON data to IPFS via Pinata.
    Useful for storing complete diary entry metadata.
    """
    if not PINATA_JWT and not (PINATA_API_KEY and PINATA_SECRET_KEY):
        return IPFSUploadResult(
            success=False,
            ipfs_hash=None,
            ipfs_url=None,
            size=0,
            error="Pinata API credentials not configured"
        )

    try:
        headers = get_pinata_headers()

        payload = {
            "pinataContent": data,
            "pinataMetadata": {
                "name": name,
                "keyvalues": {
                    "app": "bengaluru-travel-diary",
                    "type": "diary-entry"
                }
            },
            "pinataOptions": {
                "cidVersion": 1
            }
        }

        # Create SSL context with certifi certificates (fixes macOS SSL issues)
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                f"{PINATA_API_URL}/pinning/pinJSONToIPFS",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    ipfs_hash = result.get("IpfsHash")
                    size = result.get("PinSize", 0)

                    return IPFSUploadResult(
                        success=True,
                        ipfs_hash=ipfs_hash,
                        ipfs_url=f"{IPFS_GATEWAY}/{ipfs_hash}",
                        size=size,
                        error=None
                    )
                else:
                    error_text = await resp.text()
                    return IPFSUploadResult(
                        success=False,
                        ipfs_hash=None,
                        ipfs_url=None,
                        size=0,
                        error=f"Pinata API error: {resp.status} - {error_text}"
                    )

    except Exception as e:
        return IPFSUploadResult(
            success=False,
            ipfs_hash=None,
            ipfs_url=None,
            size=0,
            error=f"Error uploading JSON to IPFS: {str(e)}"
        )


def generate_content_hash(content: str) -> str:
    """Generate SHA256 hash of content for verification"""
    return hashlib.sha256(content.encode()).hexdigest()


def is_ipfs_configured() -> bool:
    """Check if IPFS (Pinata) is configured"""
    return bool(PINATA_JWT or (PINATA_API_KEY and PINATA_SECRET_KEY))


def get_ipfs_url(ipfs_hash: str) -> str:
    """Get gateway URL for an IPFS hash"""
    return f"{IPFS_GATEWAY}/{ipfs_hash}"


# Alternative gateways if Pinata gateway is slow
ALTERNATIVE_GATEWAYS = [
    "https://ipfs.io/ipfs",
    "https://cloudflare-ipfs.com/ipfs",
    "https://dweb.link/ipfs"
]


def get_alternative_urls(ipfs_hash: str) -> list[str]:
    """Get alternative gateway URLs for an IPFS hash"""
    return [f"{gateway}/{ipfs_hash}" for gateway in ALTERNATIVE_GATEWAYS]