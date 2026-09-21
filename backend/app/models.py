from typing import Optional, List
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    pair_id: Optional[str] = None


class PreferencesRequest(BaseModel):
    partner: str  # 'A' | 'B'
    moods: List[str] = []
    mood_text: str = ""
    languages: List[str] = []
    content_type: str = "Movies only"
    min_rating: int = 6
    eras: List[str] = []
    device_id: str


class SwipeRequest(BaseModel):
    partner: str
    tmdb_id: int
    round: int
    direction: str  # 'left' | 'right'
    device_id: str


class FinalizeRequest(BaseModel):
    tmdb_id: int


class RatingRequest(BaseModel):
    pair_id: str
    tmdb_id: int
    partner: str
    rating: int
