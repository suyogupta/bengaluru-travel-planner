"""
Travel Planner API - Masumi Network Integration
MIP-003 Compatible Endpoints + Custom Features
"""

import os
import logging
import sys

# Configure logging for production visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("travel_api")
logger.setLevel(logging.INFO)

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

logger.info("=" * 60)
logger.info("TRAVEL PLANNER API STARTING")
logger.info("=" * 60)
logger.info(f"GOOGLE_API_KEY set: {bool(os.getenv('GOOGLE_API_KEY'))}")
logger.info(f"BLOCKFROST_API_KEY set: {bool(os.getenv('BLOCKFROST_API_KEY'))}")
logger.info(f"MASUMI_API_URL: {os.getenv('MASUMI_API_URL', 'http://localhost:3001')}")
logger.info(f"MASUMI_API_KEY set: {bool(os.getenv('MASUMI_API_KEY'))}")
logger.info("=" * 60)

# Now import the rest
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Agent imports - use the actual TravelPlannerRunner
from travel_planner import TravelQuery, TravelPlannerRunner

# Payment verification
from api.payment import (
    verify_payment,
    is_payment_already_used,
    mark_payment_as_used,
    get_payment_info,
    PAYMENT_WALLET_ADDRESS,
    REQUIRED_PAYMENT_LOVELACE,
)

# Masumi escrow integration
from api.masumi import (
    create_masumi_payment,
    check_masumi_payment,
    complete_masumi_payment,
    get_masumi_info,
)

# Travel Diary feature
from api.diary import (
    submit_diary_entry,
    get_recent_entries,
    get_wallet_stats,
    has_submitted_today,
)

app = FastAPI(
    title="Bengaluru Travel Planner Agent",
    description="AI-powered travel itinerary planner with Masumi Network integration",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Enums & Models ==============

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUNDED = "refunded"


class ItineraryRequest(BaseModel):
    """Input for travel itinerary generation - matches TravelQuery"""
    # Required fields
    plan_type: str = Field(
        default="fullday",
        description="Plan type: fullday, morning, evening, night"
    )
    people: str = Field(
        default="friends",
        description="Group type: friends, family, couple, corporate, solo"
    )
    number_of_people: int = Field(
        default=4,
        description="Number of people in the group",
        ge=1,
        le=50
    )
    location: str = Field(
        ...,
        description="Starting location in Bengaluru (e.g., 'HSR Layout', 'Koramangala')"
    )
    date_of_plan: str = Field(
        ...,
        description="Date of the plan (e.g., '7 December 2025')"
    )
    start_time: str = Field(
        default="10 AM",
        description="Start time (e.g., '10 AM', '9:30 AM')"
    )

    # Optional fields
    occasion: Optional[str] = Field(
        default=None,
        description="Occasion: birthday, anniversary, casual, celebration, weekend fun"
    )
    inclusions: Optional[list[str]] = Field(
        default=None,
        description="Activities to include: temple, zoo, nature, food, shopping, museum, adventure"
    )
    budget: Optional[int] = Field(
        default=None,
        description="Total budget in INR for all people",
        ge=500
    )
    budget_mode: str = Field(
        default="flexible",
        description="Budget mode: strict or flexible"
    )
    transport_mode: Optional[str] = Field(
        default=None,
        description="Preferred transport: auto, cab, metro, mixed"
    )
    remarks: Optional[str] = Field(
        default=None,
        description="Special requests or remarks"
    )


class StartJobRequest(BaseModel):
    """MIP-003 start_job request"""
    input_data: ItineraryRequest
    payment_tx_hash: Optional[str] = Field(default=None, description="Cardano transaction hash for payment")


class StartJobResponse(BaseModel):
    """MIP-003 start_job response"""
    job_id: str
    status: JobStatus
    payment_required: float  # ADA amount
    payment_address: str


class JobStatusResponse(BaseModel):
    """MIP-003 status response"""
    job_id: str
    status: JobStatus
    progress: Optional[int] = None
    message: Optional[str] = None


class JobResultResponse(BaseModel):
    """MIP-003 result response"""
    job_id: str
    status: JobStatus
    result: Optional[dict] = None
    error: Optional[str] = None


class FeedbackSpot(BaseModel):
    """Feedback for a single spot"""
    spot_name: str
    photo_url: str  # In real app: upload to IPFS
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Photo feedback submission"""
    spots: list[FeedbackSpot]
    overall_rating: int = Field(ge=1, le=5)
    overall_comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Feedback verification result"""
    verified: bool
    verification_details: list[dict]
    reward_earned: float  # ADA amount
    reward_tx_hash: Optional[str] = None
    nft_eligible_photos: list[str]  # Photo URLs eligible for NFT


class NFTMintRequest(BaseModel):
    """NFT minting request"""
    photo_url: str
    title: str
    description: Optional[str] = None


class NFTMintResponse(BaseModel):
    """NFT minting result"""
    success: bool
    nft_id: Optional[str] = None
    policy_id: Optional[str] = None
    asset_name: Optional[str] = None
    transaction_hash: Optional[str] = None
    ipfs_url: Optional[str] = None
    message: str


class GalleryPhoto(BaseModel):
    """Community gallery photo"""
    photo_url: str
    title: str
    spot_name: str
    photographer: str
    nft_id: Optional[str] = None
    likes: int = 0
    timestamp: datetime


# ============== In-Memory Storage (Demo) ==============

jobs_db: dict[str, dict] = {}
feedback_db: dict[str, dict] = {}
gallery_db: list[GalleryPhoto] = []

# Real payment address (Cardano Preprod)
ITINERARY_PRICE_ADA = 2.0  # Cost per itinerary in ADA
FEEDBACK_REWARD_ADA = 0.5  # Reward per verified feedback


# ============== Agent Runner ==============

async def run_agent(job_id: str, request: ItineraryRequest):
    """Run the travel planner agent asynchronously using TravelPlannerRunner"""
    logger.info(f"[JOB {job_id}] Starting agent run")
    logger.info(f"[JOB {job_id}] Request: location={request.location}, date={request.date_of_plan}, people={request.number_of_people}")

    try:
        jobs_db[job_id]["status"] = JobStatus.PROCESSING
        jobs_db[job_id]["progress"] = 10
        logger.info(f"[JOB {job_id}] Status: PROCESSING (10%)")

        # Convert API request to TravelQuery
        query = TravelQuery(
            type=request.plan_type,
            people=request.people,
            number_of_people=request.number_of_people,
            location=request.location,
            date_of_plan=request.date_of_plan,
            start_time=request.start_time,
            occasion=request.occasion,
            inclusions=request.inclusions,
            budget=request.budget,
            budget_mode=request.budget_mode,
            transport_mode=request.transport_mode,
            remarks=request.remarks,
        )
        logger.info(f"[JOB {job_id}] TravelQuery created: {query.to_query_string()}")

        jobs_db[job_id]["progress"] = 20
        jobs_db[job_id]["message"] = "Initializing travel planner agents..."
        logger.info(f"[JOB {job_id}] Initializing TravelPlannerRunner...")

        # Use the actual TravelPlannerRunner
        runner = TravelPlannerRunner(debug=False)
        logger.info(f"[JOB {job_id}] TravelPlannerRunner initialized")

        jobs_db[job_id]["progress"] = 40
        jobs_db[job_id]["message"] = "Researching attractions, events, transport..."
        logger.info(f"[JOB {job_id}] Starting plan_trip() - calling AI agents...")

        # Run the agent
        result_text = await runner.plan_trip(query)
        logger.info(f"[JOB {job_id}] plan_trip() completed, result length: {len(result_text)} chars")

        jobs_db[job_id]["progress"] = 100
        jobs_db[job_id]["status"] = JobStatus.COMPLETED
        jobs_db[job_id]["result"] = {
            "itinerary": result_text,
            "query": {
                "type": request.plan_type,
                "people": request.people,
                "number_of_people": request.number_of_people,
                "location": request.location,
                "date": request.date_of_plan,
                "start_time": request.start_time,
                "occasion": request.occasion,
                "inclusions": request.inclusions,
            },
            "generated_at": datetime.now().isoformat(),
        }
        logger.info(f"[JOB {job_id}] SUCCESS - Job completed!")

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[JOB {job_id}] FAILED - Error: {str(e)}")
        logger.error(f"[JOB {job_id}] Traceback:\n{error_traceback}")
        jobs_db[job_id]["status"] = JobStatus.FAILED
        jobs_db[job_id]["error"] = str(e)
        jobs_db[job_id]["traceback"] = error_traceback


# ============== MIP-003 Endpoints ==============

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "name": "Bengaluru Travel Planner Agent",
        "version": "1.0.0",
        "masumi_compatible": True,
        "mip_version": "MIP-003",
        "features": [
            "AI-powered itinerary generation",
            "Multi-agent system (Research, Events, Transport, Food, Weather)",
            "Pay-per-use with ADA",
            "Photo-verified feedback rewards",
            "NFT minting for travel photos",
        ],
    }


@app.get("/availability")
async def check_availability():
    """MIP-003: Check agent availability"""
    return {
        "available": True,
        "queue_length": len([j for j in jobs_db.values() if j["status"] == JobStatus.PENDING]),
        "estimated_wait_seconds": 60,
        "price_ada": ITINERARY_PRICE_ADA,
    }


@app.get("/input_schema")
async def get_input_schema():
    """MIP-003: Return the input schema for this agent"""
    return {
        "schema": ItineraryRequest.model_json_schema(),
        "example": {
            "plan_type": "fullday",
            "people": "friends",
            "number_of_people": 8,
            "location": "HSR Layout, Bengaluru",
            "date_of_plan": "7 December 2025",
            "start_time": "10 AM",
            "occasion": "weekend fun",
            "inclusions": ["temple", "nature", "food"],
            "budget": 5000,
            "budget_mode": "flexible",
            "transport_mode": "cab",
            "remarks": "Prefer outdoor activities",
        },
        "field_options": {
            "plan_type": ["fullday", "morning", "evening", "night"],
            "people": ["friends", "family", "couple", "corporate", "solo"],
            "budget_mode": ["strict", "flexible"],
            "transport_mode": ["auto", "cab", "metro", "mixed"],
            "inclusions": [
                "temple", "zoo", "nature", "food", "shopping",
                "museum", "adventure", "park", "lake", "brewery",
                "cafe", "historical", "art", "nightlife"
            ],
        },
    }


@app.get("/payment-info")
async def payment_info():
    """Get payment information for users"""
    return get_payment_info()


@app.post("/start_job", response_model=StartJobResponse)
async def start_job(request: StartJobRequest, background_tasks: BackgroundTasks):
    """MIP-003: Start a new itinerary generation job (requires 2 ADA payment)"""
    job_id = str(uuid.uuid4())

    # Create job record
    jobs_db[job_id] = {
        "id": job_id,
        "status": JobStatus.PENDING,
        "input": request.input_data.model_dump(),
        "payment_status": PaymentStatus.PENDING,
        "payment_tx_hash": request.payment_tx_hash,
        "created_at": datetime.now().isoformat(),
        "progress": 0,
        "message": "Pay 2 ADA to the wallet address, then submit your transaction hash",
        "result": None,
        "error": None,
    }

    # If tx_hash provided, verify payment on blockchain
    if request.payment_tx_hash:
        # Check if payment was already used
        if await is_payment_already_used(request.payment_tx_hash):
            raise HTTPException(
                status_code=400,
                detail="This transaction has already been used for another job"
            )

        # Verify payment on Cardano blockchain
        verification = await verify_payment(request.payment_tx_hash)

        if verification.is_valid:
            mark_payment_as_used(request.payment_tx_hash)
            jobs_db[job_id]["payment_status"] = PaymentStatus.CONFIRMED
            jobs_db[job_id]["message"] = "Payment verified! Generating itinerary..."
            # Start processing in background
            background_tasks.add_task(run_agent, job_id, request.input_data)
        else:
            jobs_db[job_id]["message"] = f"Payment verification failed: {verification.error}"

    return StartJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        payment_required=ITINERARY_PRICE_ADA,
        payment_address=PAYMENT_WALLET_ADDRESS,
    )


@app.post("/confirm_payment/{job_id}")
async def confirm_payment(job_id: str, tx_hash: str, background_tasks: BackgroundTasks):
    """Verify payment on Cardano blockchain and start job processing"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs_db[job_id]

    if job["payment_status"] == PaymentStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="Payment already confirmed")

    # Check if payment was already used for another job
    if await is_payment_already_used(tx_hash):
        raise HTTPException(
            status_code=400,
            detail="This transaction has already been used for another job"
        )

    # Verify payment on Cardano blockchain via Blockfrost
    verification = await verify_payment(tx_hash)

    if not verification.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Payment verification failed: {verification.error}"
        )

    # Mark payment as used and confirmed
    mark_payment_as_used(tx_hash)
    job["payment_status"] = PaymentStatus.CONFIRMED
    job["payment_tx_hash"] = tx_hash
    job["message"] = "Payment verified! Starting itinerary generation..."

    # Start agent processing
    input_data = ItineraryRequest(**job["input"])
    background_tasks.add_task(run_agent, job_id, input_data)

    return {
        "message": "Payment verified on Cardano blockchain! Job processing started.",
        "job_id": job_id,
        "amount_paid_lovelace": verification.amount_lovelace,
        "amount_paid_ada": verification.amount_lovelace / 1_000_000,
        "tx_hash": tx_hash,
    }


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """MIP-003: Get job status"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs_db[job_id]

    message = job.get("message", "")
    if job["status"] == JobStatus.PENDING:
        message = f"Payment: {job['payment_status']}"

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        message=message,
    )


@app.get("/result/{job_id}", response_model=JobResultResponse)
async def get_job_result(job_id: str):
    """MIP-003: Get job result"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs_db[job_id]

    if job["status"] not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Job not yet completed")

    return JobResultResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )


# ============== Feedback & Rewards Endpoints ==============

@app.post("/feedback/{job_id}", response_model=FeedbackResponse)
async def submit_feedback(job_id: str, feedback: FeedbackRequest):
    """Submit photo feedback for a completed itinerary"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs_db[job_id]

    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only submit feedback for completed itineraries")

    # Verify photos (in production: use AI vision model to verify)
    verification_results = []
    nft_eligible = []
    verified_count = 0

    for spot in feedback.spots:
        # Demo verification - in production, use vision AI to:
        # 1. Verify photo matches the location
        # 2. Check photo quality for NFT eligibility
        # 3. Detect if photo is stock/duplicate

        is_verified = True  # Demo: always verified
        is_nft_quality = spot.rating >= 4  # High-rated photos eligible for NFT

        verification_results.append({
            "spot_name": spot.spot_name,
            "verified": is_verified,
            "photo_quality_score": 0.85,  # Demo score
            "nft_eligible": is_nft_quality,
        })

        if is_verified:
            verified_count += 1
        if is_nft_quality:
            nft_eligible.append(spot.photo_url)

    # Calculate reward based on verified spots
    total_spots = len(feedback.spots)
    verification_rate = verified_count / total_spots if total_spots > 0 else 0

    reward = FEEDBACK_REWARD_ADA * verification_rate

    # Store feedback
    feedback_db[job_id] = {
        "job_id": job_id,
        "feedback": feedback.model_dump(),
        "verification_results": verification_results,
        "reward_earned": reward,
        "submitted_at": datetime.now().isoformat(),
    }

    # In production: Send ADA reward to user's wallet
    reward_tx_hash = f"tx_{uuid.uuid4().hex[:16]}" if reward > 0 else None

    return FeedbackResponse(
        verified=verified_count == total_spots,
        verification_details=verification_results,
        reward_earned=reward,
        reward_tx_hash=reward_tx_hash,
        nft_eligible_photos=nft_eligible,
    )


# ============== NFT Minting Endpoints ==============

@app.post("/mint-nft/{job_id}", response_model=NFTMintResponse)
async def mint_nft(job_id: str, request: NFTMintRequest):
    """Mint a travel photo as NFT on Cardano"""
    if job_id not in feedback_db:
        raise HTTPException(status_code=404, detail="Feedback not found. Submit feedback first.")

    feedback = feedback_db[job_id]

    # Check if photo is eligible for NFT
    eligible_photos = [
        v["spot_name"] for v in feedback["verification_results"]
        if v.get("nft_eligible")
    ]

    # Demo NFT minting response
    # In production: Use Cardano NFT minting with Lucid/cardano-cli
    nft_id = f"TravelMemory_{uuid.uuid4().hex[:8]}"
    policy_id = f"policy_{uuid.uuid4().hex[:24]}"

    # Add to gallery
    gallery_db.append(GalleryPhoto(
        photo_url=request.photo_url,
        title=request.title,
        spot_name=request.title,
        photographer=f"traveler_{job_id[:8]}",
        nft_id=nft_id,
        likes=0,
        timestamp=datetime.now(),
    ))

    return NFTMintResponse(
        success=True,
        nft_id=nft_id,
        policy_id=policy_id,
        asset_name=f"TravelMemory{job_id[:8]}",
        transaction_hash=f"tx_{uuid.uuid4().hex[:32]}",
        ipfs_url=f"ipfs://Qm{uuid.uuid4().hex[:44]}",
        message=f"Successfully minted '{request.title}' as NFT!",
    )


@app.get("/gallery")
async def get_gallery(limit: int = 20, offset: int = 0):
    """Get community photo gallery"""
    sorted_gallery = sorted(gallery_db, key=lambda x: x.timestamp, reverse=True)

    return {
        "total": len(gallery_db),
        "photos": [photo.model_dump() for photo in sorted_gallery[offset:offset + limit]],
    }


@app.post("/gallery/{photo_index}/like")
async def like_photo(photo_index: int):
    """Like a photo in the gallery"""
    if photo_index >= len(gallery_db):
        raise HTTPException(status_code=404, detail="Photo not found")

    gallery_db[photo_index].likes += 1

    return {"likes": gallery_db[photo_index].likes}


# ============== Demo Endpoints ==============

@app.post("/demo/quick-plan")
async def demo_quick_plan(request: ItineraryRequest, background_tasks: BackgroundTasks):
    """Demo endpoint - skip payment for testing"""
    job_id = str(uuid.uuid4())

    jobs_db[job_id] = {
        "id": job_id,
        "status": JobStatus.PENDING,
        "input": request.model_dump(),
        "payment_status": PaymentStatus.CONFIRMED,  # Auto-confirm for demo
        "payment_tx_hash": "demo_tx",
        "created_at": datetime.now().isoformat(),
        "progress": 0,
        "message": "Starting...",
        "result": None,
        "error": None,
    }

    background_tasks.add_task(run_agent, job_id, request)

    return {"job_id": job_id, "message": "Demo job started (payment skipped)"}


@app.get("/demo/jobs")
async def list_all_jobs():
    """Demo endpoint - list all jobs"""
    return {
        "jobs": [
            {
                "job_id": job_id,
                "status": job["status"],
                "progress": job.get("progress", 0),
                "message": job.get("message", ""),
                "created_at": job["created_at"],
            }
            for job_id, job in jobs_db.items()
        ]
    }


@app.get("/demo/job/{job_id}/debug")
async def get_job_debug(job_id: str):
    """Demo endpoint - get full job details for debugging"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]


# ============== Masumi Escrow Endpoints ==============

# Store for Masumi payment-to-job mapping
masumi_jobs: dict[str, dict] = {}


@app.get("/masumi/info")
async def masumi_info():
    """Get Masumi integration info"""
    return get_masumi_info()


@app.post("/masumi/create-payment")
async def create_payment_request(request: ItineraryRequest):
    """
    Create a Masumi escrow payment request.

    This creates an escrow payment where funds are held in a smart contract.
    The payment is protected - held until the agent completes work.
    """
    # Create Masumi payment request with input data for hash
    input_data = request.model_dump()
    payment = await create_masumi_payment(input_data, REQUIRED_PAYMENT_LOVELACE)

    if payment.error:
        raise HTTPException(status_code=500, detail=payment.error)

    # Create job record linked to Masumi payment
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {
        "id": job_id,
        "status": JobStatus.PENDING,
        "input": input_data,
        "payment_status": PaymentStatus.PENDING,
        "payment_method": "masumi_escrow",
        "masumi_payment_id": payment.payment_id,
        "blockchain_identifier": payment.blockchain_identifier,
        "created_at": datetime.now().isoformat(),
        "progress": 0,
        "message": "Pay to smart contract, then call /masumi/verify-payment",
        "result": None,
        "error": None,
    }

    # Map Masumi payment to job
    masumi_jobs[payment.payment_id] = job_id

    return {
        "job_id": job_id,
        "payment_id": payment.payment_id,
        "blockchain_identifier": payment.blockchain_identifier,
        "seller_address": payment.seller_address,
        "amount_lovelace": payment.amount_lovelace,
        "amount_ada": payment.amount_lovelace / 1_000_000,
        "instructions": [
            "1. Use the blockchain_identifier to submit payment to smart contract",
            "2. Send exactly 2 ADA to the seller address",
            "3. Wait for transaction confirmation (~20 blocks)",
            "4. Call /masumi/verify-payment/{payment_id} to verify and start job",
            "5. Your payment is protected by Masumi escrow"
        ],
        "payment_protection": "Your payment is held in smart contract escrow until the agent completes work"
    }


@app.post("/masumi/verify-payment/{payment_id}")
async def verify_masumi_payment(payment_id: str, background_tasks: BackgroundTasks):
    """
    Verify a Masumi escrow payment and start the job.
    """
    # Check payment status via Masumi
    payment_status = await check_masumi_payment(payment_id)

    if payment_status.error:
        raise HTTPException(status_code=500, detail=payment_status.error)

    if not payment_status.is_paid:
        return {
            "verified": False,
            "status": payment_status.status,
            "message": "Payment not yet confirmed. Please wait for blockchain confirmation."
        }

    # Get linked job
    if payment_id not in masumi_jobs:
        raise HTTPException(status_code=404, detail="Payment ID not linked to any job")

    job_id = masumi_jobs[payment_id]
    job = jobs_db.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["payment_status"] == PaymentStatus.CONFIRMED:
        return {
            "verified": True,
            "job_id": job_id,
            "message": "Payment already verified. Job is processing."
        }

    # Update job status
    job["payment_status"] = PaymentStatus.CONFIRMED
    job["message"] = "Masumi payment verified! Generating itinerary..."

    # Start agent processing
    input_data = ItineraryRequest(**job["input"])
    background_tasks.add_task(run_agent_with_masumi_complete, job_id, input_data, payment_id)

    return {
        "verified": True,
        "job_id": job_id,
        "status": "processing",
        "message": "Payment verified via Masumi escrow! Job started."
    }


async def run_agent_with_masumi_complete(job_id: str, request: ItineraryRequest, payment_id: str):
    """Run agent and complete Masumi payment on success"""
    try:
        # Run the normal agent
        await run_agent(job_id, request)

        # If successful, complete the Masumi payment (releases escrow)
        job = jobs_db.get(job_id)
        if job and job["status"] == JobStatus.COMPLETED:
            result_hash = job_id  # Use job_id as result hash
            success = await complete_masumi_payment(payment_id, result_hash)
            if success:
                job["masumi_escrow_released"] = True
                job["message"] = "Itinerary complete! Escrow payment released."

    except Exception as e:
        jobs_db[job_id]["status"] = JobStatus.FAILED
        jobs_db[job_id]["error"] = str(e)


@app.get("/masumi/payment-status/{payment_id}")
async def get_masumi_payment_status(payment_id: str):
    """Check Masumi payment status"""
    status = await check_masumi_payment(payment_id)

    job_id = masumi_jobs.get(payment_id)
    job_status = None
    if job_id and job_id in jobs_db:
        job_status = jobs_db[job_id]["status"]

    return {
        "payment_id": payment_id,
        "payment_status": status.status,
        "is_paid": status.is_paid,
        "job_id": job_id,
        "job_status": job_status,
        "error": status.error
    }


# ============== Travel Diary Endpoints ==============

class DiarySubmitRequest(BaseModel):
    """Request to submit a travel diary entry"""
    wallet_address: str = Field(..., description="Cardano wallet address (starts with 'addr')")
    title: str = Field(..., description="Diary entry title", min_length=5, max_length=100)
    content: str = Field(..., description="Diary content (50-5000 chars)", min_length=50, max_length=5000)
    location: str = Field(..., description="Location in Bengaluru where you visited")
    image_base64: Optional[str] = Field(default=None, description="Base64 encoded travel photo (JPEG/PNG)")


class DiarySubmitResponse(BaseModel):
    """Response from diary submission"""
    success: bool
    entry_id: Optional[str]
    quality_score: float
    is_eligible_for_reward: bool
    reward_sent: bool
    reward_amount_ada: float = 1.0
    reward_tx_hash: Optional[str]
    feedback: str
    error: Optional[str]


@app.post("/diary/submit", response_model=DiarySubmitResponse)
async def submit_diary(request: DiarySubmitRequest):
    """
    Submit a travel diary entry with optional photo.

    - One entry per wallet address per day
    - AI verifies quality (score 0-10)
    - Score >= 7 earns 1 ADA reward
    - Photo increases chances of higher score
    """
    result = await submit_diary_entry(
        wallet_address=request.wallet_address,
        title=request.title,
        content=request.content,
        location=request.location,
        image_base64=request.image_base64
    )

    return DiarySubmitResponse(
        success=result.success,
        entry_id=result.entry_id,
        quality_score=result.quality_score,
        is_eligible_for_reward=result.is_eligible_for_reward,
        reward_sent=result.reward_sent,
        reward_amount_ada=1.0 if result.reward_sent else 0.0,
        reward_tx_hash=result.reward_tx_hash,
        feedback=result.feedback,
        error=result.error
    )


@app.get("/diary/entries")
async def get_diary_entries(limit: int = 10):
    """Get recent diary entries from the community"""
    entries = get_recent_entries(limit=limit)
    return {
        "total": len(entries),
        "entries": entries
    }


@app.get("/diary/check/{wallet_address}")
async def check_diary_eligibility(wallet_address: str):
    """Check if a wallet can submit a diary entry today"""
    can_submit = not has_submitted_today(wallet_address)
    stats = get_wallet_stats(wallet_address)

    return {
        "wallet_address": wallet_address,
        "can_submit_today": can_submit,
        "stats": stats,
        "reward_per_quality_entry": "1 ADA",
        "minimum_quality_score": 7.0
    }


@app.get("/diary/stats/{wallet_address}")
async def get_diary_stats(wallet_address: str):
    """Get diary statistics for a wallet"""
    stats = get_wallet_stats(wallet_address)
    return stats


@app.get("/diary/info")
async def diary_info():
    """Get information about the travel diary feature"""
    return {
        "feature": "Travel Diary with AI Rewards",
        "description": "Share your Bengaluru travel experiences and earn ADA rewards",
        "rules": {
            "submission_limit": "1 entry per wallet per day",
            "reward_amount": "1 ADA",
            "minimum_score": 7.0,
            "content_length": "50-5000 characters",
            "photo_bonus": "Including a photo increases your score"
        },
        "scoring_criteria": {
            "authenticity": "2 points - Genuine travel experience",
            "detail": "2 points - Specific details about place/food/experience",
            "engagement": "2 points - Interesting and well-written",
            "relevance": "2 points - About Bengaluru/Karnataka travel",
            "photo": "2 points - Relevant travel photo included"
        },
        "tips": [
            "Write about specific places you visited",
            "Include details about food, culture, or experiences",
            "Upload a photo from your trip",
            "Be genuine - AI detects generic content",
            "Share what made your visit special"
        ]
    }


@app.get("/diary/image/{entry_id}")
async def get_diary_image(entry_id: str):
    """Serve locally stored diary images"""
    from api.diary import get_local_image_path

    image_path = get_local_image_path(entry_id)
    if image_path and image_path.exists():
        return FileResponse(
            image_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    raise HTTPException(status_code=404, detail="Image not found")


# ============== Static Files (Frontend) ==============

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.get("/app")
async def serve_frontend():
    """Serve the frontend app"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found")


if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)