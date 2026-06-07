import { Popover } from "@base-ui/react/popover";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSSEEvent } from "@/hooks/use-sse-event";
import { getMyNotifications, markNotificationsRead, type Notification } from "@/lib/api";
import { cn } from "@/lib/utils";

export function NotificationPopover() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: getMyNotifications,
  });

  const notifications = data?.notifications ?? [];
  const lastReadAt = data?.last_read_at ? new Date(data.last_read_at) : null;
  const hasUnread = notifications.some(
    (n) => lastReadAt === null || new Date(n.created_at) > lastReadAt,
  );

  const handleNotificationEvent = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }, [queryClient]);

  useSSEEvent("notification", handleNotificationEvent);

  function handleOpenChange(isOpen: boolean) {
    setOpen(isOpen);
    if (isOpen && hasUnread) {
      void markNotificationsRead().then(() => {
        void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      });
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger
        className={cn(
          "relative inline-flex size-9 items-center justify-center rounded-md text-sm transition-colors outline-none",
          "hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring",
        )}
        title={t("nav.notifications", { defaultValue: "Notifications" })}
      >
        <Bell className="size-4" />
        {hasUnread && (
          <span className="absolute top-1.5 right-1.5 flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-500 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-red-500" />
          </span>
        )}
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Positioner className="z-50 w-80" side="bottom" align="end" sideOffset={8}>
          <Popover.Popup className="rounded-lg border bg-popover text-popover-foreground shadow-lg outline-none data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0 data-[closed]:zoom-out-95 data-[open]:zoom-in-95">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <p className="font-medium text-sm">
                {t("nav.notifications", { defaultValue: "Notifications" })}
              </p>
              {notifications.length > 0 && (
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {notifications.length}
                </span>
              )}
            </div>

            <div className="max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">
                  {t("notifications.empty", {
                    defaultValue: "No notifications",
                  })}
                </p>
              ) : (
                notifications.map((n) => (
                  <NotificationRow
                    key={n.id}
                    notification={n}
                    isUnread={lastReadAt === null || new Date(n.created_at) > lastReadAt}
                  />
                ))
              )}
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

function NotificationRow({
  notification: n,
  isUnread,
}: {
  notification: Notification;
  isUnread: boolean;
}) {
  const { i18n } = useTranslation();

  const date = new Date(n.created_at).toLocaleDateString(i18n.language, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={cn("border-b px-4 py-3 last:border-0", isUnread && "bg-muted/40")}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {isUnread && <span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-red-500" />}
          <p className="font-medium text-sm leading-snug">{n.title}</p>
        </div>
        <span className="shrink-0 text-[11px] text-muted-foreground">{date}</span>
      </div>
      <p className={cn("mt-1 text-sm leading-snug text-muted-foreground", isUnread && "pl-3")}>
        {n.content}
      </p>
    </div>
  );
}
