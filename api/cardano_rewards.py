"""
Cardano Rewards Module
Sends real ADA rewards for quality diary entries using PyCardano
"""

import os
import hashlib
from typing import Optional, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

from pycardano import (
    BlockFrostChainContext,
    TransactionBuilder,
    TransactionOutput,
    Address,
    PaymentSigningKey,
    PaymentVerificationKey,
    StakeSigningKey,
    StakeVerificationKey,
)
from mnemonic import Mnemonic

# Configuration
BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_API_KEY", "")
BLOCKFROST_NETWORK = os.getenv("BLOCKFROST_NETWORK", "preprod")
ENCRYPTION_KEY = os.getenv("MASUMI_ENCRYPTION_KEY", "TravelPlannerMasumi2024SecureKey")

# Database connection for getting wallet
DATABASE_URL = os.getenv("MASUMI_DATABASE_URL", "postgresql://suyoggupta@localhost:5432/masumi_payment")

# Network configuration
NETWORK_IDS = {
    "preprod": 0,
    "preview": 0,
    "mainnet": 1
}


@dataclass
class RewardResult:
    """Result of sending a reward"""
    success: bool
    tx_hash: Optional[str]
    explorer_url: Optional[str]
    error: Optional[str]


def decrypt_mnemonic(encrypted_hex: str, password: str) -> str:
    """
    Decrypt mnemonic using the same algorithm as Masumi payment service.
    Uses AES-256-CBC with scrypt key derivation.
    """
    # Parse the encrypted data
    encrypted_bytes = bytes.fromhex(encrypted_hex)
    salt = encrypted_bytes[:16]
    iv = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]

    # Derive key using scrypt (same params as Node.js crypto.scryptSync)
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=16384,  # Default Node.js scrypt N
        r=8,      # Default Node.js scrypt r
        p=1,      # Default Node.js scrypt p
        backend=default_backend()
    )
    key = kdf.derive(password.encode())

    # Decrypt using AES-256-CBC
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    padding_length = padded_plaintext[-1]
    plaintext = padded_plaintext[:-padding_length]

    return plaintext.decode('utf-8')


def get_reward_wallet_mnemonic() -> Optional[str]:
    """
    Get the selling wallet mnemonic from Masumi database.
    """
    try:
        import psycopg2

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Get the selling wallet's encrypted mnemonic
        cursor.execute("""
            SELECT s."encryptedMnemonic"
            FROM "HotWallet" h
            JOIN "WalletSecret" s ON h."secretId" = s.id
            WHERE h.type = 'Selling'
            LIMIT 1
        """)

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            encrypted_mnemonic = result[0]
            return decrypt_mnemonic(encrypted_mnemonic, ENCRYPTION_KEY)

        return None

    except Exception as e:
        print(f"[REWARD] Error getting wallet mnemonic: {e}")
        return None


def get_reward_wallet_address() -> Optional[str]:
    """
    Get the selling wallet address directly from Masumi database.
    """
    try:
        import psycopg2

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Get the selling wallet address
        cursor.execute("""
            SELECT h."walletAddress"
            FROM "HotWallet" h
            WHERE h.type = 'Selling'
            LIMIT 1
        """)

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return result[0]

        return None

    except Exception as e:
        print(f"[REWARD] Error getting wallet address: {e}")
        return None


def mnemonic_to_keys(mnemonic: str) -> Tuple[PaymentSigningKey, PaymentVerificationKey, Address]:
    """
    Derive payment keys and address from mnemonic.
    Uses BIP32/CIP-1852 derivation path.
    """
    from pycardano import HDWallet

    # Create HD wallet from mnemonic
    hdwallet = HDWallet.from_mnemonic(mnemonic)

    # Derive payment key at path m/1852'/1815'/0'/0/0
    child = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")

    # Get the raw key bytes and create signing key (Ed25519 keys are 32 bytes)
    payment_signing_key = PaymentSigningKey.from_primitive(child.xprivate_key[:32])
    payment_verification_key = PaymentVerificationKey.from_signing_key(payment_signing_key)

    # Also derive stake key at m/1852'/1815'/0'/2/0 for full address
    stake_child = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
    stake_skey = StakeSigningKey.from_primitive(stake_child.xprivate_key[:32])
    stake_vkey = StakeVerificationKey.from_signing_key(stake_skey)

    # Create base address (with stake key)
    from pycardano import Network
    network = Network.TESTNET  # Preprod is testnet
    address = Address(payment_verification_key.hash(), stake_vkey.hash(), network)

    return payment_signing_key, payment_verification_key, address


async def send_ada_reward(
    recipient_address: str,
    amount_lovelace: int = 1_000_000  # 1 ADA
) -> RewardResult:
    """
    Send ADA reward using the Node.js MeshSDK script.
    Uses async subprocess to avoid blocking and includes retry logic.

    Note: We use Node.js because MeshSDK has more reliable HD wallet derivation
    that matches the Masumi payment service wallet generation.
    """
    import asyncio
    import json
    import os

    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            # Get the wallet mnemonic
            mnemonic = get_reward_wallet_mnemonic()
            if not mnemonic:
                return RewardResult(
                    success=False,
                    tx_hash=None,
                    explorer_url=None,
                    error="Could not get reward wallet mnemonic"
                )

            print(f"[REWARD] Attempt {attempt + 1}/{MAX_RETRIES}: Sending {amount_lovelace} lovelace to {recipient_address[:30]}...")

            # Path to the Node.js script (relative to project root)
            script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "send_ada_reward.js")
            script_path = os.path.abspath(script_path)

            # Run the Node.js script using async subprocess with arguments
            process = await asyncio.create_subprocess_exec(
                "node", script_path,
                recipient_address,
                str(amount_lovelace),
                mnemonic,
                BLOCKFROST_API_KEY,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60.0  # 60 second timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                raise Exception("Transaction timed out after 60 seconds")

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            # Log debug output
            if stderr_str:
                for line in stderr_str.split('\n'):
                    if line.startswith('Debug:'):
                        print(f"[REWARD] {line}")

            # Parse result from stdout (last line should be JSON)
            result_lines = [l for l in stdout_str.split('\n') if l.strip()]
            if not result_lines:
                raise Exception(f"No output from script. stderr: {stderr_str}")

            result_json = result_lines[-1]
            result = json.loads(result_json)

            if result.get("success"):
                tx_hash = result.get("tx_hash")
                explorer_url = result.get("explorer_url")
                print(f"[REWARD] Transaction submitted: {tx_hash}")
                print(f"[REWARD] Explorer: {explorer_url}")

                return RewardResult(
                    success=True,
                    tx_hash=tx_hash,
                    explorer_url=explorer_url,
                    error=None
                )
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            error_msg = str(e)
            print(f"[REWARD] Attempt {attempt + 1} failed: {error_msg}")

            # Check if it's a retryable error (network issues)
            if attempt < MAX_RETRIES - 1 and any(x in error_msg.lower() for x in ['timeout', 'connection', 'network', 'reset', 'refused', 'econnreset']):
                print(f"[REWARD] Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
                continue

            # Non-retryable error or last attempt
            return RewardResult(
                success=False,
                tx_hash=None,
                explorer_url=None,
                error=error_msg
            )

    return RewardResult(
        success=False,
        tx_hash=None,
        explorer_url=None,
        error="Max retries exceeded"
    )


def is_reward_system_configured() -> bool:
    """Check if the reward system is properly configured"""
    return bool(BLOCKFROST_API_KEY)


def get_reward_wallet_info() -> dict:
    """Get info about the reward wallet"""
    try:
        mnemonic = get_reward_wallet_mnemonic()
        if not mnemonic:
            return {"configured": False, "error": "Could not get wallet"}

        payment_skey, payment_vkey, address = mnemonic_to_keys(mnemonic)

        return {
            "configured": True,
            "address": str(address),
            "network": BLOCKFROST_NETWORK
        }
    except Exception as e:
        return {"configured": False, "error": str(e)}