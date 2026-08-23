import { useTranslation } from "react-i18next";
import type { Column } from "@/components/data-table";
import { DateCell, EmptyCell, idColumn, TargetCell, UserLink } from "@/components/table-cells";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { AdminEvent } from "@/lib/api";

const EVENT_TYPE_COLORS: Record<string, string> = {
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
  "submission.trap": "bg-red-700/10 text-red-700 dark:text-red-300",
  "solution.timeout": "bg-orange-600/10 text-orange-700 dark:text-orange-400",
  "challenge.complete": "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  "hint.unlock": "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  "challenge.feedback": "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  "admin.user_created": "bg-green-600/10 text-green-700 dark:text-green-400",
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

export function useEventColumns(): Column<AdminEvent>[] {
  const { t } = useTranslation();
  return [
    idColumn<AdminEvent>(t),
    {
      key: "created_at",
      header: t("table.col_date", { defaultValue: "Date" }),
      sortable: true,
      cell: (e) => <DateCell value={e.created_at} />,
      className: "w-40",
    },
    {
      key: "event_type",
      header: t("table.col_type", { defaultValue: "Type" }),
      sortable: true,
      cell: (e) => <EventTypeBadge type={e.event_type} />,
      className: "w-44",
    },
    {
      key: "ip",
      header: t("table.col_ip", { defaultValue: "IP" }),
      sortable: false,
      cell: (e) =>
        e.ip ? (
          <code className="text-xs font-mono text-muted-foreground">{e.ip}</code>
        ) : (
          <EmptyCell />
        ),
      className: "w-36",
    },
    {
      key: "actor_username",
      header: t("table.col_user", { defaultValue: "User" }),
      sortable: true,
      cell: (e) => <UserLink id={e.actor_id} name={e.actor_username} />,
    },
    {
      key: "target_type",
      header: t("table.col_target", { defaultValue: "Target" }),
      sortable: true,
      cell: (e) => <TargetCell type={e.target_type} id={e.target_id} label={e.target_label} />,
    },
    {
      key: "meta",
      header: t("table.col_details", { defaultValue: "Details" }),
      sortable: false,
      cell: (e) => {
        const summary = formatMeta(e.meta).join(" · ");
        return summary ? (
          <span className="block truncate font-mono text-xs text-muted-foreground">{summary}</span>
        ) : (
          <EmptyCell />
        );
      },
      // w-full + max-w-0 lets this column absorb the leftover width and ellipsis
      // instead of widening the table.
      className: "w-full max-w-0",
    },
  ];
}

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

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 text-muted-foreground">{label}:</span>
      <span className="break-all">{value}</span>
    </div>
  );
}

export function EventDetailsDialog({
  event,
  onClose,
}: {
  event: AdminEvent | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
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
            <DetailRow
              label={t("table.col_date", { defaultValue: "Date" })}
              value={<DateCell value={event.created_at} />}
            />
            <DetailRow
              label={t("table.col_user", { defaultValue: "User" })}
              value={<UserLink id={event.actor_id} name={event.actor_username} />}
            />
            <DetailRow
              label={t("table.col_ip", { defaultValue: "IP" })}
              value={event.ip ?? <EmptyCell />}
            />
            <DetailRow
              label={t("table.col_target", { defaultValue: "Target" })}
              value={
                <TargetCell
                  type={event.target_type}
                  id={event.target_id}
                  label={event.target_label}
                />
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
