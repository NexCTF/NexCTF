import type { SchedulerJob, SchedulerTask } from "@/lib/api";
import { cn } from "@/lib/utils";

const PILL = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";

export function jobStatus(job: SchedulerJob): "scheduled" | "completed" | "disabled" {
  if (job.is_active) return "scheduled";
  // A recurring job that is off was disabled, never "completed".
  if (job.last_run && !job.cron_expression) return "completed";
  return "disabled";
}

const STATUS_STYLES = {
  scheduled: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  completed: "bg-green-500/10 text-green-600 dark:text-green-400",
  disabled: "bg-muted text-muted-foreground",
} as const;

const TASK_STATUS_STYLES = {
  pending: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  success: "bg-green-500/10 text-green-600 dark:text-green-400",
  failed: "bg-red-500/10 text-red-600 dark:text-red-400",
} as const;

export function JobStatusBadge({ job }: { job: SchedulerJob }) {
  const s = jobStatus(job);
  return <span className={cn(PILL, STATUS_STYLES[s])}>{s}</span>;
}

export function TaskStatusBadge({ status }: { status: SchedulerTask["status"] }) {
  return <span className={cn(PILL, TASK_STATUS_STYLES[status])}>{status}</span>;
}
