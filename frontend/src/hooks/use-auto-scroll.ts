import { type RefObject, useEffect } from "react";

/** Pause on the first rows before scrolling; also how often a list that fits is re-checked. */
const PAUSE_TOP_MS = 8_000;
/** Pause on the last rows before jumping back to the top. */
const PAUSE_BOTTOM_MS = 5_000;
/** Scrolling speed, in rows per second. */
const ROWS_PER_SECOND = 1;
/** Longest frame step, so a throttled or hidden tab does not jump to the bottom. */
const MAX_FRAME_MS = 100;

/**
 * Loop *content* through *viewport*: pause at the top, scroll down at a steady pace,
 * pause at the bottom, then jump back. Animation frames run only while scrolling.
 */
export function useAutoScroll(
  viewport: RefObject<HTMLElement | null>,
  content: RefObject<HTMLElement | null>,
  rowsPerScreen: number,
): void {
  useEffect(() => {
    const view = viewport.current;
    const list = content.current;
    if (!view || !list || typeof requestAnimationFrame === "undefined") return;

    let timer: ReturnType<typeof setTimeout> | undefined;
    let frame = 0;
    let offset = 0;
    const maxOffset = () => list.scrollHeight - view.clientHeight;
    const moveTo = (px: number) => {
      offset = px;
      list.style.transform = `translateY(${-px}px)`;
    };

    const scroll = () => {
      if (maxOffset() <= 0) return pauseAtTop();
      let last = performance.now();
      const step = (now: number) => {
        const elapsed = Math.min(now - last, MAX_FRAME_MS);
        last = now;
        const speed = (view.clientHeight / rowsPerScreen) * ROWS_PER_SECOND;
        moveTo(Math.min(maxOffset(), offset + (speed * elapsed) / 1000));
        if (offset >= maxOffset()) timer = setTimeout(pauseAtTop, PAUSE_BOTTOM_MS);
        else frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    };
    const pauseAtTop = () => {
      moveTo(0);
      timer = setTimeout(scroll, PAUSE_TOP_MS);
    };

    pauseAtTop();
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [viewport, content, rowsPerScreen]);
}
