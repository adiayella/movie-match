const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json() as Promise<T>;
}

export interface CreateSessionResponse {
  session_id: string;
  pair_id: string;
  join_url: string;
  qr_png_base64: string;
}

export interface TitleCard {
  id?: string;
  session_id?: string;
  round: number;
  tmdb_id: number;
  media_type: string;
  title: string;
  year: number | null;
  imdb_rating: number | null;
  runtime: number | null;
  synopsis: string | null;
  poster_url: string | null;
}

export interface SessionRow {
  id: string;
  pair_id: string;
  status: string;
  round: number;
  created_at: string;
}

export interface GetSessionResponse {
  session: SessionRow;
  pool: TitleCard[];
  match: (TitleCard & { ott_platforms: OttPlatform[] }) | null;
}

export interface SwipeResponse {
  matched?: boolean;
  waiting?: boolean;
  round_complete?: boolean;
  next_round?: number;
  final_choice?: boolean;
  top5?: (TitleCard & { score: number })[];
  tmdb_id?: number;
  ott_platforms?: OttPlatform[];
  title?: string;
  year?: number | null;
  poster_url?: string | null;
  synopsis?: string | null;
  [key: string]: unknown;
}

export interface OttPlatform {
  name: string;
  logo_url: string | null;
  deep_link: string | null;
}

export const api = {
  createSession: (pairId?: string | null) =>
    request<CreateSessionResponse>("/sessions", {
      method: "POST",
      body: JSON.stringify({ pair_id: pairId || undefined }),
    }),

  joinSession: (sessionId: string) =>
    request<SessionRow>(`/sessions/${sessionId}/join`, { method: "POST" }),

  submitPreferences: (
    sessionId: string,
    body: {
      partner: "A" | "B";
      moods: string[];
      mood_text: string;
      languages: string[];
      content_type: string;
      min_rating: number;
      eras: string[];
      device_id: string;
    }
  ) =>
    request<{ status: string; partner: "A" | "B" }>(`/sessions/${sessionId}/preferences`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getSession: (sessionId: string, partner: "A" | "B") =>
    request<GetSessionResponse>(
      `/sessions/${sessionId}?partner=${partner}`
    ),

  submitSwipe: (
    sessionId: string,
    body: {
      partner: "A" | "B";
      tmdb_id: number;
      round: number;
      direction: "left" | "right";
      device_id: string;
    }
  ) =>
    request<SwipeResponse>(`/sessions/${sessionId}/swipes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  finalize: (sessionId: string, tmdbId: number) =>
    request<SwipeResponse>(`/sessions/${sessionId}/finalize`, {
      method: "POST",
      body: JSON.stringify({ tmdb_id: tmdbId }),
    }),

  submitRating: (body: {
    pair_id: string;
    tmdb_id: number;
    partner: "A" | "B";
    rating: number;
  }) =>
    request<{ ok: boolean }>("/ratings", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getPairHistory: (pairId: string) =>
    request<{ sessions: SessionRow[]; ratings: unknown[] }>(
      `/pairs/${pairId}/history`
    ),
};
