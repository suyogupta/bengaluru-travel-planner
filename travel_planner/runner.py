"""
Travel Itinerary Agent Runner
==============================
Simple interface to run the multi-agent travel planner.
"""

import os
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from google.adk.runners import InMemoryRunner

# Configure logging
logger = logging.getLogger("travel_planner")
logger.setLevel(logging.INFO)

# Set API key before importing agents
if "GOOGLE_API_KEY" not in os.environ:
    logger.error("GOOGLE_API_KEY environment variable is not set!")
    raise EnvironmentError("Please set GOOGLE_API_KEY environment variable")
else:
    logger.info("GOOGLE_API_KEY is configured")

from .travel_agents import itinerary_coordinator, get_all_agents


@dataclass
class TravelQuery:
    """Structured travel query input."""

    # Required fields
    type: str  # fullday, morning, evening, night
    people: str  # friends, family, couple, corporate, solo
    number_of_people: int
    location: str  # Starting location
    date_of_plan: str  # Date in any format
    start_time: str  # e.g., "10 AM"

    # Optional fields
    occasion: Optional[str] = None
    inclusions: Optional[list[str]] = None
    budget: Optional[int] = None
    budget_mode: str = "flexible"  # strict or flexible
    transport_mode: Optional[str] = None  # auto, cab, metro, mixed
    remarks: Optional[str] = None

    def to_query_string(self) -> str:
        """Convert to query string format for the agent."""
        parts = [
            f"type:{self.type}",
            f"people:{self.people}",
            f"numberOfPeople:{self.number_of_people}",
            f"location:{self.location}",
            f"dateOfPlan:{self.date_of_plan}",
            f"startTime:{self.start_time}",
        ]

        if self.occasion:
            parts.append(f"occasion:{self.occasion}")

        if self.inclusions:
            parts.append(f"inclusions:{', '.join(self.inclusions)}")

        if self.budget:
            parts.append(f"budget:{self.budget}")
            parts.append(f"budgetMode:{self.budget_mode}")

        if self.transport_mode:
            parts.append(f"transportMode:{self.transport_mode}")

        if self.remarks:
            parts.append(f"remarks:{self.remarks}")

        return ", ".join(parts)


class TravelPlannerRunner:
    """Runner for the travel planner agent system."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.runner = InMemoryRunner(
            agent=itinerary_coordinator,
            app_name="travel_planner"
        )
        self.agents = get_all_agents()
        self._session_counter = 0

    async def plan_trip(self, query: TravelQuery) -> str:
        """
        Generate a travel itinerary based on the query.

        Args:
            query: TravelQuery object with trip details

        Returns:
            Formatted itinerary string
        """
        query_string = query.to_query_string()
        return await self._run_agent(query_string)

    async def plan_trip_raw(self, query_string: str) -> str:
        """
        Generate itinerary from raw query string.

        Args:
            query_string: Raw query like "type:fullday, people:friends, ..."

        Returns:
            Formatted itinerary string
        """
        return await self._run_agent(query_string)

    async def _run_agent(self, query_string: str) -> str:
        """Internal method to run the agent with proper API."""
        import uuid
        from google.genai import types
        from google.adk.sessions import InMemorySessionService
        from google.adk.runners import Runner

        self._session_counter += 1
        user_id = "travel_user"
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        app_name = "travel_planner"

        logger.info(f"[SESSION {session_id}] Starting agent execution")
        logger.info(f"[SESSION {session_id}] Query: {query_string[:100]}...")

        if self.debug:
            print(f"\n{'='*60}")
            print("TRAVEL PLANNER - Debug Mode")
            print(f"{'='*60}")
            print(f"Query: {query_string}")
            print(f"Session: {session_id}")
            print(f"{'='*60}\n")

        try:
            # Create session service and session explicitly
            logger.info(f"[SESSION {session_id}] Creating InMemorySessionService...")
            session_service = InMemorySessionService()
            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            logger.info(f"[SESSION {session_id}] Session created successfully")

            # Create Runner with explicit session service
            logger.info(f"[SESSION {session_id}] Creating Runner with itinerary_coordinator...")
            runner = Runner(
                agent=itinerary_coordinator,
                app_name=app_name,
                session_service=session_service,
            )
            logger.info(f"[SESSION {session_id}] Runner created successfully")

            # Create proper message content object
            user_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=query_string)]
            )

            result_text = ""
            event_count = 0

            logger.info(f"[SESSION {session_id}] Starting run_async - calling AI agents...")
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                event_count += 1
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                result_text += part.text
                                if self.debug:
                                    print(part.text, end="", flush=True)

            logger.info(f"[SESSION {session_id}] run_async completed - {event_count} events, {len(result_text)} chars result")

            if self.debug:
                print(f"\n{'='*60}\n")

            return result_text

        except Exception as e:
            logger.error(f"[SESSION {session_id}] AGENT ERROR: {str(e)}")
            import traceback
            logger.error(f"[SESSION {session_id}] Traceback:\n{traceback.format_exc()}")
            raise


# =============================================================================
# Quick-run functions for notebook/interactive use
# =============================================================================

async def quick_plan(
    plan_type: str = "fullday",
    people: str = "friends",
    num_people: int = 4,
    location: str = "HSR Layout, Bengaluru",
    date: str = "7 December 2025",
    start_time: str = "10 AM",
    inclusions: list[str] = None,
    occasion: str = None,
    budget: int = None,
) -> str:
    """
    Quick function to generate an itinerary.

    Example:
        result = await quick_plan(
            plan_type="fullday",
            people="friends",
            num_people=8,
            location="NIFT College, HSR Layout",
            date="5 December 2025",
            start_time="10 AM",
            inclusions=["temple", "zoo", "nature"],
            occasion="weekend fun"
        )
        print(result)
    """
    query = TravelQuery(
        type=plan_type,
        people=people,
        number_of_people=num_people,
        location=location,
        date_of_plan=date,
        start_time=start_time,
        inclusions=inclusions,
        occasion=occasion,
        budget=budget,
    )

    runner = TravelPlannerRunner(debug=True)
    return await runner.plan_trip(query)


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Command-line interface for the travel planner."""
    import argparse

    parser = argparse.ArgumentParser(description="Bengaluru Travel Planner AI")
    parser.add_argument("--type", default="fullday", help="Plan type: fullday/morning/evening/night")
    parser.add_argument("--people", default="friends", help="Group type: friends/family/couple/solo")
    parser.add_argument("--num", type=int, default=4, help="Number of people")
    parser.add_argument("--location", required=True, help="Starting location")
    parser.add_argument("--date", required=True, help="Date of plan")
    parser.add_argument("--time", default="10 AM", help="Start time")
    parser.add_argument("--inclusions", nargs="+", help="Activities to include")
    parser.add_argument("--occasion", help="Occasion for the trip")
    parser.add_argument("--budget", type=int, help="Total budget in INR")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    query = TravelQuery(
        type=args.type,
        people=args.people,
        number_of_people=args.num,
        location=args.location,
        date_of_plan=args.date,
        start_time=args.time,
        inclusions=args.inclusions,
        occasion=args.occasion,
        budget=args.budget,
    )

    runner = TravelPlannerRunner(debug=args.debug)
    result = asyncio.run(runner.plan_trip(query))
    print(result)


if __name__ == "__main__":
    main()