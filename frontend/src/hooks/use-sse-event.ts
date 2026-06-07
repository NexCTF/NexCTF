import { useEffect } from "react";
import { addSSEListener } from "@/lib/sse";

/**
 * Subscribe to a typed SSE event for the lifetime of the component.
 *
 * @example
 * useSSEEvent<Notification>("notification", (data) => {
 *   queryClient.invalidateQueries({ queryKey: ["notifications"] });
 * });
 */
export function useSSEEvent<T = unknown>(eventType: string, handler: (data: T) => void) {
  // biome-ignore lint/correctness/useExhaustiveDependencies: handler excluded intentionally — callers should memoize
  useEffect(() => {
    return addSSEListener<T>(eventType, handler);
  }, [eventType]);
}
