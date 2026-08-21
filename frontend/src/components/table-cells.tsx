import { Link } from "@tanstack/react-router";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Column } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { cn } from "@/lib/utils";

type TFn = ReturnType<typeof useTranslation>["t"];

const RELATION_CLS =
  "inline-flex items-center gap-1 -mx-1.5 rounded px-1.5 py-0.5 text-sm font-medium text-primary underline-offset-2 hover:underline hover:bg-primary/10 transition-colors";

type RelationProps = { id: string | null | undefined; name?: string | null };

/** Placeholder for a missing value. */
export function EmptyCell() {
  return <span className="text-muted-foreground">—</span>;
}

/** Keep a click on an interactive cell from firing the row's own handler. */
export function stopRowClick(e: React.MouseEvent) {
  e.stopPropagation();
}

function relationLabel(name: string | null | undefined, id: string) {
  return name ?? id.split("-")[0];
}

/** A record can be named without being linkable — show the name, drop the link. */
function unlinkedRelation(name: string | null | undefined) {
  return name ? <span>{name}</span> : <EmptyCell />;
}

export function TeamLink({ id, name }: RelationProps) {
  if (!id) return unlinkedRelation(name);
  return (
    <Link
      to="/admin/teams/$teamId"
      params={{ teamId: id }}
      className={RELATION_CLS}
      onClick={stopRowClick}
    >
      {relationLabel(name, id)}
      <ArrowUpRight className="size-3 opacity-60" />
    </Link>
  );
}

export function UserLink({ id, name }: RelationProps) {
  if (!id) return unlinkedRelation(name);
  return (
    <Link
      to="/admin/users/$userId"
      params={{ userId: id }}
      className={RELATION_CLS}
      onClick={stopRowClick}
    >
      {relationLabel(name, id)}
      <ArrowUpRight className="size-3 opacity-60" />
    </Link>
  );
}

export function ChallengeLink({ id, name }: RelationProps) {
  if (!id) return unlinkedRelation(name);
  return (
    <Link
      to="/admin/challenges/$challengeId"
      params={{ challengeId: id }}
      className={RELATION_CLS}
      onClick={stopRowClick}
    >
      {relationLabel(name, id)}
      <ArrowUpRight className="size-3 opacity-60" />
    </Link>
  );
}

/** Event targets carry the owning table name, so the link varies per row. */
const TARGET_LINKS: Record<string, ((props: RelationProps) => React.ReactElement) | undefined> = {
  teams: TeamLink,
  users: UserLink,
  challenges: ChallengeLink,
};

export function TargetCell({
  type,
  id,
  label,
}: {
  type: string | null;
  id: string | null;
  label?: string | null;
}) {
  if (!type) return <EmptyCell />;
  const RelationLink = TARGET_LINKS[type];
  return (
    <span className="inline-flex items-center gap-1">
      {RelationLink && id ? (
        <RelationLink id={id} name={label} />
      ) : (
        <span className="text-muted-foreground">{label ?? id ?? "—"}</span>
      )}
      <span className="text-xs text-muted-foreground/60">({type})</span>
    </span>
  );
}

/** Enabled/disabled state: coloured dot plus its label. */
export function StatusCell({ active, label }: { active: boolean; label?: string }) {
  const { t } = useTranslation();
  const text =
    label ??
    (active
      ? t("table.status_active", { defaultValue: "Active" })
      : t("table.status_inactive", { defaultValue: "Inactive" }));
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs",
        active ? "text-green-600 dark:text-green-400" : "text-muted-foreground",
      )}
    >
      <span
        className={cn("size-1.5 rounded-full", active ? "bg-green-500" : "bg-muted-foreground/50")}
      />
      {text}
    </span>
  );
}

/** Plain yes/no attribute. */
export function BoolCell({ value }: { value: boolean }) {
  return (
    <span className={value ? "text-green-500" : "text-muted-foreground"}>{value ? "✓" : "✗"}</span>
  );
}

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: "short",
  timeStyle: "medium",
});

export function DateCell({ value }: { value: string | null | undefined }) {
  if (!value) return <EmptyCell />;
  return (
    <span className="text-muted-foreground text-xs whitespace-nowrap">
      {DATE_FORMAT.format(new Date(value))}
    </span>
  );
}

/** Right-aligned wrapper for the trailing action column. */
export function ActionsCell({ children }: { children: React.ReactNode }) {
  return <div className="flex justify-end gap-1">{children}</div>;
}

/** Signed number, green when positive and red when negative. */
export function SignedPoints({ amount }: { amount: number }) {
  return (
    <span
      className={cn(
        "tabular-nums",
        amount > 0 ? "text-green-500" : amount < 0 ? "text-red-500" : "text-muted-foreground",
      )}
    >
      {amount > 0 ? "+" : ""}
      {amount}
    </span>
  );
}

/** Highlights the admin role. */
export function RoleBadge({ role }: { role: string }) {
  const isAdmin = role === "admin";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        isAdmin ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
      )}
    >
      {isAdmin && <ShieldCheck className="size-3" />}
      {role}
    </span>
  );
}

/** The leading ID column every admin table opens with. */
export function idColumn<T extends { id: string }>(t: TFn): Column<T> {
  return {
    key: "id",
    header: t("table.col_id", { defaultValue: "ID" }),
    sortable: false,
    cell: (row) => <IdCell id={row.id} />,
    className: "w-32",
  };
}
