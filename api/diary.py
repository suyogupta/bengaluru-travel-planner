"""
Travel Diary Feature
Allows users to post travel diary entries with photos
Quality entries are rewarded with 1 ADA
Limited to 1 entry per wallet address per day

Storage:
- Images stored on IPFS (via Pinata)
- Metadata hash stored on Cardano blockchain
- Local JSON file as index/cache
"""

import os
import json
import base64
import hashlib
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import google.generativeai as genai

# Import IPFS and Cardano modules
from api.ipfs_storage import (
    upload_image_to_ipfs,
    upload_json_to_ipfs,
    is_ipfs_configured,
    get_ipfs_url,
    generate_content_hash
)
from api.cardano_metadata import (
    create_diary_metadata,
    submit_metadata_tx,
    is_cardano_configured,
    get_explorer_url
)
from api.cardano_rewards import (
    send_ada_reward as send_real_ada_reward,
    is_reward_system_configured
)

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Storage path for diary entries
DIARY_STORAGE_PATH = Path(__file__).parent.parent / "data" / "diary_entries.json"
DIARY_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Local image storage path
IMAGES_STORAGE_PATH = Path(__file__).parent.parent / "data" / "images"
IMAGES_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Reward amount in lovelace (1 ADA = 1,000,000 lovelace)
REWARD_AMOUNT_LOVELACE = 1_000_000


@dataclass
class DiaryEntry:
    """A travel diary entry"""
    id: str
    wallet_address: str
    title: str
    content: str
    location: str
    image_base64: Optional[str]  # Base64 encoded image (truncated for local storage)
    created_at: str
    quality_score: float  # 0-10 score from AI
    is_rewarded: bool
    reward_tx_hash: Optional[str]
    verification_feedback: str
    # New fields for decentralized storage
    content_hash: Optional[str]  # SHA256 hash of content
    image_ipfs_hash: Optional[str]  # IPFS CID for image
    image_ipfs_url: Optional[str]  # Gateway URL for image
    metadata_ipfs_hash: Optional[str]  # IPFS CID for full metadata
    chain_tx_hash: Optional[str]  # Cardano tx hash with metadata
    cardanoscan_url: Optional[str]  # Link to view on explorer


@dataclass
class DiarySubmissionResult:
    """Result of diary submission"""
    success: bool
    entry_id: Optional[str]
    quality_score: float
    is_eligible_for_reward: bool
    reward_sent: bool
    reward_tx_hash: Optional[str]
    feedback: str
    error: Optional[str]
    # New fields for storage info
    image_ipfs_url: Optional[str] = None
    metadata_ipfs_url: Optional[str] = None
    chain_tx_hash: Optional[str] = None
    cardanoscan_url: Optional[str] = None


def load_diary_entries() -> list[dict]:
    """Load all diary entries from storage"""
    if not DIARY_STORAGE_PATH.exists():
        return []
    try:
        with open(DIARY_STORAGE_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_diary_entries(entries: list[dict]):
    """Save diary entries to storage"""
    with open(DIARY_STORAGE_PATH, 'w') as f:
        json.dump(entries, f, indent=2)


def get_entries_by_wallet(wallet_address: str) -> list[dict]:
    """Get all entries by a specific wallet"""
    entries = load_diary_entries()
    return [e for e in entries if e.get('wallet_address') == wallet_address]


def has_submitted_today(wallet_address: str) -> bool:
    """Check if wallet has reached daily submission limit (10 for testing)"""
    today = date.today().isoformat()
    entries = get_entries_by_wallet(wallet_address)

    # Count entries from today
    today_count = 0
    for entry in entries:
        entry_date = entry.get('created_at', '')[:10]  # Get YYYY-MM-DD
        if entry_date == today:
            today_count += 1

    # Allow up to 10 entries per day for testing
    return today_count >= 10


def generate_entry_id(wallet_address: str, content: str) -> str:
    """Generate unique entry ID"""
    data = f"{wallet_address}:{content}:{datetime.utcnow().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def save_image_locally(entry_id: str, image_base64: str) -> Optional[str]:
    """Save image locally and return the local URL path"""
    try:
        image_data = base64.b64decode(image_base64)
        image_path = IMAGES_STORAGE_PATH / f"{entry_id}.jpg"
        with open(image_path, 'wb') as f:
            f.write(image_data)
        # Return the API path for serving the image
        return f"/diary/image/{entry_id}"
    except Exception as e:
        print(f"[LOCAL] Error saving image locally: {e}")
        return None


def get_local_image_path(entry_id: str) -> Optional[Path]:
    """Get the path to a locally stored image"""
    image_path = IMAGES_STORAGE_PATH / f"{entry_id}.jpg"
    if image_path.exists():
        return image_path
    return None


async def verify_diary_quality(
    title: str,
    content: str,
    location: str,
    image_base64: Optional[str] = None
) -> tuple[float, str]:
    """
    Use Gemini AI to verify diary quality and relevance.
    Returns (score 0-10, feedback)
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')

        prompt = f"""You are a travel diary quality evaluator. Analyze this travel diary entry and provide:
1. A quality score from 0-10 (be strict but fair)
2. Brief feedback explaining the score

Criteria for scoring:
- Authenticity: Does it seem like a genuine travel experience? (2 points)
- Detail: Are there specific details about the place, food, or experience? (2 points)
- Engagement: Is it interesting and well-written? (2 points)
- Relevance: Is it about Bengaluru/Karnataka travel? (2 points)
- Photo relevance: Does the description match a travel photo? (2 points)

IMPORTANT:
- Score 7+ means the entry deserves a reward
- Be strict about spam, low-effort, or fake entries (score < 5)
- Generic or copied content should score low

Travel Diary Entry:
Title: {title}
Location: {location}
Content: {content}

{"[Photo attached - evaluate if description matches a travel photo context]" if image_base64 else "[No photo attached - deduct 2 points]"}

Respond in this exact JSON format:
{{"score": <number 0-10>, "feedback": "<brief feedback>"}}
"""

        # If image is provided, include it in the analysis
        if image_base64:
            try:
                # Decode base64 image for Gemini
                image_data = base64.b64decode(image_base64)

                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": image_data}
                ])
            except Exception:
                # If image processing fails, analyze text only
                response = model.generate_content(prompt)
        else:
            response = model.generate_content(prompt)

        # Parse response
        response_text = response.text.strip()

        # Try to extract JSON from response
        if '{' in response_text and '}' in response_text:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)

            score = float(result.get('score', 5))
            feedback = result.get('feedback', 'Entry evaluated.')

            # Clamp score to 0-10
            score = max(0, min(10, score))

            return score, feedback
        else:
            return 5.0, "Could not fully evaluate entry. Default score assigned."

    except Exception as e:
        print(f"Error verifying diary: {e}")
        return 5.0, f"Evaluation error: {str(e)}"


async def send_ada_reward(recipient_address: str, amount_lovelace: int = REWARD_AMOUNT_LOVELACE) -> tuple[bool, Optional[str]]:
    """
    Send ADA reward to the diary author.
    Returns (success, tx_hash)

    Uses PyCardano with the Masumi selling wallet to send real ADA rewards.
    """
    try:
        # Check if reward system is configured
        if not is_reward_system_configured():
            print("[REWARD] Reward system not configured (missing Blockfrost API key)")
            return False, None

        print(f"[REWARD] Sending {amount_lovelace} lovelace to {recipient_address}")

        # Use the real ADA sending function
        result = await send_real_ada_reward(recipient_address, amount_lovelace)

        if result.success:
            print(f"[REWARD] Transaction submitted: {result.tx_hash}")
            print(f"[REWARD] Explorer: {result.explorer_url}")
            return True, result.tx_hash
        else:
            print(f"[REWARD] Failed to send reward: {result.error}")
            return False, None

    except Exception as e:
        print(f"[REWARD] Error sending reward: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def submit_diary_entry(
    wallet_address: str,
    title: str,
    content: str,
    location: str,
    image_base64: Optional[str] = None
) -> DiarySubmissionResult:
    """
    Submit a new diary entry.
    - Validates wallet hasn't submitted today
    - Uploads image to IPFS (if provided and configured)
    - Verifies quality with AI
    - Stores metadata on Cardano blockchain
    - Rewards if quality score >= 7
    """

    # Validate wallet address format (basic check)
    if not wallet_address or not wallet_address.startswith('addr'):
        return DiarySubmissionResult(
            success=False,
            entry_id=None,
            quality_score=0,
            is_eligible_for_reward=False,
            reward_sent=False,
            reward_tx_hash=None,
            feedback="Invalid wallet address format.",
            error="Wallet address must start with 'addr'"
        )

    # Check daily limit
    if has_submitted_today(wallet_address):
        return DiarySubmissionResult(
            success=False,
            entry_id=None,
            quality_score=0,
            is_eligible_for_reward=False,
            reward_sent=False,
            reward_tx_hash=None,
            feedback="You have already submitted a diary entry today. Try again tomorrow!",
            error="Daily limit reached"
        )

    # Validate content length
    if len(content) < 50:
        return DiarySubmissionResult(
            success=False,
            entry_id=None,
            quality_score=0,
            is_eligible_for_reward=False,
            reward_sent=False,
            reward_tx_hash=None,
            feedback="Diary content is too short. Please write at least 50 characters.",
            error="Content too short"
        )

    if len(content) > 5000:
        return DiarySubmissionResult(
            success=False,
            entry_id=None,
            quality_score=0,
            is_eligible_for_reward=False,
            reward_sent=False,
            reward_tx_hash=None,
            feedback="Diary content is too long. Maximum 5000 characters.",
            error="Content too long"
        )

    # Generate entry ID and content hash
    entry_id = generate_entry_id(wallet_address, content)
    content_hash = generate_content_hash(content)

    # === IPFS STORAGE ===
    image_ipfs_hash = None
    image_ipfs_url = None
    metadata_ipfs_hash = None
    metadata_ipfs_url = None

    # Save image locally first (always as backup)
    local_image_url = None
    if image_base64:
        local_image_url = save_image_locally(entry_id, image_base64)
        if local_image_url:
            print(f"[LOCAL] Image saved locally: {local_image_url}")

    # Upload image to IPFS if provided and configured
    if image_base64 and is_ipfs_configured():
        print(f"[IPFS] Uploading image for entry {entry_id}...")
        image_result = await upload_image_to_ipfs(image_base64, f"diary_{entry_id}.jpg")
        if image_result.success:
            image_ipfs_hash = image_result.ipfs_hash
            image_ipfs_url = image_result.ipfs_url
            print(f"[IPFS] Image uploaded: {image_ipfs_url}")
        else:
            print(f"[IPFS] Image upload failed: {image_result.error}")
            # Use local URL as fallback
            if local_image_url:
                image_ipfs_url = local_image_url
                print(f"[LOCAL] Using local image as fallback: {local_image_url}")

    # Verify quality with AI
    quality_score, feedback = await verify_diary_quality(title, content, location, image_base64)

    # Determine if eligible for reward (score >= 7)
    is_eligible = quality_score >= 7.0

    # Send reward if eligible
    reward_sent = False
    reward_tx_hash = None

    if is_eligible:
        reward_sent, reward_tx_hash = await send_ada_reward(wallet_address)
        if reward_sent:
            feedback += " Congratulations! You earned 1 ADA reward!"
        else:
            feedback += " You qualified for a reward but there was an issue processing it."

    # === CARDANO METADATA ===
    chain_tx_hash = None
    cardanoscan_url = None

    # Create and submit metadata to Cardano
    metadata = create_diary_metadata(
        entry_id=entry_id,
        title=title,
        location=location,
        content=content,
        image_ipfs_hash=image_ipfs_hash,
        quality_score=quality_score,
        is_rewarded=reward_sent,
        wallet_address=wallet_address
    )

    print(f"[CARDANO] Submitting metadata for entry {entry_id}...")
    chain_result = await submit_metadata_tx(metadata, wallet_address)
    if chain_result.success:
        chain_tx_hash = chain_result.tx_hash
        cardanoscan_url = chain_result.cardanoscan_url
        print(f"[CARDANO] Metadata stored: {cardanoscan_url}")
    else:
        print(f"[CARDANO] Metadata storage failed: {chain_result.error}")

    # Upload full metadata JSON to IPFS (for permanent storage)
    if is_ipfs_configured():
        full_metadata = {
            "entry_id": entry_id,
            "wallet_address": wallet_address,
            "title": title,
            "content": content,
            "location": location,
            "content_hash": content_hash,
            "image_ipfs": image_ipfs_hash,
            "quality_score": quality_score,
            "is_rewarded": reward_sent,
            "chain_tx_hash": chain_tx_hash,
            "created_at": datetime.utcnow().isoformat(),
            "app": "bengaluru-travel-diary",
            "version": "1.0"
        }
        metadata_result = await upload_json_to_ipfs(full_metadata, f"diary_metadata_{entry_id}.json")
        if metadata_result.success:
            metadata_ipfs_hash = metadata_result.ipfs_hash
            metadata_ipfs_url = metadata_result.ipfs_url
            print(f"[IPFS] Full metadata uploaded: {metadata_ipfs_url}")

    # Add storage info to feedback
    storage_info = []
    if image_ipfs_url:
        storage_info.append(f"Image stored on IPFS")
    if chain_tx_hash:
        storage_info.append(f"Metadata recorded on Cardano")
    if storage_info:
        feedback += f" [{', '.join(storage_info)}]"

    # Create entry
    entry = DiaryEntry(
        id=entry_id,
        wallet_address=wallet_address,
        title=title,
        content=content,
        location=location,
        image_base64=image_base64[:100] + "..." if image_base64 else None,
        created_at=datetime.utcnow().isoformat(),
        quality_score=quality_score,
        is_rewarded=reward_sent,
        reward_tx_hash=reward_tx_hash,
        verification_feedback=feedback,
        # New storage fields
        content_hash=content_hash,
        image_ipfs_hash=image_ipfs_hash,
        image_ipfs_url=image_ipfs_url,
        metadata_ipfs_hash=metadata_ipfs_hash,
        chain_tx_hash=chain_tx_hash,
        cardanoscan_url=cardanoscan_url
    )

    # Save entry locally (as index/cache)
    entries = load_diary_entries()
    entries.append(asdict(entry))
    save_diary_entries(entries)

    return DiarySubmissionResult(
        success=True,
        entry_id=entry_id,
        quality_score=quality_score,
        is_eligible_for_reward=is_eligible,
        reward_sent=reward_sent,
        reward_tx_hash=reward_tx_hash,
        feedback=feedback,
        error=None,
        image_ipfs_url=image_ipfs_url,
        metadata_ipfs_url=metadata_ipfs_url,
        chain_tx_hash=chain_tx_hash,
        cardanoscan_url=cardanoscan_url
    )


def get_recent_entries(limit: int = 20) -> list[dict]:
    """Get recent diary entries (for public gallery display)"""
    entries = load_diary_entries()

    # Sort by created_at descending
    entries.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    # Return limited entries with sensitive data removed
    public_entries = []
    for entry in entries[:limit]:
        content = entry.get('content', '')
        entry_id = entry.get('id')

        # Determine image URL - prefer IPFS, fallback to local
        image_url = entry.get('image_ipfs_url')
        if not image_url and entry_id:
            # Check if local image exists
            local_path = get_local_image_path(entry_id)
            if local_path:
                image_url = f"/diary/image/{entry_id}"

        public_entries.append({
            'id': entry_id,
            'title': entry.get('title'),
            'content_preview': content[:200] + '...' if len(content) > 200 else content,
            'content_full': content,  # Full content for expanded view
            'location': entry.get('location'),
            'created_at': entry.get('created_at'),
            'quality_score': entry.get('quality_score'),
            'is_rewarded': entry.get('is_rewarded'),
            'reward_tx_hash': entry.get('reward_tx_hash'),
            'verification_feedback': entry.get('verification_feedback', ''),
            'wallet_short': entry.get('wallet_address', '')[:20] + '...' if entry.get('wallet_address') else None,
            # Storage info - use computed image_url
            'image_ipfs_url': image_url,
            'image_ipfs_hash': entry.get('image_ipfs_hash'),
            'chain_tx_hash': entry.get('chain_tx_hash'),
            'cardanoscan_url': entry.get('cardanoscan_url'),
            'content_hash': entry.get('content_hash')
        })

    return public_entries


def get_wallet_stats(wallet_address: str) -> dict:
    """Get statistics for a wallet"""
    entries = get_entries_by_wallet(wallet_address)

    total_entries = len(entries)
    total_rewards = sum(1 for e in entries if e.get('is_rewarded'))
    avg_score = sum(e.get('quality_score', 0) for e in entries) / total_entries if total_entries > 0 else 0

    return {
        'wallet_address': wallet_address,
        'total_entries': total_entries,
        'total_rewards': total_rewards,
        'total_ada_earned': total_rewards,  # 1 ADA per reward
        'average_score': round(avg_score, 2),
        'can_submit_today': not has_submitted_today(wallet_address)
    }