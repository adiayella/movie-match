import os
from concurrent.futures import ThreadPoolExecutor
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


def _discover(
    media_type: str,
    brief: dict,
    min_rating: int,
    exclude_ids: Optional[set] = None,
    vote_floor: int = 20,
    use_genres: bool = True,
    use_era: bool = True,
) -> list:
    params = {
        "sort_by": "popularity.desc",
        "vote_average.gte": min_rating,
        # A vote_average off a handful of votes is noise: obscure titles
        # routinely sit at 10.0 from a single vote and would otherwise
        # dominate a "7+ rating" pool. 20 is deliberately low -- TMDB vote
        # counts are sparse for regional Indian cinema, and a stricter floor
        # (50) cut a Telugu pool from 30 titles down to 11.
        "vote_count.gte": vote_floor,
    }
    genre_ids = _map_genres_to_ids(brief.get("genres", []), media_type) if use_genres else []
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

    year_min = brief.get("year_min") if use_era else None
    year_max = brief.get("year_max") if use_era else None
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


TARGET_POOL = 30


def discover_titles(brief: dict, content_type: str, min_rating: int, exclude_ids: Optional[set] = None) -> list:
    media_types = brief.get("media_types") or ["movie"]
    want_movies = "movie" in media_types
    want_tv = "tv" in media_types and content_type != "Movies only"
    if content_type == "Movies only":
        want_tv = False

    # Narrow preference combinations legitimately return nothing -- "Telugu
    # horror/thriller rated 8+" has zero matches on TMDB, and the couple
    # would just hit a dead end. So widen the net in stages and keep topping
    # the deck up, strictest matches first: the exact ask leads, looser
    # results only fill whatever space is left. Language is never relaxed --
    # serving Hindi films to someone who asked for Telugu is a worse answer
    # than a slightly lower-rated Telugu one.
    ladder = [
        dict(min_rating=min_rating, vote_floor=20, use_genres=True, use_era=True),
        dict(min_rating=min_rating, vote_floor=5, use_genres=True, use_era=True),
        dict(min_rating=min_rating, vote_floor=5, use_genres=False, use_era=True),
        dict(min_rating=max(6, min_rating - 1), vote_floor=5, use_genres=True, use_era=True),
        dict(min_rating=max(6, min_rating - 2), vote_floor=5, use_genres=False, use_era=True),
        dict(min_rating=6, vote_floor=5, use_genres=False, use_era=False),
        dict(min_rating=0, vote_floor=0, use_genres=False, use_era=False),
    ]

    seen = set()
    deduped: list = []
    for step in ladder:
        batch = []
        if want_movies:
            batch.extend(_discover("movie", brief, exclude_ids=exclude_ids, **step))
        if want_tv:
            batch.extend(_discover("tv", brief, exclude_ids=exclude_ids, **step))

        batch.sort(key=lambda x: x.get("imdb_rating") or 0, reverse=True)
        for item in batch:
            key = (item["media_type"], item["tmdb_id"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        if len(deduped) >= TARGET_POOL:
            break

    top = deduped[:TARGET_POOL]

    # Runtime needs a per-title detail call. Done serially that was 30
    # round trips tacked onto the end of pool generation -- with both
    # partners already staring at a spinner, and long enough to risk the
    # request timing out on a phone. These are independent, so fan them out.
    movies = [t for t in top if t["media_type"] == "movie"]
    if movies:
        with ThreadPoolExecutor(max_workers=8) as pool:
            runtimes = pool.map(
                lambda t: _fetch_runtime(t["tmdb_id"], "movie"), movies
            )
            for item, runtime in zip(movies, runtimes):
                item["runtime"] = runtime

    return top
