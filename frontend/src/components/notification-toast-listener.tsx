import { useCallback } from "react";
import { toast } from "sonner";
import { useSSEEvent } from "@/hooks/use-sse-event";
import type { Notification } from "@/lib/api";

/**
 * Mounts no UI — just listens for SSE notification events and fires toasts.
 * Add this to any layout that should receive live notification alerts.
 */
export function NotificationToastListener() {
  const handler = useCallback((data: Notification) => {
    toast.info(data.title, { description: data.content });
  }, []);

  useSSEEvent("notification", handler);
  return null;
}
