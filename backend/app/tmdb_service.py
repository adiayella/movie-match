import os
from datetime import date
from typing import Optional

import httpx

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

LANGUAGE_MAP = {
    "hindi": "hi",
    "english": "en",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
}

ERA_RANGES = {
    "classic": (1900, 1999),
    "classic (pre-2000)": (1900, 1999),
    "2000-2020": (2000, 2020),
    "2000–2020": (2000, 2020),
    "recent": (2021, 2026),
    "recent (2021-2026)": (2021, 2026),
    "recent (2021–2026)": (2021, 2026),
    "any": None,
}

_genre_cache: dict = {}


def _headers() -> dict:
    return {"Authorization": f"Bearer {TMDB_API_KEY}", "accept": "application/json"}


def language_label_to_iso(label: str) -> Optional[str]:
    return LANGUAGE_MAP.get(label.strip().lower())


def era_to_year_range(label: str):
    return ERA_RANGES.get(label.strip().lower())


def _fetch_genre_map(media_type: str) -> dict:
    if media_type in _genre_cache:
        return _genre_cache[media_type]
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{BASE_URL}/genre/{media_type}/list", headers=_headers()
            )
            resp.raise_for_status()
            data = resp.json()
        mapping = {g["name"].lower(): g["id"] for g in data.get("genres", [])}
    except httpx.HTTPError:
        mapping = {}
    _genre_cache[media_type] = mapping
    return mapping


def _map_genres_to_ids(genre_names: list, media_type: str) -> list:
    mapping = _fetch_genre_map(media_type)
    ids = []
    for name in genre_names or []:
        gid = mapping.get(str(name).lower())
        if gid:
            ids.append(gid)
    return ids


def _normalize(item: dict, media_type: str) -> Optional[dict]:
    title = item.get("title") or item.get("name")
    if not title:
        return None
    date = item.get("release_date") or item.get("first_air_date") or ""
    year = None
    if date and len(date) >= 4:
        try:
            year = int(date[:4])
        except ValueError:
            year = None
    poster_path = item.get("poster_path")
    return {
        "tmdb_id": item.get("id"),
        "media_type": media_type,
        "title": title,
        "year": year,
        "imdb_rating": item.get("vote_average"),
        "runtime": None,
        "synopsis": item.get("overview"),
        "poster_url": f"{IMAGE_BASE}{poster_path}" if poster_path else None,
    }


def _fetch_runtime(tmdb_id: int, media_type: str) -> Optional[int]:
    if media_type != "movie":
        return None
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{BASE_URL}/movie/{tmdb_id}", headers=_headers()
            )
            resp.raise_for_status()
            return resp.json().get("runtime")
    except httpx.HTTPError:
        return None


def _discover(media_type: str, brief: dict, min_rating: int, exclude_ids: Optional[set] = None) -> list:
    params = {
        "sort_by": "popularity.desc",
        "vote_average.gte": min_rating,
        # A vote_average off a handful of votes is noise: obscure titles
        # routinely sit at 10.0 from a single vote and would otherwise
        # dominate a "7+ rating" pool. 20 is deliberately low -- TMDB vote
        # counts are sparse for regional Indian cinema, and a stricter floor
        # (50) cut a Telugu pool from 30 titles down to 11.
        "vote_count.gte": 20,
    }
    genre_ids = _map_genres_to_ids(brief.get("genres", []), media_type)
    if genre_ids:
        # Pipe = OR ("any of these genres"), comma = AND ("all of these
        # genres"). We want OR: a brief naming 3+ genres should widen the
        # pool, not require every title to match all of them at once
        # (comma routinely returned zero results for anything but the
        # most generic genre combos).
        params["with_genres"] = "|".join(str(g) for g in genre_ids)

    languages_iso = brief.get("languages_iso") or []
    if len(languages_iso) == 1:
        params["with_original_language"] = languages_iso[0]

    year_min = brief.get("year_min")
    year_max = brief.get("year_max")
    date_field = "primary_release_date" if media_type == "movie" else "first_air_date"
    if year_min:
        params[f"{date_field}.gte"] = f"{year_min}-01-01"
    # Never propose something that isn't out yet. The whole promise of the
    # app is "watch it tonight, here's where" -- an unreleased title has no
    # streaming options at all, so a match on one is a dead end.
    today = date.today().isoformat()
    upper = f"{year_max}-12-31" if year_max else today
    params[f"{date_field}.lte"] = min(upper, today)

    results = []
    try:
        with httpx.Client(timeout=10) as client:
            # One page is only 20 results, which left round 2 with almost
            # nothing after de-duplicating against round 1. Pull a few pages
            # so both rounds have a full deck to work with.
            for page in range(1, 4):
                resp = client.get(
                    f"{BASE_URL}/discover/{media_type}",
                    headers=_headers(),
                    params={**params, "page": page},
                )
                resp.raise_for_status()
                page_results = resp.json().get("results", [])
                if not page_results:
                    break
                results.extend(page_results)
    except httpx.HTTPError:
        pass

    normalized = []
    for item in results:
        norm = _normalize(item, media_type)
        if not norm or not norm["tmdb_id"]:
            continue
        if exclude_ids and norm["tmdb_id"] in exclude_ids:
            continue
        normalized.append(norm)
    return normalized


def get_imdb_id(tmdb_id: int, media_type: str) -> Optional[str]:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids", headers=_headers()
            )
            resp.raise_for_status()
            return resp.json().get("imdb_id")
    except httpx.HTTPError:
        return None


def discover_titles(brief: dict, content_type: str, min_rating: int, exclude_ids: Optional[set] = None) -> list:
    media_types = brief.get("media_types") or ["movie"]
    want_movies = "movie" in media_types
    want_tv = "tv" in media_types and content_type != "Movies only"
    if content_type == "Movies only":
        want_tv = False

    results = []
    if want_movies:
        results.extend(_discover("movie", brief, min_rating, exclude_ids))
    if want_tv:
        results.extend(_discover("tv", brief, min_rating, exclude_ids))

    seen = set()
    deduped = []
    for item in results:
        key = (item["media_type"], item["tmdb_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda x: x.get("imdb_rating") or 0, reverse=True)
    top = deduped[:30]

    for item in top:
        if item["media_type"] == "movie":
            item["runtime"] = _fetch_runtime(item["tmdb_id"], "movie")

    return top
