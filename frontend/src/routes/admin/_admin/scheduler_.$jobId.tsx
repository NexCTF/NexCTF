import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Play, Trash2 } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DetailPageShell, DetailSection } from "@/components/detail-page";
import { IdCell } from "@/components/id-cell";
import { JobStatusBadge } from "@/components/scheduler-status";
import { SchemaFields } from "@/components/schema-form";
import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  deleteAdminSchedulerJob,
  getAdminSchedulerJob,
  getAdminSchedulerJobTypes,
  runAdminSchedulerJob,
  type SchedulerTask,
  updateAdminSchedulerJob,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/scheduler_/$jobId")({
  component: SchedulerJobDetailPage,
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 text-sm">
      <span className="w-36 shrink-0 text-muted-foreground">{label}</span>
      <span className="flex-1">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Task status badge
// ---------------------------------------------------------------------------

const TASK_STATUS_STYLES = {
  pending: "bg-yellow-500/10 text-yellow-600",
  success: "bg-green-500/10 text-green-600",
  failed: "bg-red-500/10 text-red-600",
} as const;

function TaskStatusBadge({ status }: { status: SchedulerTask["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        TASK_STATUS_STYLES[status],
      )}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function SchedulerJobDetailPage() {
  const { t } = useTranslation();
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: job, isLoading } = useQuery({
    queryKey: ["admin", "scheduler", "job", jobId],
    queryFn: () => getAdminSchedulerJob(jobId),
  });

  const { data: jobTypes = [] } = useQuery({
    queryKey: ["admin", "scheduler", "types"],
    queryFn: getAdminSchedulerJobTypes,
    enabled: !!job,
  });

  const updateSchema = jobTypes.find((jt) => jt.type_name === job?.job_type)?.update_schema;

  // biome-ignore lint/correctness/useExhaustiveDependencies: job?.tasks tracks only the tasks array
  const sortedTasks = useMemo(
    () =>
      job
        ? [...job.tasks].sort(
            (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
          )
        : [],
    [job?.tasks],
  );

  const [editForm, setEditForm] = useState<{
    name: string;
    scheduled_at: string;
    params: Record<string, unknown>;
  } | null>(null);

  const isEditing = editForm !== null;

  function startEdit() {
    if (!job) return;
    setEditForm({
      name: job.name,
      scheduled_at: job.scheduled_at,
      params: { ...job.params },
    });
  }

  function cancelEdit() {
    setEditForm(null);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      updateAdminSchedulerJob(jobId, {
        name: editForm?.name,
        scheduled_at: editForm?.scheduled_at,
        params: editForm?.params,
      }),
    onSuccess: () => {
      toast.success(t("admin.scheduler.saved", { defaultValue: "Job saved" }));
      cancelEdit();
      void queryClient.invalidateQueries({
        queryKey: ["admin", "scheduler", "job", jobId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "scheduler", "jobs"],
      });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.scheduler.save_error", {
            defaultValue: "Failed to save job",
          }),
        ),
      ),
  });

  const toggleMutation = useMutation({
    mutationFn: (is_active: boolean) => updateAdminSchedulerJob(jobId, { is_active }),
    onSuccess: (updated) => {
      toast.success(
        updated.is_active
          ? t("admin.scheduler.enabled", { defaultValue: "Job enabled" })
          : t("admin.scheduler.disabled", { defaultValue: "Job disabled" }),
      );
      void queryClient.invalidateQueries({
        queryKey: ["admin", "scheduler", "job", jobId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["admin", "scheduler", "jobs"],
      });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.scheduler.toggle_error", {
            defaultValue: "Failed to update job",
          }),
        ),
      ),
  });

  const runMutation = useMutation({
    mutationFn: () => runAdminSchedulerJob(jobId),
    onSuccess: (task) => {
      toast.success(
        task.status === "failed"
          ? t("admin.scheduler.run_failed", {
              defaultValue: "Execution failed",
            })
          : t("admin.scheduler.run_success", { defaultValue: "Job executed" }),
      );
      void queryClient.invalidateQueries({
        queryKey: ["admin", "scheduler", "job", jobId],
      });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.scheduler.run_error", { defaultValue: "Execution failed" })),
      ),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAdminSchedulerJob(jobId),
    onSuccess: () => {
      toast.success(t("admin.scheduler.deleted", { defaultValue: "Job deleted" }));
      void navigate({ to: "/admin/scheduler" });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.scheduler.delete_error", {
            defaultValue: "Failed to delete job",
          }),
        ),
      ),
  });

  function handleDeleteClick() {
    if (!job) return;
    if (
      !window.confirm(
        t("admin.scheduler.delete_confirm", {
          name: job.name,
          defaultValue: `Delete job "${job.name}"?`,
        }),
      )
    )
      return;
    deleteMutation.mutate();
  }

  if (!isLoading && !job) {
    return (
      <DetailPageShell
        backTo="/admin/scheduler"
        backLabel={t("admin.scheduler.detail_back", {
          defaultValue: "Back to Scheduler",
        })}
      >
        <p className="text-muted-foreground">
          {t("admin.scheduler.not_found", { defaultValue: "Job not found." })}
        </p>
      </DetailPageShell>
    );
  }

  return (
    <DetailPageShell
      backTo="/admin/scheduler"
      backLabel={t("admin.scheduler.detail_back", {
        defaultValue: "Back to Scheduler",
      })}
      title={job?.name}
      isLoading={isLoading}
      badge={job && <JobStatusBadge job={job} />}
      actions={
        job && (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => toggleMutation.mutate(!job.is_active)}
              disabled={toggleMutation.isPending}
            >
              {job.is_active
                ? t("admin.scheduler.disable_btn", { defaultValue: "Disable" })
                : t("admin.scheduler.enable_btn", { defaultValue: "Enable" })}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              <Play className="size-3.5" />
              {t("admin.scheduler.run", { defaultValue: "Run now" })}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleDeleteClick}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="size-3.5" />
              {t("common.delete", { defaultValue: "Delete" })}
            </Button>
          </div>
        )
      }
    >
      {job && (
        <>
          {/* Job info */}
          <DetailSection
            title={t("admin.scheduler.info_title", {
              defaultValue: "Job Info",
            })}
          >
            <div className="space-y-4">
              <div className="rounded-lg border divide-y">
                <InfoRow
                  label={t("admin.scheduler.field_id", { defaultValue: "ID" })}
                  value={<IdCell id={job.id} />}
                />
                <InfoRow
                  label={t("admin.scheduler.field_type", {
                    defaultValue: "Job type",
                  })}
                  value={
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{job.job_type}</code>
                  }
                />
                <InfoRow
                  label={t("admin.scheduler.col_last_run", {
                    defaultValue: "Last run",
                  })}
                  value={
                    job.last_run ? (
                      new Date(job.last_run).toLocaleString()
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )
                  }
                />
                <InfoRow
                  label={t("admin.scheduler.field_created_at", {
                    defaultValue: "Created at",
                  })}
                  value={new Date(job.created_at).toLocaleString()}
                />
              </div>

              {/* Editable fields */}
              {isEditing ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-name">
                      {t("admin.scheduler.field_name", {
                        defaultValue: "Name",
                      })}
                    </Label>
                    <Input
                      id="edit-name"
                      value={editForm?.name ?? ""}
                      onChange={(e) => setEditForm((f) => f && { ...f, name: e.target.value })}
                      required
                    />
                  </div>

                  <DateTimePicker
                    label={t("admin.scheduler.field_scheduled_at", {
                      defaultValue: "Scheduled at",
                    })}
                    value={editForm?.scheduled_at ?? ""}
                    onChange={(v) => setEditForm((f) => f && { ...f, scheduled_at: v })}
                    required
                  />

                  {updateSchema && editForm && (
                    <div className="space-y-1.5">
                      <p className="text-sm font-medium">
                        {t("admin.scheduler.field_params", {
                          defaultValue: "Parameters",
                        })}
                      </p>
                      <div className="space-y-4">
                        <SchemaFields
                          schema={updateSchema}
                          values={editForm.params}
                          onChange={(key, val) =>
                            setEditForm(
                              (f) =>
                                f && {
                                  ...f,
                                  params: { ...f.params, [key]: val },
                                },
                            )
                          }
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => saveMutation.mutate()}
                      disabled={saveMutation.isPending}
                    >
                      {saveMutation.isPending
                        ? t("common.saving", { defaultValue: "Saving…" })
                        : t("common.save", { defaultValue: "Save" })}
                    </Button>
                    <Button size="sm" variant="outline" onClick={cancelEdit}>
                      {t("common.cancel", { defaultValue: "Cancel" })}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border divide-y">
                  <InfoRow
                    label={t("admin.scheduler.field_name", {
                      defaultValue: "Name",
                    })}
                    value={job.name}
                  />
                  <InfoRow
                    label={t("admin.scheduler.field_scheduled_at", {
                      defaultValue: "Scheduled at",
                    })}
                    value={new Date(job.scheduled_at).toLocaleString()}
                  />
                  <InfoRow
                    label={t("admin.scheduler.field_params", {
                      defaultValue: "Parameters",
                    })}
                    value={
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                        {JSON.stringify(job.params, null, 2)}
                      </pre>
                    }
                  />
                  <div className="px-4 py-3">
                    <Button size="sm" variant="outline" onClick={startEdit}>
                      Edit
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </DetailSection>

          {/* Execution history */}
          <DetailSection
            title={t("admin.scheduler.tasks_title", {
              defaultValue: "Execution history",
            })}
          >
            {job.tasks.length === 0 ? (
              <p className="text-sm text-muted-foreground px-1">
                {t("admin.scheduler.tasks_empty", {
                  defaultValue: "No executions yet.",
                })}
              </p>
            ) : (
              <div className="rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                        {t("admin.scheduler.col_task_status", {
                          defaultValue: "Status",
                        })}
                      </th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                        {t("admin.scheduler.col_task_started", {
                          defaultValue: "Started",
                        })}
                      </th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                        {t("admin.scheduler.col_task_completed", {
                          defaultValue: "Completed",
                        })}
                      </th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                        {t("admin.scheduler.col_task_error", {
                          defaultValue: "Error",
                        })}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {sortedTasks.map((task) => (
                      <tr key={task.id}>
                        <td className="px-4 py-2.5">
                          <TaskStatusBadge status={task.status} />
                        </td>
                        <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                          {new Date(task.started_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                          {task.completed_at ? new Date(task.completed_at).toLocaleString() : "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          {task.error ? (
                            <span className="text-destructive text-xs font-mono">{task.error}</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </DetailSection>
        </>
      )}
    </DetailPageShell>
  );
}
