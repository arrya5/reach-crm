import { useEffect, useRef, useState } from "react";

// Polls an async fetcher on an interval. We use polling (not websockets) for
// live campaign stats — simplest thing that works for this scale; the README
// notes SSE/WebSockets as the at-scale upgrade.
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number, active = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saved = useRef(fetcher);
  saved.current = fetcher;

  useEffect(() => {
    if (!active) return;
    let alive = true;
    const tick = async () => {
      try {
        const d = await saved.current();
        if (alive) setData(d);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs, active]);

  return { data, error };
}
