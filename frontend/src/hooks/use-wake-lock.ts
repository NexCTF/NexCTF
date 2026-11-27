import { useEffect } from "react";

/** Keep the screen awake while the component is mounted, where the browser allows it. */
export function useWakeLock(): void {
  useEffect(() => {
    if (!("wakeLock" in navigator)) return;
    let sentinel: WakeLockSentinel | null = null;
    let disposed = false;

    const acquire = async () => {
      if (document.visibilityState !== "visible" || (sentinel && !sentinel.released)) return;
      try {
        const lock = await navigator.wakeLock.request("screen");
        if (disposed) void lock.release();
        else sentinel = lock;
      } catch {
        // Refused (no user activation, battery saver, insecure origin): the screen may sleep.
      }
    };

    const onVisibilityChange = () => void acquire();
    void acquire();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      void sentinel?.release();
    };
  }, []);
}
