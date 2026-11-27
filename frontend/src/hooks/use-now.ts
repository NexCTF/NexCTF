import { useEffect, useState } from "react";

/** The value of *read*, re-read every *intervalMs*. */
export function useNow(intervalMs: number, read: () => number = Date.now): number {
  const [now, setNow] = useState(read);

  useEffect(() => {
    const timer = setInterval(() => setNow(read()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, read]);

  return now;
}
