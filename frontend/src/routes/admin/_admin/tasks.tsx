import { createFileRoute } from "@tanstack/react-router";
import { ExternalLink, ListTodo, RefreshCw } from "lucide-react";
import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

/** The pgqueuer dashboard the backend serves to admins. */
const TASK_DASHBOARD_URL = "/api/admin/tasks/";
/** The storage key the dashboard reads its theme from before first paint. */
const DASHBOARD_THEME_KEY = "pgq-theme";

type DashboardWindow = Window & { pgqSetTheme?: (theme: string) => void };

export const Route = createFileRoute("/admin/_admin/tasks")({
  validateSearch: (search: Record<string, unknown>): { job?: number } => ({
    job: Number.isSafeInteger(search.job) ? (search.job as number) : undefined,
  }),
  component: TasksPage,
});

/** The framed dashboard, shown in the admin's theme on every page it loads. */
function useDashboardFrame() {
  const { resolvedTheme } = useTheme();
  const frame = useRef<HTMLIFrameElement>(null);

  useLayoutEffect(() => {
    localStorage.setItem(DASHBOARD_THEME_KEY, resolvedTheme);
    (frame.current?.contentWindow as DashboardWindow | null)?.pgqSetTheme?.(resolvedTheme);
  }, [resolvedTheme]);

  const reload = () => frame.current?.contentWindow?.location.reload();

  return { frameProps: { ref: frame }, reload };
}

function TasksPage() {
  const { t } = useTranslation();
  const { job } = Route.useSearch();
  const { frameProps, reload } = useDashboardFrame();
  const src = job === undefined ? TASK_DASHBOARD_URL : `${TASK_DASHBOARD_URL}jobs/${job}`;
  const title = t("admin.nav.tasks", { defaultValue: "Task queue" });

  return (
    <div className="flex flex-1 flex-col gap-6 p-8">
      <PageHeader
        icon={ListTodo}
        title={title}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={reload}>
              <RefreshCw />
              {t("admin.tasks.refresh", { defaultValue: "Refresh" })}
            </Button>
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink />
              {t("admin.tasks.open_in_new_tab", { defaultValue: "Open in new tab" })}
            </a>
          </div>
        }
      />
      <iframe
        {...frameProps}
        src={src}
        title={title}
        className="min-h-[36rem] w-full flex-1 rounded-md border bg-background"
      />
    </div>
  );
}
