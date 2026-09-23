import os
import random
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import claude_service, streaming_service, tmdb_service
from .db import get_client
from .models import (
    CreateSessionRequest,
    FinalizeRequest,
    PreferencesRequest,
    RatingRequest,
    SwipeRequest,
)
from .qr import generate_qr_base64

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173")

# CORS: allow the frontend dev origin, and any origin via env for now (MVP simplification).
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")

app = FastAPI(title="Movie Match API")


# Registered BEFORE the CORS middleware so that CORS ends up outermost and
# still decorates error responses. An exception escaping to Starlette's
# default handler produces a 500 with no CORS headers, which a browser can
# only report as an opaque "Failed to fetch"/"Load failed" -- indistinguishable
# from the server being down, and impossible to show the user anything useful
# about. Convert it to a normal JSON response instead.
@app.middleware("http")
async def json_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 -- last line of defence
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}"},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOWED_ORIGINS == "*" else ALLOWED_ORIGINS.split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db():
    return get_client()


def _resolve_partner(db, session_id: str, device_id: str, fallback: str) -> str:
    """Authoritative partner lookup by device_id. Never trust a client-supplied
    partner label for anything that affects match detection or pool
    ordering -- a device's locally cached guess can go stale (e.g. it
    re-visits the join link after already being assigned a slot), and a
    stale guess silently corrupts swipe attribution. Falls back to the
    caller-supplied value only when this device has no preferences row yet
    (nothing authoritative to resolve against)."""
    row = (
        db.table("preferences")
        .select("partner")
        .eq("session_id", session_id)
        .eq("device_id", device_id)
        .limit(1)
        .execute()
    )
    if row.data:
        return row.data[0]["partner"]
    return fallback


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/sessions")
def create_session(body: CreateSessionRequest):
    db = _db()
    pair_id = body.pair_id
    if not pair_id:
        pair_resp = db.table("pairs").insert({}).execute()
        pair_id = pair_resp.data[0]["id"]

    session_resp = (
        db.table("sessions")
        .insert({"pair_id": pair_id, "status": "waiting_b", "round": 1})
        .execute()
    )
    session_id = session_resp.data[0]["id"]

    join_url = f"{PUBLIC_BASE_URL}/s/{session_id}"
    qr_png_base64 = generate_qr_base64(join_url)

    return {
        "session_id": session_id,
        "pair_id": pair_id,
        "join_url": join_url,
        "qr_png_base64": qr_png_base64,
    }


@app.post("/sessions/{session_id}/join")
def join_session(session_id: str):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]
    if session["status"] == "waiting_b":
        db.table("sessions").update({"status": "collecting_prefs"}).eq(
            "id", session_id
        ).execute()
        session["status"] = "collecting_prefs"
    return session


def _title_pool_context(pool_rows: list) -> list:
    return [
        {
            "tmdb_id": r["tmdb_id"],
            "title": r["title"],
            "media_type": r["media_type"],
            "year": r["year"],
        }
        for r in pool_rows
    ]


@app.post("/sessions/{session_id}/preferences")
def submit_preferences(session_id: str, body: PreferencesRequest):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]

    # The client's requested partner slot is only a hint. Whichever slot a
    # device actually gets is decided here, keyed by device_id -- this is
    # the single source of truth. Relying on the client to guess its own
    # slot in advance breaks whenever both people reach this form the same
    # way (e.g. both just open the shared link instead of one continuing
    # from the "creator" screen on their own device), which silently
    # doubled up both submissions as the same partner.
    existing_resp = (
        db.table("preferences").select("*").eq("session_id", session_id).execute()
    )
    existing = existing_resp.data or []
    device_row = next((p for p in existing if p.get("device_id") == body.device_id), None)

    if device_row:
        assigned_partner = device_row["partner"]
        db.table("preferences").update(
            {
                "moods": body.moods,
                "mood_text": body.mood_text,
                "languages": body.languages,
                "content_type": body.content_type,
                "min_rating": body.min_rating,
                "eras": body.eras,
            }
        ).eq("id", device_row["id"]).execute()
    else:
        occupied = {p["partner"] for p in existing}
        if len(occupied) >= 2:
            raise HTTPException(
                status_code=409, detail="This session already has two partners"
            )
        assigned_partner = "A" if "A" not in occupied else "B"
        db.table("preferences").insert(
            {
                "session_id": session_id,
                "partner": assigned_partner,
                "device_id": body.device_id,
                "moods": body.moods,
                "mood_text": body.mood_text,
                "languages": body.languages,
                "content_type": body.content_type,
                "min_rating": body.min_rating,
                "eras": body.eras,
            }
        ).execute()

    prefs_resp = (
        db.table("preferences").select("*").eq("session_id", session_id).execute()
    )
    prefs = prefs_resp.data
    partners_present = {p["partner"] for p in prefs}

    error: Optional[str] = None
    if {"A", "B"} <= partners_present and session["status"] != "swiping":
        profile_a = next(p for p in prefs if p["partner"] == "A")
        profile_b = next(p for p in prefs if p["partner"] == "B")

        history = None
        if session.get("pair_id"):
            hist_resp = (
                db.table("ratings")
                .select("*")
                .eq("pair_id", session["pair_id"])
                .execute()
            )
            history = hist_resp.data or None

        # Never let a failure here (a flaky/blocked external API, a bad
        # brief, whatever) silently flip the session to "swiping" with an
        # empty pool -- that used to strand both partners on an infinite
        # "waiting" screen with zero explanation. Keep status unchanged and
        # surface a real error the client can show + retry on instead.
        try:
            brief = claude_service.build_search_brief(profile_a, profile_b, history)

            content_type = profile_a.get("content_type") or profile_b.get("content_type")
            min_rating = max(
                profile_a.get("min_rating") or 6, profile_b.get("min_rating") or 6
            )

            titles = tmdb_service.discover_titles(brief, content_type, min_rating)

            if not titles:
                raise RuntimeError(
                    "No titles matched these preferences (TMDB returned nothing, "
                    "or TMDB was unreachable). Try again, or broaden your language/"
                    "era/rating choices."
                )

            rows = [
                {
                    "session_id": session_id,
                    "round": 1,
                    "tmdb_id": t["tmdb_id"],
                    "media_type": t["media_type"],
                    "title": t["title"],
                    "year": t["year"],
                    "imdb_rating": t["imdb_rating"],
                    "runtime": t["runtime"],
                    "synopsis": t["synopsis"],
                    "poster_url": t["poster_url"],
                }
                for t in titles
            ]
            db.table("title_pool").insert(rows).execute()

            db.table("sessions").update({"status": "swiping"}).eq(
                "id", session_id
            ).execute()
            session["status"] = "swiping"
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any
            # failure in this block must not corrupt session status.
            error = str(exc)

    return {"status": session["status"], "partner": assigned_partner, "error": error}


@app.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    partner: str = Query(...),
    device_id: Optional[str] = Query(None),
):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]

    if device_id:
        partner = _resolve_partner(db, session_id, device_id, partner)

    pool_resp = (
        db.table("title_pool")
        .select("*")
        .eq("session_id", session_id)
        .eq("round", session["round"])
        .execute()
    )
    pool = pool_resp.data or []

    rng = random.Random(f"{partner}{session_id}")
    rng.shuffle(pool)

    match = None
    if session["status"] == "matched":
        match_resp = (
            db.table("matches")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if match_resp.data:
            match_row = match_resp.data[0]
            title_resp = (
                db.table("title_pool")
                .select("*")
                .eq("session_id", session_id)
                .eq("tmdb_id", match_row["tmdb_id"])
                .limit(1)
                .execute()
            )
            title_row = title_resp.data[0] if title_resp.data else {}
            match = {**title_row, "ott_platforms": match_row.get("ott_platforms") or []}

    return {"session": session, "pool": pool, "match": match}


def _current_pool(db, session_id: str, round_num: int) -> list:
    resp = (
        db.table("title_pool")
        .select("*")
        .eq("session_id", session_id)
        .eq("round", round_num)
        .execute()
    )
    return resp.data or []


def _swipes_for_round(db, session_id: str, round_num: int) -> list:
    resp = (
        db.table("swipes")
        .select("*")
        .eq("session_id", session_id)
        .eq("round", round_num)
        .execute()
    )
    return resp.data or []


@app.post("/sessions/{session_id}/swipes")
def submit_swipe(session_id: str, body: SwipeRequest):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]
    partner = _resolve_partner(db, session_id, body.device_id, body.partner)

    db.table("swipes").insert(
        {
            "session_id": session_id,
            "partner": partner,
            "tmdb_id": body.tmdb_id,
            "round": body.round,
            "direction": body.direction,
        }
    ).execute()

    swipes = _swipes_for_round(db, session_id, body.round)

    if body.direction == "right":
        others_right = [
            s
            for s in swipes
            if s["tmdb_id"] == body.tmdb_id
            and s["direction"] == "right"
            and s["partner"] != partner
        ]
        if others_right:
            pool = _current_pool(db, session_id, body.round)
            title_row = next((t for t in pool if t["tmdb_id"] == body.tmdb_id), None)
            media_type = title_row["media_type"] if title_row else "movie"

            ott = streaming_service.get_ott_platforms(body.tmdb_id, media_type)

            db.table("matches").insert(
                {
                    "session_id": session_id,
                    "tmdb_id": body.tmdb_id,
                    "round": body.round,
                    "ott_platforms": ott,
                }
            ).execute()
            db.table("sessions").update({"status": "matched"}).eq(
                "id", session_id
            ).execute()

            return {
                "matched": True,
                "tmdb_id": body.tmdb_id,
                "ott_platforms": ott,
                **({k: title_row[k] for k in title_row} if title_row else {}),
            }

    pool = _current_pool(db, session_id, body.round)
    pool_ids = {t["tmdb_id"] for t in pool}

    def swiped_ids(partner: str) -> set:
        return {s["tmdb_id"] for s in swipes if s["partner"] == partner}

    a_done = pool_ids <= swiped_ids("A")
    b_done = pool_ids <= swiped_ids("B")

    if a_done and b_done:
        if body.round == 1:
            a_liked_ids = {
                s["tmdb_id"]
                for s in swipes
                if s["partner"] == "A" and s["direction"] == "right"
            }
            b_liked_ids = {
                s["tmdb_id"]
                for s in swipes
                if s["partner"] == "B" and s["direction"] == "right"
            }
            liked_ids = a_liked_ids | b_liked_ids
            liked_titles = [t for t in pool if t["tmdb_id"] in liked_ids]

            prefs_resp = (
                db.table("preferences")
                .select("*")
                .eq("session_id", session_id)
                .execute()
            )
            prefs = prefs_resp.data
            profile_a = next((p for p in prefs if p["partner"] == "A"), {})
            profile_b = next((p for p in prefs if p["partner"] == "B"), {})
            base_brief = claude_service.build_search_brief(profile_a, profile_b, None)

            refined_brief = claude_service.refine_from_swipes(
                base_brief, _title_pool_context(liked_titles)
            )

            content_type = profile_a.get("content_type") or profile_b.get(
                "content_type"
            )
            min_rating = max(
                profile_a.get("min_rating") or 6, profile_b.get("min_rating") or 6
            )

            exclude_ids = pool_ids
            new_titles = tmdb_service.discover_titles(
                refined_brief, content_type, min_rating, exclude_ids=exclude_ids
            )

            rows = [
                {
                    "session_id": session_id,
                    "round": 2,
                    "tmdb_id": t["tmdb_id"],
                    "media_type": t["media_type"],
                    "title": t["title"],
                    "year": t["year"],
                    "imdb_rating": t["imdb_rating"],
                    "runtime": t["runtime"],
                    "synopsis": t["synopsis"],
                    "poster_url": t["poster_url"],
                }
                for t in new_titles
            ]
            if rows:
                db.table("title_pool").insert(rows).execute()

            db.table("sessions").update({"round": 2, "status": "swiping"}).eq(
                "id", session_id
            ).execute()

            return {"round_complete": True, "next_round": 2}

        else:
            round1_swipes = _swipes_for_round(db, session_id, 1)
            round2_swipes = swipes
            all_swipes = round1_swipes + round2_swipes

            scores: dict = {}
            for s in all_swipes:
                if s["direction"] == "right":
                    key = s["tmdb_id"]
                    scores.setdefault(key, set()).add(s["partner"])

            pool_r1 = _current_pool(db, session_id, 1)
            all_pool = {t["tmdb_id"]: t for t in pool_r1}
            all_pool.update({t["tmdb_id"]: t for t in pool})

            ranked = sorted(
                scores.items(), key=lambda kv: len(kv[1]), reverse=True
            )[:5]
            top5 = []
            for tmdb_id, partners in ranked:
                title_row = all_pool.get(tmdb_id)
                if title_row:
                    top5.append({**title_row, "score": len(partners)})

            db.table("sessions").update({"status": "final_choice"}).eq(
                "id", session_id
            ).execute()

            return {"round_complete": True, "final_choice": True, "top5": top5}

    return {"matched": False, "waiting": True}


@app.post("/sessions/{session_id}/finalize")
def finalize(session_id: str, body: FinalizeRequest):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]

    pool = _current_pool(db, session_id, session["round"])
    title_row = next((t for t in pool if t["tmdb_id"] == body.tmdb_id), None)
    if not title_row:
        pool_r1 = _current_pool(db, session_id, 1)
        title_row = next((t for t in pool_r1 if t["tmdb_id"] == body.tmdb_id), None)

    media_type = title_row["media_type"] if title_row else "movie"
    ott = streaming_service.get_ott_platforms(body.tmdb_id, media_type)

    db.table("matches").insert(
        {
            "session_id": session_id,
            "tmdb_id": body.tmdb_id,
            "round": session["round"],
            "ott_platforms": ott,
        }
    ).execute()
    db.table("sessions").update({"status": "matched"}).eq("id", session_id).execute()

    return {
        "matched": True,
        "tmdb_id": body.tmdb_id,
        "ott_platforms": ott,
        **({k: title_row[k] for k in title_row} if title_row else {}),
    }


@app.post("/ratings")
def submit_rating(body: RatingRequest):
    db = _db()
    db.table("ratings").insert(
        {
            "pair_id": body.pair_id,
            "tmdb_id": body.tmdb_id,
            "partner": body.partner,
            "rating": body.rating,
        }
    ).execute()
    return {"ok": True}


@app.get("/pairs/{pair_id}/history")
def get_pair_history(pair_id: str):
    db = _db()
    sessions_resp = db.table("sessions").select("*").eq("pair_id", pair_id).execute()
    ratings_resp = db.table("ratings").select("*").eq("pair_id", pair_id).execute()
    return {
        "sessions": sessions_resp.data or [],
        "ratings": ratings_resp.data or [],
    }
