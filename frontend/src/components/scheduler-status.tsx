import type { SchedulerJob } from "@/lib/api";
import { cn } from "@/lib/utils";

export function jobStatus(job: SchedulerJob): "scheduled" | "completed" | "disabled" {
  if (job.is_active) return "scheduled";
  if (job.last_run) return "completed";
  return "disabled";
}

export const STATUS_STYLES = {
  scheduled: "bg-blue-500/10 text-blue-600",
  completed: "bg-green-500/10 text-green-600",
  disabled: "bg-muted text-muted-foreground",
} as const;

export function JobStatusBadge({ job }: { job: SchedulerJob }) {
  const s = jobStatus(job);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[s],
      )}
    >
      {s}
    </span>
  );
}
