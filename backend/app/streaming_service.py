import os

import httpx

from . import tmdb_service

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "ott-details.p.rapidapi.com")
BASE_URL = f"https://{RAPIDAPI_HOST}"


def get_ott_platforms(tmdb_id: int, media_type: str, country: str = "IN") -> list:
    if not RAPIDAPI_KEY:
        return []

    imdb_id = tmdb_service.get_imdb_id(tmdb_id, media_type)
    if not imdb_id:
        return []

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{BASE_URL}/gettitleDetails",
                headers=headers,
                params={"imdbid": imdb_id},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return []

    platforms = []
    try:
        options = (data.get("streamingAvailability") or {}).get("country", {}).get(
            country, []
        )
        for opt in options:
            platform = opt.get("platform")
            platforms.append(
                {
                    "name": platform,
                    "logo_url": None,
                    "deep_link": opt.get("url"),
                }
            )
    except (AttributeError, TypeError):
        return []

    return platforms
