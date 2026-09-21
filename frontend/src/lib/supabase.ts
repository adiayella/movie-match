import { createClient, RealtimeChannel } from "@supabase/supabase-js";
import { useEffect, useRef, useState } from "react";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export interface SessionRealtimeState {
  status: string | null;
  round: number | null;
  lastEvent: "session" | "swipe" | "match" | null;
}

export function useSessionRealtime(sessionId: string | null): SessionRealtimeState {
  const [state, setState] = useState<SessionRealtimeState>({
    status: null,
    round: null,
    lastEvent: null,
  });
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!sessionId || !SUPABASE_URL) return;

    const channel = supabase
      .channel(`session-${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "sessions",
          filter: `id=eq.${sessionId}`,
        },
        (payload) => {
          const row = payload.new as { status?: string; round?: number };
          setState((prev) => ({
            status: row.status ?? prev.status,
            round: row.round ?? prev.round,
            lastEvent: "session",
          }));
        }
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "swipes",
          filter: `session_id=eq.${sessionId}`,
        },
        () => {
          setState((prev) => ({ ...prev, lastEvent: "swipe" }));
        }
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "matches",
          filter: `session_id=eq.${sessionId}`,
        },
        () => {
          setState((prev) => ({ ...prev, lastEvent: "match" }));
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [sessionId]);

  return state;
}
