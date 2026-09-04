import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Play, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CronInput } from "@/components/cron-input";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { DetailPageShell, DetailSection, InfoRow } from "@/components/detail-page";
import { IdCell } from "@/components/id-cell";
import { JobStatusBadge, TaskStatusBadge } from "@/components/scheduler-status";
import { SchemaFields } from "@/components/schema-form";
import { DateCell, EmptyCell } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  deleteAdminSchedulerJob,
  getAdminSchedulerJob,
  getAdminSchedulerJobTasks,
  getAdminSchedulerJobTypes,
  runAdminSchedulerJob,
  type SchedulerTask,
  updateAdminSchedulerJob,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/scheduler_/$jobId")({
  component: SchedulerJobDetailPage,
});

function SchedulerJobDetailPage() {
  const { t } = useTranslation();

  const scheduleLabel = (cron: string | null) =>
    cron?.trim()
      ? t("admin.scheduler.field_next_run", { defaultValue: "Next run" })
      : t("admin.scheduler.field_scheduled_at", { defaultValue: "Scheduled at" });
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
  });

  const updateSchema = jobTypes.find((jt) => jt.type_name === job?.job_type)?.update_schema;

  function refreshJob() {
    for (const queryKey of [
      ["admin", "scheduler", "job", jobId],
      ["admin", "scheduler", "jobs"],
      ["admin", "scheduler", "tasks", jobId],
    ]) {
      void queryClient.invalidateQueries({ queryKey });
    }
  }

  const taskTable = useTableState();
  const {
    data: tasks,
    isLoading: tasksLoading,
    isFetching: tasksFetching,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ["admin", "scheduler", "tasks", jobId, taskTable.queryString],
    queryFn: () => getAdminSchedulerJobTasks(jobId, taskTable.queryString),
    placeholderData: (prev) => prev,
  });

  const taskColumns: Column<SchedulerTask>[] = [
    {
      key: "status",
      header: t("admin.scheduler.col_task_status", { defaultValue: "Status" }),
      cell: (task) => <TaskStatusBadge status={task.status} />,
    },
    {
      key: "started_at",
      header: t("admin.scheduler.col_task_started", { defaultValue: "Started" }),
      sortable: true,
      cell: (task) => <DateCell value={task.started_at} />,
    },
    {
      key: "completed_at",
      header: t("admin.scheduler.col_task_completed", { defaultValue: "Completed" }),
      cell: (task) => <DateCell value={task.completed_at} />,
    },
    {
      key: "error",
      header: t("admin.scheduler.col_task_error", { defaultValue: "Error" }),
      cell: (task) =>
        task.error ? (
          <span className="text-destructive text-xs font-mono">{task.error}</span>
        ) : (
          <EmptyCell />
        ),
    },
  ];

  const [editForm, setEditForm] = useState<{
    name: string;
    scheduled_at: string;
    cron_expression: string;
    params: Record<string, unknown>;
  } | null>(null);

  function startEdit() {
    if (!job) return;
    setEditForm({
      name: job.name,
      scheduled_at: job.scheduled_at,
      cron_expression: job.cron_expression ?? "",
      params: { ...job.params },
    });
  }

  function cancelEdit() {
    setEditForm(null);
  }

  function dateEdited(): boolean {
    if (!editForm || !job) return false;
    return new Date(editForm.scheduled_at).getTime() !== new Date(job.scheduled_at).getTime();
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      updateAdminSchedulerJob(jobId, {
        name: editForm?.name,
        scheduled_at: dateEdited() ? editForm?.scheduled_at : undefined,
        cron_expression: editForm?.cron_expression.trim() || null,
        params: editForm?.params,
      }),
    onSuccess: () => {
      toast.success(t("admin.scheduler.saved", { defaultValue: "Job saved" }));
      cancelEdit();
      refreshJob();
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
      refreshJob();
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
      refreshJob();
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
            <ConfirmDialog
              description={t("admin.scheduler.delete_confirm", {
                name: job?.name ?? "",
                defaultValue: 'Delete job "{{name}}"?',
              })}
              confirmLabel={t("common.delete", { defaultValue: "Delete" })}
              onConfirm={() => deleteMutation.mutate()}
              trigger={
                <Button size="sm" variant="destructive" disabled={deleteMutation.isPending}>
                  <Trash2 className="size-3.5" />
                  {t("common.delete", { defaultValue: "Delete" })}
                </Button>
              }
            />
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
                  value={<DateCell value={job.last_run} />}
                />
                <InfoRow
                  label={t("admin.scheduler.field_created_at", {
                    defaultValue: "Created at",
                  })}
                  value={<DateCell value={job.created_at} />}
                />
              </div>

              {/* Editable fields */}
              {editForm !== null ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-name">
                      {t("admin.scheduler.field_name", {
                        defaultValue: "Name",
                      })}
                    </Label>
                    <Input
                      id="edit-name"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      required
                    />
                  </div>

                  <DateTimePicker
                    label={scheduleLabel(editForm.cron_expression)}
                    value={editForm.scheduled_at}
                    onChange={(v) => setEditForm({ ...editForm, scheduled_at: v })}
                    required
                  />

                  <CronInput
                    id="edit-cron"
                    value={editForm.cron_expression}
                    onChange={(v) => setEditForm({ ...editForm, cron_expression: v })}
                  />

                  {updateSchema && (
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
                            setEditForm({
                              ...editForm,
                              params: { ...editForm.params, [key]: val },
                            })
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
                        ? t("common.saving")
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
                    label={scheduleLabel(job.cron_expression)}
                    value={<DateCell value={job.scheduled_at} />}
                  />
                  <InfoRow
                    label={t("admin.scheduler.field_cron", {
                      defaultValue: "Repeat (cron)",
                    })}
                    value={
                      job.cron_expression ? (
                        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                          {job.cron_expression}
                        </code>
                      ) : (
                        <EmptyCell />
                      )
                    }
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
                      {t("common.edit", { defaultValue: "Edit" })}
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
            <DataTable
              columns={taskColumns}
              response={tasks}
              table={taskTable}
              isLoading={tasksLoading}
              isFetching={tasksFetching}
              rowKey={(task) => task.id}
              onRefresh={() => void refetchTasks()}
            />
          </DetailSection>
        </>
      )}
    </DetailPageShell>
  );
}
