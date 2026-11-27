import { useEffect, useState } from "react";

/** Index into *count* items, from 0 at mount, advancing every *periodMs*; 0 turns it off. */
export function useCycle(count: number, periodMs: number): number {
  const [startedAt] = useState(Date.now);
  const [now, setNow] = useState(startedAt);

  useEffect(() => {
    if (periodMs <= 0) return;
    const timer = setInterval(() => setNow(Date.now()), periodMs);
    return () => clearInterval(timer);
  }, [periodMs]);

  if (periodMs <= 0 || count <= 0) return 0;
  return Math.floor((now - startedAt) / periodMs) % count;
}
