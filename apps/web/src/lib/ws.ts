import { useEffect, useRef, useState } from "react";
import type { AxisScore } from "./types";

interface UseLiveFeedOpts {
  url: string;
  enabled?: boolean;
  max?: number;
}

export interface LiveEvent {
  type: "check";
  id: string;
  prompt_version: string;
  flagged: boolean;
  created_at: string;
  output_text: string;
  axes: AxisScore[];
}

export function useLiveFeed({ url, enabled = true, max = 50 }: UseLiveFeedOpts) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = (msg) => {
      if (!alive) return;
      try {
        const data = JSON.parse(msg.data) as LiveEvent;
        if (data.type === "check") {
          setEvents((prev) => [data, ...prev].slice(0, max));
        }
      } catch {
        // ignore non-json frames (heartbeats etc.)
      }
    };
    ws.onopen = () => {
      ws.send("hello");
    };
    return () => {
      alive = false;
      ws.close();
    };
  }, [url, enabled, max]);

  return { events };
}
