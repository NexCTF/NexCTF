import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarDays } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { useSSEEvent } from "@/hooks/use-sse-event";
import { type AdminEvent, getAdminEvents } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/events")({
  component: EventsPage,
});

export const EVENT_TYPE_COLORS: Record<string, string> = {
  "user.register": "bg-green-500/10 text-green-600 dark:text-green-400",
  "user.login": "bg-blue-500/10 text-blue-600 dark:text-blue-400",
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
    key: "team_name",
    header: "Team",
    sortable: true,
    cell: (e) =>
      e.team_id ? (
        <span className="text-muted-foreground">{e.team_name ?? e.team_id}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    key: "challenge_title",
    header: "Challenge",
    sortable: false,
    cell: (e) =>
      e.challenge_id ? (
        <span className="text-muted-foreground">{e.challenge_title ?? e.challenge_id}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    key: "meta",
    header: "Details",
    sortable: false,
    cell: (e) => {
      const entries = Object.entries(e.meta).filter(([k]) => !["challenge_title"].includes(k));
      if (entries.length === 0) return <span className="text-muted-foreground">—</span>;
      return (
        <span className="text-xs text-muted-foreground font-mono">
          {entries.map(([k, v]) => `${k}: ${v}`).join(" · ")}
        </span>
      );
    },
  },
];

function EventsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();

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
      />
    </div>
  );
}
