-- Movie Match schema
-- NOTE ON SECURITY MODEL: This MVP has no user auth/login. Access control is
-- entirely based on knowledge of a session_id / pair_id (i.e. the same trust
-- model as a shareable link). RLS is enabled on every table but policies are
-- intentionally permissive (allow all for anon) since there is no concept of
-- a logged-in user to scope rows to. Do not treat this as a template for an
-- app that needs real per-user data isolation.

create extension if not exists "pgcrypto";

create table if not exists pairs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now()
);

create table if not exists sessions (
  id uuid primary key default gen_random_uuid(),
  pair_id uuid references pairs(id),
  status text not null default 'waiting_b',
  round int not null default 1,
  created_at timestamptz default now()
);

create table if not exists preferences (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions(id),
  partner text check (partner in ('A','B')),
  device_id text,
  moods text[],
  mood_text text,
  languages text[],
  content_type text,
  min_rating int,
  eras text[],
  created_at timestamptz default now()
);

create table if not exists title_pool (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions(id),
  round int,
  tmdb_id int,
  media_type text,
  title text,
  year int,
  imdb_rating numeric,
  runtime int,
  synopsis text,
  poster_url text
);

create table if not exists swipes (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions(id),
  partner text,
  tmdb_id int,
  round int,
  direction text check (direction in ('left','right')),
  created_at timestamptz default now()
);

create table if not exists matches (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions(id),
  tmdb_id int,
  round int,
  ott_platforms jsonb,
  created_at timestamptz default now()
);

create table if not exists ratings (
  id uuid primary key default gen_random_uuid(),
  pair_id uuid references pairs(id),
  tmdb_id int,
  partner text,
  rating int,
  created_at timestamptz default now()
);

alter table pairs enable row level security;
alter table sessions enable row level security;
alter table preferences enable row level security;
alter table title_pool enable row level security;
alter table swipes enable row level security;
alter table matches enable row level security;
alter table ratings enable row level security;

create policy "allow all" on pairs for all using (true) with check (true);
create policy "allow all" on sessions for all using (true) with check (true);
create policy "allow all" on preferences for all using (true) with check (true);
create policy "allow all" on title_pool for all using (true) with check (true);
create policy "allow all" on swipes for all using (true) with check (true);
create policy "allow all" on matches for all using (true) with check (true);
create policy "allow all" on ratings for all using (true) with check (true);

-- Required for the frontend's Supabase Realtime subscriptions (session status,
-- swipe, and match live updates) to receive postgres_changes events.
alter publication supabase_realtime add table sessions, swipes, matches;
