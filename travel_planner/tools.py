"""
Custom Tools for Travel Itinerary Agent
- Google Distance Matrix API (with Geocode-first approach for accuracy)
- Google Geocoding API
- Google Places API
"""

import os
import httpx
from typing import Optional, Tuple

# Use environment variable for API key
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")


def _get_api_key() -> str:
    """Get API key from environment or raise error."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    return key


async def geocode_location(
    address: str,
    city: str = "Bengaluru"
) -> dict:
    """
    Convert an address or place name to geographic coordinates using Google Geocoding API.

    Args:
        address: The address or place name to geocode (e.g., "NIFT College, HSR Layout")
        city: City context for better accuracy (default: Bengaluru)

    Returns:
        dict with latitude, longitude, formatted address, and place details

    Example:
        result = await geocode_location("Cubbon Park")
        # Returns: {"latitude": 12.9763, "longitude": 77.5929, "formatted_address": "Cubbon Park, Bengaluru...", ...}
    """
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    # Add city context if not already present
    full_address = address if city.lower() in address.lower() else f"{address}, {city}, India"

    params = {
        "address": full_address,
        "key": _get_api_key(),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params, timeout=30.0)
            data = response.json()

            if data.get("status") != "OK":
                return {
                    "error": f"Geocoding Error: {data.get('status')}",
                    "error_message": data.get("error_message", "Location not found"),
                    "query": address,
                    "status": "ERROR"
                }

            result = data["results"][0]
            location = result["geometry"]["location"]

            # Extract useful address components
            address_components = {}
            for component in result.get("address_components", []):
                types = component.get("types", [])
                if "locality" in types:
                    address_components["city"] = component["long_name"]
                elif "sublocality_level_1" in types:
                    address_components["area"] = component["long_name"]
                elif "administrative_area_level_1" in types:
                    address_components["state"] = component["long_name"]
                elif "postal_code" in types:
                    address_components["pincode"] = component["long_name"]

            return {
                "query": address,
                "formatted_address": result["formatted_address"],
                "latitude": location["lat"],
                "longitude": location["lng"],
                "place_id": result.get("place_id"),
                "location_type": result["geometry"].get("location_type"),
                "address_components": address_components,
                "google_maps_url": f"https://www.google.com/maps?q={location['lat']},{location['lng']}",
                "status": "OK"
            }

    except httpx.TimeoutException:
        return {"error": "Request timed out", "query": address, "status": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e), "query": address, "status": "ERROR"}


async def _geocode_to_coords(address: str, city: str = "Bengaluru") -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Internal helper to geocode an address and return coordinates.

    Returns:
        Tuple of (latitude, longitude, formatted_address, error_message)
    """
    result = await geocode_location(address, city)

    if result.get("status") == "OK":
        return (
            result["latitude"],
            result["longitude"],
            result["formatted_address"],
            None
        )
    else:
        return (None, None, None, result.get("error", "Geocoding failed"))


async def get_distance_matrix(
    origins: str,
    destinations: str,
    mode: str = "driving",
    departure_time: Optional[str] = None,
    use_geocode: bool = True
) -> dict:
    """
    Get travel distance and duration between locations using Google Distance Matrix API.

    IMPROVED: Now geocodes addresses first for more accurate results.

    Args:
        origins: Starting location - address or place name (e.g., "NIFT College, HSR Layout, Bengaluru")
        destinations: Destination location - address or place name (e.g., "Lalbagh Botanical Garden, Bengaluru")
        mode: Travel mode - "driving", "walking", "bicycling", or "transit"
        departure_time: Optional departure time for traffic estimation (use "now" for current traffic)
        use_geocode: If True (default), geocode addresses first for accuracy

    Returns:
        dict with distance, duration, duration_in_traffic, coordinates, and resolved addresses

    Example:
        result = await get_distance_matrix(
            origins="NIFT College, HSR Layout, Bengaluru",
            destinations="Cubbon Park, Bengaluru",
            mode="driving",
            departure_time="now"
        )
    """
    base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    origin_coords = None
    dest_coords = None
    origin_resolved = origins
    dest_resolved = destinations

    # Step 1: Geocode both locations first for accuracy
    if use_geocode:
        # Geocode origin
        origin_lat, origin_lng, origin_address, origin_error = await _geocode_to_coords(origins)
        if origin_error:
            return {
                "error": f"Origin geocoding failed: {origin_error}",
                "origin_query": origins,
                "status": "GEOCODE_ERROR"
            }
        origin_coords = f"{origin_lat},{origin_lng}"
        origin_resolved = origin_address

        # Geocode destination
        dest_lat, dest_lng, dest_address, dest_error = await _geocode_to_coords(destinations)
        if dest_error:
            return {
                "error": f"Destination geocoding failed: {dest_error}",
                "destination_query": destinations,
                "status": "GEOCODE_ERROR"
            }
        dest_coords = f"{dest_lat},{dest_lng}"
        dest_resolved = dest_address

    # Step 2: Call Distance Matrix API with coordinates (more accurate) or addresses
    params = {
        "origins": origin_coords if use_geocode else origins,
        "destinations": dest_coords if use_geocode else destinations,
        "mode": mode,
        "key": _get_api_key(),
        "units": "metric",
    }

    if departure_time:
        params["departure_time"] = departure_time if departure_time != "now" else "now"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params, timeout=30.0)
            data = response.json()

            if data.get("status") != "OK":
                return {
                    "error": f"API Error: {data.get('status')}",
                    "error_message": data.get("error_message", "Unknown error"),
                    "status": "ERROR"
                }

            element = data["rows"][0]["elements"][0]

            if element.get("status") != "OK":
                return {
                    "error": f"Route Error: {element.get('status')}",
                    "status": "ERROR"
                }

            result = {
                # Original queries
                "origin_query": origins,
                "destination_query": destinations,
                # Resolved addresses (what was actually used)
                "origin_resolved": origin_resolved,
                "destination_resolved": dest_resolved,
                # Coordinates used (for verification)
                "origin_coordinates": origin_coords,
                "destination_coordinates": dest_coords,
                # Distance and duration
                "distance": element["distance"]["text"],
                "distance_meters": element["distance"]["value"],
                "distance_km": round(element["distance"]["value"] / 1000, 2),
                "duration": element["duration"]["text"],
                "duration_seconds": element["duration"]["value"],
                "duration_minutes": round(element["duration"]["value"] / 60),
                "travel_mode": mode,
                "status": "OK"
            }

            # Add traffic duration if available (only for driving with departure_time)
            if "duration_in_traffic" in element:
                result["duration_in_traffic"] = element["duration_in_traffic"]["text"]
                result["duration_in_traffic_seconds"] = element["duration_in_traffic"]["value"]
                result["duration_in_traffic_minutes"] = round(element["duration_in_traffic"]["value"] / 60)

            return result

    except httpx.TimeoutException:
        return {"error": "Request timed out", "status": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e), "status": "ERROR"}


async def get_multi_stop_distances(
    locations: list[str],
    mode: str = "driving"
) -> dict:
    """
    Get distances between multiple consecutive stops for route planning.
    Uses geocode-first approach for accurate results.

    Args:
        locations: List of locations in order of visit (e.g., ["NIFT College", "Temple", "Zoo", "Restaurant"])
        mode: Travel mode - "driving", "walking", "bicycling", or "transit"

    Returns:
        dict with leg-by-leg distances, coordinates, and total journey stats

    Example:
        result = await get_multi_stop_distances(
            locations=["NIFT HSR Layout", "Ragigudda Temple", "Lalbagh Garden", "Bannerghatta Zoo"],
            mode="driving"
        )
    """
    if len(locations) < 2:
        return {"error": "Need at least 2 locations", "status": "ERROR"}

    # First, geocode all locations
    geocoded_locations = []
    for loc in locations:
        lat, lng, address, error = await _geocode_to_coords(loc)
        if error:
            geocoded_locations.append({
                "query": loc,
                "error": error,
                "status": "ERROR"
            })
        else:
            geocoded_locations.append({
                "query": loc,
                "formatted_address": address,
                "latitude": lat,
                "longitude": lng,
                "coordinates": f"{lat},{lng}",
                "status": "OK"
            })

    # Calculate distances between consecutive stops
    legs = []
    total_distance_meters = 0
    total_duration_seconds = 0
    total_duration_traffic_seconds = 0

    for i in range(len(locations) - 1):
        origin_geo = geocoded_locations[i]
        dest_geo = geocoded_locations[i + 1]

        # Skip if either location failed to geocode
        if origin_geo.get("status") != "OK" or dest_geo.get("status") != "OK":
            legs.append({
                "leg_number": i + 1,
                "from_query": locations[i],
                "to_query": locations[i + 1],
                "error": "Geocoding failed for one or both locations",
                "status": "ERROR"
            })
            continue

        # Use coordinates for distance matrix
        result = await get_distance_matrix(
            origins=locations[i],
            destinations=locations[i + 1],
            mode=mode,
            departure_time="now",
            use_geocode=True  # Already geocoded, but let it verify
        )

        if result.get("status") == "OK":
            leg = {
                "leg_number": i + 1,
                "from_query": locations[i],
                "from_resolved": result.get("origin_resolved"),
                "from_coordinates": result.get("origin_coordinates"),
                "to_query": locations[i + 1],
                "to_resolved": result.get("destination_resolved"),
                "to_coordinates": result.get("destination_coordinates"),
                "distance": result["distance"],
                "distance_km": result["distance_km"],
                "duration": result["duration"],
                "duration_minutes": result["duration_minutes"],
                "status": "OK"
            }

            if "duration_in_traffic" in result:
                leg["duration_in_traffic"] = result["duration_in_traffic"]
                leg["duration_in_traffic_minutes"] = result["duration_in_traffic_minutes"]
                total_duration_traffic_seconds += result.get("duration_in_traffic_seconds", 0)

            legs.append(leg)
            total_distance_meters += result.get("distance_meters", 0)
            total_duration_seconds += result.get("duration_seconds", 0)
        else:
            legs.append({
                "leg_number": i + 1,
                "from_query": locations[i],
                "to_query": locations[i + 1],
                "error": result.get("error", "Unknown error"),
                "status": "ERROR"
            })

    return {
        "legs": legs,
        "geocoded_locations": geocoded_locations,
        "total_distance_km": round(total_distance_meters / 1000, 2),
        "total_duration_minutes": round(total_duration_seconds / 60),
        "total_duration_in_traffic_minutes": round(total_duration_traffic_seconds / 60) if total_duration_traffic_seconds > 0 else None,
        "number_of_stops": len(locations),
        "travel_mode": mode,
        "status": "OK"
    }


async def reverse_geocode(
    latitude: float,
    longitude: float
) -> dict:
    """
    Convert geographic coordinates to a human-readable address.

    Args:
        latitude: Latitude coordinate (e.g., 12.9716)
        longitude: Longitude coordinate (e.g., 77.5946)

    Returns:
        dict with formatted address and place details
    """
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        "latlng": f"{latitude},{longitude}",
        "key": _get_api_key(),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params, timeout=30.0)
            data = response.json()

            if data.get("status") != "OK":
                return {
                    "error": f"Reverse Geocoding Error: {data.get('status')}",
                    "status": "ERROR"
                }

            result = data["results"][0]

            return {
                "latitude": latitude,
                "longitude": longitude,
                "formatted_address": result["formatted_address"],
                "place_id": result.get("place_id"),
                "status": "OK"
            }

    except Exception as e:
        return {"error": str(e), "status": "ERROR"}


async def find_nearby_places(
    location: str,
    place_type: str,
    radius_meters: int = 5000
) -> dict:
    """
    Find nearby places of a specific type using Google Places API.
    Uses geocoding for accurate center point.

    Args:
        location: Center location for search (e.g., "HSR Layout, Bengaluru")
        place_type: Type of place to find (e.g., "restaurant", "temple", "park", "cafe")
        radius_meters: Search radius in meters (default: 5000 = 5km)

    Returns:
        dict with list of nearby places including coordinates
    """
    # First geocode the location
    geo_result = await geocode_location(location)

    if geo_result.get("status") != "OK":
        return geo_result

    lat = geo_result["latitude"]
    lng = geo_result["longitude"]

    # Use Places Text Search API
    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    params = {
        "query": f"{place_type} near {location}",
        "location": f"{lat},{lng}",
        "radius": radius_meters,
        "key": _get_api_key(),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params, timeout=30.0)
            data = response.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                return {
                    "error": f"Places API Error: {data.get('status')}",
                    "status": "ERROR"
                }

            places = []
            for place in data.get("results", [])[:10]:  # Limit to top 10
                place_location = place.get("geometry", {}).get("location", {})
                places.append({
                    "name": place.get("name"),
                    "address": place.get("formatted_address"),
                    "latitude": place_location.get("lat"),
                    "longitude": place_location.get("lng"),
                    "coordinates": f"{place_location.get('lat')},{place_location.get('lng')}",
                    "rating": place.get("rating"),
                    "total_ratings": place.get("user_ratings_total"),
                    "price_level": place.get("price_level"),  # 0-4 scale
                    "open_now": place.get("opening_hours", {}).get("open_now"),
                    "place_id": place.get("place_id"),
                    "types": place.get("types", []),
                })

            return {
                "search_location": location,
                "search_center": {
                    "latitude": lat,
                    "longitude": lng,
                    "formatted_address": geo_result["formatted_address"]
                },
                "search_type": place_type,
                "radius_km": radius_meters / 1000,
                "places_found": len(places),
                "places": places,
                "status": "OK"
            }

    except Exception as e:
        return {"error": str(e), "status": "ERROR"}


def estimate_cab_fare(distance_km: float, duration_minutes: int, cab_type: str = "auto") -> dict:
    """
    Estimate cab/auto fare for Bengaluru based on distance and duration.

    Args:
        distance_km: Distance in kilometers
        duration_minutes: Duration in minutes
        cab_type: "auto", "mini", "sedan", "suv", "xl"

    Returns:
        Fare estimate with breakdown
    """
    # Approximate Bengaluru rates (2024-2025)
    rates = {
        "auto": {"base": 30, "per_km": 15, "per_min": 1},
        "mini": {"base": 50, "per_km": 12, "per_min": 1.5},
        "sedan": {"base": 80, "per_km": 14, "per_min": 1.5},
        "suv": {"base": 100, "per_km": 18, "per_min": 2},
        "xl": {"base": 120, "per_km": 22, "per_min": 2.5},  # For groups (6+ people)
        "tempo": {"base": 500, "per_km": 25, "per_min": 3},  # Tempo traveler (10+ people)
    }

    rate = rates.get(cab_type.lower(), rates["auto"])

    distance_charge = distance_km * rate["per_km"]
    time_charge = duration_minutes * rate["per_min"]
    base_fare = rate["base"]

    total = base_fare + distance_charge + time_charge

    # Add surge estimate (1.2x average for peak hours)
    surge_estimate = total * 1.2

    return {
        "cab_type": cab_type,
        "distance_km": distance_km,
        "duration_minutes": duration_minutes,
        "base_fare": round(base_fare),
        "distance_charge": round(distance_charge),
        "time_charge": round(time_charge),
        "estimated_fare": round(total),
        "with_surge_estimate": round(surge_estimate),
        "currency": "INR",
        "note": "Fares are approximate. Actual fares may vary based on traffic, surge pricing, and route."
    }


async def calculate_route_with_fares(
    locations: list[str],
    group_size: int = 4,
    mode: str = "driving"
) -> dict:
    """
    Calculate complete route with distance, duration, and fare estimates.
    Recommends transport options based on group size.

    Args:
        locations: List of locations in order
        group_size: Number of people traveling
        mode: Travel mode

    Returns:
        Complete route with fares for different transport options
    """
    # Get multi-stop distances
    route = await get_multi_stop_distances(locations, mode)

    if route.get("status") != "OK":
        return route

    total_km = route["total_distance_km"]
    total_mins = route["total_duration_minutes"]
    traffic_mins = route.get("total_duration_in_traffic_minutes", total_mins)

    # Calculate fares for different options
    fare_options = []

    if group_size <= 3:
        # Auto is best for small groups
        auto_fare = estimate_cab_fare(total_km, traffic_mins, "auto")
        fare_options.append({
            "option": "Auto Rickshaw",
            "suitable_for": "1-3 people",
            "total_fare": auto_fare["estimated_fare"],
            "per_person": round(auto_fare["estimated_fare"] / group_size),
            "with_surge": auto_fare["with_surge_estimate"],
            "recommended": True
        })

    if group_size <= 4:
        # Mini cab
        mini_fare = estimate_cab_fare(total_km, traffic_mins, "mini")
        fare_options.append({
            "option": "Ola/Uber Mini",
            "suitable_for": "1-4 people",
            "total_fare": mini_fare["estimated_fare"],
            "per_person": round(mini_fare["estimated_fare"] / group_size),
            "with_surge": mini_fare["with_surge_estimate"],
            "recommended": group_size == 4
        })

    if group_size <= 6:
        # SUV/XL
        suv_fare = estimate_cab_fare(total_km, traffic_mins, "suv")
        fare_options.append({
            "option": "Ola/Uber XL (SUV)",
            "suitable_for": "4-6 people",
            "total_fare": suv_fare["estimated_fare"],
            "per_person": round(suv_fare["estimated_fare"] / group_size),
            "with_surge": suv_fare["with_surge_estimate"],
            "recommended": 4 <= group_size <= 6
        })

    if group_size > 6:
        # Multiple cabs or tempo traveler
        # Option 1: Multiple SUVs
        num_cabs = (group_size + 5) // 6  # Ceiling division
        suv_fare = estimate_cab_fare(total_km, traffic_mins, "suv")
        fare_options.append({
            "option": f"{num_cabs}x Ola/Uber XL",
            "suitable_for": f"{group_size} people in {num_cabs} cabs",
            "total_fare": suv_fare["estimated_fare"] * num_cabs,
            "per_person": round((suv_fare["estimated_fare"] * num_cabs) / group_size),
            "with_surge": suv_fare["with_surge_estimate"] * num_cabs,
            "recommended": False
        })

        # Option 2: Tempo Traveler (better for groups)
        tempo_fare = estimate_cab_fare(total_km, traffic_mins, "tempo")
        fare_options.append({
            "option": "Tempo Traveler",
            "suitable_for": "8-12 people (book via Savaari/Zoomcar)",
            "total_fare": tempo_fare["estimated_fare"],
            "per_person": round(tempo_fare["estimated_fare"] / group_size),
            "with_surge": tempo_fare["with_surge_estimate"],
            "recommended": True,
            "note": "Advance booking required. Best for day trips."
        })

    route["group_size"] = group_size
    route["fare_options"] = fare_options
    route["recommended_option"] = next((f for f in fare_options if f.get("recommended")), fare_options[0])

    return route