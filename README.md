# Movie Match

A movie/TV matchmaker for two. Both partners independently set their mood and
preferences, Claude turns those into a search brief, TMDB supplies candidate
titles, and both partners swipe through the same pool (shuffled independently)
until they land on a mutual match — then the app shows exactly where to
stream it in India right now. Sessions, swipes, and post-watch ratings persist
in Supabase so future movie nights get smarter about what the couple actually
enjoys.

## Stack

- **Backend**: Python + FastAPI (owns all secret-keyed calls to Claude, TMDB,
  and the RapidAPI streaming-availability API, plus match/round logic).
- **Frontend**: React + Vite + TypeScript, mobile-first, swipe deck built with
  `framer-motion`.
- **Data + realtime**: Supabase (Postgres). The backend writes with the
  service key; the frontend subscribes directly to Supabase Realtime with the
  anon key for live status updates (partner joined, match found, etc).

## Setup

### 1. Supabase

1. Create a new Supabase project.
2. Run `supabase/migrations/0001_init.sql` in the SQL editor (or via the
   Supabase CLI) to create the schema and RLS policies.
3. Grab your project URL, anon key, and service role key.

### 2. Backend

```bash
cd backend
cp .env.example .env   # fill in ANTHROPIC_API_KEY, TMDB_API_KEY, RAPIDAPI_KEY,
                        # RAPIDAPI_HOST, SUPABASE_URL, SUPABASE_SERVICE_KEY,
                        # PUBLIC_BASE_URL
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000` by default.

### 3. Frontend

```bash
cd frontend
cp .env.example .env   # fill in VITE_API_BASE_URL, VITE_SUPABASE_URL,
                        # VITE_SUPABASE_ANON_KEY
npm install
npm run dev
```

The app runs at `http://localhost:5173` by default.

## How a movie night works

1. Partner A opens the app and starts a session, gets a QR code / link.
2. Partner B scans/opens it on their own device and fills out their
   independent preference form (mood, languages, content type, min rating,
   era). Partner A does the same.
3. Once both have submitted, the backend asks Claude to build a shared search
   brief, pulls ~30 candidate titles from TMDB, and both partners start
   swiping through the same pool (independently shuffled).
4. First mutual right-swipe wins — the app immediately shows the match with
   Indian streaming platforms and deep links.
5. If round 1 finishes with no match, the backend refines the brief from what
   was liked and generates a second round. If round 2 also finishes with no
   match, both partners see a top-5 shortlist ranked by combined likes and
   pick one together.
6. After watching, either partner can leave a quick rating that feeds into
   future recommendations for the same pair.

## Security model note

This is an MVP with no user accounts/login. Access control is based entirely
on knowledge of a session/pair id (the same trust model as any shareable
link) — see the comment at the top of `supabase/migrations/0001_init.sql`.
Row Level Security is enabled on every table, but policies are intentionally
permissive (`for all using (true) with check (true)`) since there's no
authenticated user to scope rows to.

## Known gaps / things to double check

- TV show runtime is not populated (TMDB's TV endpoints don't have a single
  reliable per-episode runtime the way movies do); only movie runtimes are
  fetched.
- The RapidAPI Streaming Availability integration targets a fairly common
  endpoint shape (`GET /shows/{media_type}/{tmdb_id}?country=in`), but exact
  paths/response shapes vary by RapidAPI plan/version — `streaming_service.py`
  is written to fail soft (return `[]`) if the shape doesn't match, so a
  match is never blocked by streaming lookup issues, but you may need to
  adjust the request path/response parsing against your actual subscribed
  API version.
- CORS is wide open (`*`) for MVP simplicity — tighten `ALLOWED_ORIGINS` in
  the backend environment before any real deployment.
