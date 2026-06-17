import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useSSEEvent } from "@/hooks/use-sse-event";
import { type AdminEvent, getAdminEvents } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/events")({
  component: EventsPage,
});

export const EVENT_TYPE_COLORS: Record<string, string> = {
  "user.register": "bg-green-500/10 text-green-600 dark:text-green-400",
  "user.login": "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  "user.login_failed": "bg-red-600/10 text-red-700 dark:text-red-400",
  "user.logout": "bg-slate-500/10 text-slate-600 dark:text-slate-400",
  "user.totp_enabled": "bg-teal-500/10 text-teal-600 dark:text-teal-400",
  "user.totp_disabled": "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  "user.token_created": "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
  "user.token_revoked": "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  "submission.correct": "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  "submission.wrong": "bg-red-500/10 text-red-600 dark:text-red-400",
  "challenge.complete": "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  "hint.unlock": "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  "admin.user_updated": "bg-violet-500/10 text-violet-600 dark:text-violet-400",
  "admin.user_deleted": "bg-red-700/10 text-red-700 dark:text-red-400",
  "admin.submission_deleted": "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  "score_adjustment.created": "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  "score_adjustment.deleted": "bg-rose-700/10 text-rose-700 dark:text-rose-400",
};

function EventTypeBadge({ type }: { type: string }) {
  const cls = EVENT_TYPE_COLORS[type] ?? "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {type}
    </span>
  );
}

export const COLUMNS: Column<AdminEvent>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (e) => <IdCell id={e.id} />,
    className: "w-32",
  },
  {
    key: "created_at",
    header: "Time",
    sortable: true,
    cell: (e) => (
      <span className="text-muted-foreground text-xs whitespace-nowrap">
        {new Date(e.created_at).toLocaleString()}
      </span>
    ),
    className: "w-40",
  },
  {
    key: "event_type",
    header: "Type",
    sortable: true,
    cell: (e) => <EventTypeBadge type={e.event_type} />,
    className: "w-44",
  },
  {
    key: "ip",
    header: "IP",
    sortable: false,
    cell: (e) =>
      e.ip ? (
        <code className="text-xs font-mono text-muted-foreground">{e.ip}</code>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
    className: "w-36",
  },
  {
    key: "actor_username",
    header: "User",
    sortable: true,
    cell: (e) =>
      e.actor_id ? (
        <span className="font-medium">{e.actor_username ?? e.actor_id}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    key: "target_type",
    header: "Target",
    sortable: true,
    cell: (e) =>
      e.target_type ? (
        <span className="text-muted-foreground">
          {e.target_label ?? e.target_id}
          <span className="ml-1 text-xs opacity-60">({e.target_type})</span>
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    key: "meta",
    header: "Details",
    sortable: false,
    cell: (e) => {
      const summary = formatMeta(e.meta).join(" · ");
      return summary ? (
        <span className="block max-w-[28rem] truncate font-mono text-xs text-muted-foreground">
          {summary}
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    },
  },
];

// Flatten meta into display lines. `changes` holds a {field: [old, new]} diff,
// rendered as "field: old → new"; everything else as "key: value".
function formatMeta(meta: Record<string, unknown>): string[] {
  return Object.entries(meta).flatMap(([k, v]) => {
    if (k === "changes" && v && typeof v === "object") {
      return Object.entries(v as Record<string, unknown>).map(([field, pair]) =>
        Array.isArray(pair) ? `${field}: ${pair[0]} → ${pair[1]}` : `${field}: ${pair}`,
      );
    }
    return [`${k}: ${v}`];
  });
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 text-muted-foreground">{label}:</span>
      <span className="break-all">{value}</span>
    </div>
  );
}

function EventDetailsDialog({ event, onClose }: { event: AdminEvent | null; onClose: () => void }) {
  const parts = event ? formatMeta(event.meta) : [];
  return (
    <Dialog open={!!event} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            <EventTypeBadge type={event?.event_type ?? ""} />
          </DialogTitle>
        </DialogHeader>
        {event && (
          <div className="space-y-3 text-sm">
            <DetailRow label="Time" value={new Date(event.created_at).toLocaleString()} />
            <DetailRow
              label="User"
              value={event.actor_id ? (event.actor_username ?? event.actor_id) : "—"}
            />
            <DetailRow label="IP" value={event.ip ?? "—"} />
            <DetailRow
              label="Target"
              value={
                event.target_type
                  ? `${event.target_label ?? event.target_id} (${event.target_type})`
                  : "—"
              }
            />
            {parts.length > 0 && (
              <div className="space-y-1 rounded-md bg-muted p-3 font-mono text-xs break-all">
                {parts.map((part) => (
                  <div key={part}>{part}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function EventsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();
  const [selected, setSelected] = useState<AdminEvent | null>(null);

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "events", table.queryString],
    queryFn: () => getAdminEvents(table.queryString),
    placeholderData: (prev) => prev,
  });

  // Refresh when a new event arrives via SSE
  useSSEEvent("event", () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "events"] });
  });

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <CalendarDays className="size-6 text-muted-foreground" />
        <h1 className="text-2xl font-bold">{t("admin.nav.events", { defaultValue: "Events" })}</h1>
      </div>

      <DataTable
        columns={COLUMNS}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(e) => e.id}
        onRefresh={() => void refetch()}
        onRowClick={(e) => setSelected(e)}
      />

      <EventDetailsDialog event={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
