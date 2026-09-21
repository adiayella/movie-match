"""LLM brief-generation service.

Named claude_service for historical reasons but backed by Google's Gemini API
(the project switched providers after initial scaffolding). Function names/
signatures are unchanged so callers in main.py didn't need to change.
"""

import json
import os
from typing import Optional

from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-flash-latest"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def _call_llm(prompt: str) -> dict:
    client = _get_client()
    resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    raw = resp.text or ""
    try:
        return _extract_json(raw)
    except (ValueError, json.JSONDecodeError):
        retry_prompt = (
            prompt
            + "\n\nYour previous response could not be parsed as JSON. "
            "Respond again with ONLY a single valid JSON object, no markdown "
            "fences, no commentary, no leading or trailing text."
        )
        resp2 = client.models.generate_content(model=MODEL_NAME, contents=retry_prompt)
        raw2 = resp2.text or ""
        return _extract_json(raw2)


SCHEMA_HINT = (
    '{"genres": ["Comedy","Romance"], "tone_keywords": ["witty","warm","low-stakes"], '
    '"languages_iso": ["hi","en"], "year_min": 2015, "year_max": 2026, '
    '"media_types": ["movie","tv"], "avoid": ["gore","tragic-endings"]}'
)


def build_search_brief(profile_a: dict, profile_b: dict, history: Optional[list] = None) -> dict:
    history_block = ""
    if history:
        history_block = f"\nHere is what this couple has watched/rated before (use it to inform taste, e.g. avoid repeats they disliked, lean into genres they enjoyed):\n{json.dumps(history)}\n"

    prompt = f"""You are helping a couple decide what to watch tonight. Partner A and Partner B each filled out an independent preference form. Combine their inputs into a single search brief that a movie/TV recommendation engine can use.

Partner A profile:
{json.dumps(profile_a)}

Partner B profile:
{json.dumps(profile_b)}
{history_block}
Output ONLY a single JSON object with exactly this shape (no markdown fences, no commentary):
{SCHEMA_HINT}

Guidance:
- genres: reconcile both partners' moods/genres into a shared set that would satisfy both.
- tone_keywords: short adjectives capturing the vibe, informed by any free-text mood descriptions.
- languages_iso: ISO 639-1 codes from the union/intersection of both partners' language preferences (prefer intersection, fall back to union if no overlap).
- year_min/year_max: derived from era preferences.
- media_types: subset of ["movie","tv"].
- avoid: things to steer away from based on either partner's stated dislikes or mood.
"""
    return _call_llm(prompt)


def refine_from_swipes(brief: dict, liked_titles: list) -> dict:
    prompt = f"""A couple has been swiping on movie/TV recommendations. Here is the original search brief:
{json.dumps(brief)}

Here are the titles they both swiped right on (liked) in the first round, with genre/tone info:
{json.dumps(liked_titles)}

Produce a refined search brief for a second round of recommendations, weighted toward what they actually liked. Output ONLY a single JSON object with exactly this shape (no markdown fences, no commentary):
{SCHEMA_HINT}
"""
    return _call_llm(prompt)
