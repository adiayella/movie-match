import os
import random
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOWED_ORIGINS == "*" else ALLOWED_ORIGINS.split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db():
    return get_client()


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

    db.table("preferences").insert(
        {
            "session_id": session_id,
            "partner": body.partner,
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

    if {"A", "B"} <= partners_present:
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

        brief = claude_service.build_search_brief(profile_a, profile_b, history)

        content_type = profile_a.get("content_type") or profile_b.get("content_type")
        min_rating = max(
            profile_a.get("min_rating") or 6, profile_b.get("min_rating") or 6
        )

        titles = tmdb_service.discover_titles(brief, content_type, min_rating)

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
        if rows:
            db.table("title_pool").insert(rows).execute()

        db.table("sessions").update({"status": "swiping"}).eq(
            "id", session_id
        ).execute()
        session["status"] = "swiping"

    return {"status": session["status"]}


@app.get("/sessions/{session_id}")
def get_session(session_id: str, partner: str = Query(...)):
    db = _db()
    session_resp = db.table("sessions").select("*").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session not found")
    session = session_resp.data[0]

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

    return {"session": session, "pool": pool}


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

    db.table("swipes").insert(
        {
            "session_id": session_id,
            "partner": body.partner,
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
            and s["partner"] != body.partner
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
