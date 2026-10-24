import { Link, type LinkProps } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// DetailPageShell
// ---------------------------------------------------------------------------
// Provides the standard wrapper, back-link, header (title + optional badge +
// optional action area) and loading/not-found states for all admin detail
// pages. Use this as the outermost wrapper in every detail route.
//
// Usage:
//   <DetailPageShell
//     backTo="/admin/teams"
//     backLabel={t("admin.teams.detail_back")}
//     title={team.name}
//     isLoading={isLoading}
//   >
//     <DetailSection title="Members">…</DetailSection>
//   </DetailPageShell>
// ---------------------------------------------------------------------------

type DetailPageShellProps = {
  /** TanStack Router "to" path for the back link */
  backTo: LinkProps["to"];
  /** Text label shown next to the back arrow */
  backLabel: string;
  /** Main page title – shown as <h1> */
  title?: string;
  /** Optional badge/chip rendered right after the title */
  badge?: ReactNode;
  /** Optional buttons/actions aligned to the right of the header */
  actions?: ReactNode;
  /** When true shows a skeleton placeholder instead of children */
  isLoading?: boolean;
  children?: ReactNode;
};

export function DetailPageShell({
  backTo,
  backLabel,
  title,
  badge,
  actions,
  isLoading,
  children,
}: DetailPageShellProps) {
  if (isLoading) {
    return (
      <div className="p-4 sm:p-8 space-y-6">
        <div className="h-4 w-24 bg-muted animate-pulse rounded" />
        <div className="h-8 w-64 bg-muted animate-pulse rounded" />
        <div className="h-48 bg-muted animate-pulse rounded" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-8 space-y-6">
      {/* Header: back link + title + actions */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <Link
            to={backTo}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            {backLabel}
          </Link>
          {title && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h1 className="text-2xl font-bold break-words">{title}</h1>
              {badge}
            </div>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>

      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DetailSection
// ---------------------------------------------------------------------------
// A titled content block used inside DetailPageShell. Matches the style of
// the challenge detail info card and question sections.
// ---------------------------------------------------------------------------

type DetailSectionProps = {
  title: string;
  /** Optional element rendered right of the section title (e.g. a button) */
  actions?: ReactNode;
  children: ReactNode;
};

/** One label/value line inside a detail card. */
export function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:gap-4">
      <span className="shrink-0 text-muted-foreground sm:w-36">{label}</span>
      <span className="min-w-0 flex-1 break-words">{value}</span>
    </div>
  );
}

export function DetailSection({ title, actions, children }: DetailSectionProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}
