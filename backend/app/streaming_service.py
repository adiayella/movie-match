import os
from typing import Optional

import httpx

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "streaming-availability.p.rapidapi.com")
BASE_URL = f"https://{RAPIDAPI_HOST}"


def get_ott_platforms(tmdb_id: int, media_type: str, country: str = "in") -> list:
    if not RAPIDAPI_KEY:
        return []
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }
    tmdb_ref = f"{media_type}/{tmdb_id}"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{BASE_URL}/shows/{tmdb_ref}",
                headers=headers,
                params={"country": country},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return []

    platforms = []
    try:
        streaming_options = data.get("streamingOptions", {}) or {}
        options = streaming_options.get(country, [])
        for opt in options:
            service = opt.get("service", {}) or {}
            platforms.append(
                {
                    "name": service.get("name") or service.get("id"),
                    "logo_url": (
                        (service.get("imageSet") or {}).get("lightThemeImage")
                        or service.get("imageUrl")
                    ),
                    "deep_link": opt.get("link"),
                }
            )
    except (AttributeError, TypeError):
        return []

    return platforms
