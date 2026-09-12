import type { ReactNode } from "react";

/** Standard header for admin list pages: nav icon, title, right-aligned actions. */
export function PageHeader({
  icon: Icon,
  title,
  badge,
  actions,
}: {
  icon: React.ElementType;
  title: string;
  /** Rendered right after the title, e.g. a beta marker. */
  badge?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <Icon className="size-6 shrink-0 text-muted-foreground" />
        <h1 className="text-2xl font-bold">{title}</h1>
        {badge}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  );
}
