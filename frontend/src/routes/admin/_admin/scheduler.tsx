import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Clock, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { JobStatusBadge } from "@/components/scheduler-status";
import { initFromSchema, SchemaFields } from "@/components/schema-form";
import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  apiErrorMessage,
  createAdminSchedulerJob,
  getAdminSchedulerJobs,
  getAdminSchedulerJobTypes,
  type SchedulerJob,
  type SchedulerJobType,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/scheduler")({
  component: SchedulerPage,
});

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

const EMPTY_FORM = {
  name: "",
  job_type: "",
  scheduled_at: "",
  is_active: true,
  params: {} as Record<string, unknown>,
};

function CreateJobDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const { data: jobTypes = [] } = useQuery({
    queryKey: ["admin", "scheduler", "types"],
    queryFn: getAdminSchedulerJobTypes,
    enabled: open,
  });

  const selectedType: SchedulerJobType | undefined = jobTypes.find(
    (jt) => jt.type_name === form.job_type,
  );

  function handleTypeChange(typeName: string) {
    const jt = jobTypes.find((j) => j.type_name === typeName);
    setForm((f) => ({
      ...f,
      job_type: typeName,
      params: jt ? initFromSchema(jt.create_schema) : {},
    }));
  }

  const mutation = useMutation({
    mutationFn: createAdminSchedulerJob,
    onSuccess: () => {
      toast.success(t("admin.scheduler.created", { defaultValue: "Job created" }));
      setOpen(false);
      setForm(EMPTY_FORM);
      onCreated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.scheduler.create_error", {
            defaultValue: "Failed to create job",
          }),
        ),
      ),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.job_type || !form.scheduled_at) return;
    mutation.mutate(form);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.scheduler.create", { defaultValue: "New job" })}
          </Button>
        }
      />
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("admin.scheduler.create", { defaultValue: "New job" })}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="job-name">
              {t("admin.scheduler.field_name", { defaultValue: "Name" })}
            </Label>
            <Input
              id="job-name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t("admin.scheduler.name_placeholder", {
                defaultValue: "e.g. Open challenges at midnight",
              })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="job-type">
              {t("admin.scheduler.field_type", { defaultValue: "Job type" })}
            </Label>
            <select
              id="job-type"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={form.job_type}
              onChange={(e) => handleTypeChange(e.target.value)}
              required
            >
              <option value="">
                {t("admin.scheduler.type_placeholder", {
                  defaultValue: "Select a job type…",
                })}
              </option>
              {jobTypes.map((jt) => (
                <option key={jt.type_name} value={jt.type_name}>
                  {jt.type_name}
                </option>
              ))}
            </select>
          </div>

          <DateTimePicker
            label={t("admin.scheduler.field_scheduled_at", {
              defaultValue: "Scheduled at",
            })}
            value={form.scheduled_at}
            onChange={(utcIso) => setForm((f) => ({ ...f, scheduled_at: utcIso }))}
            required
          />

          <div className="flex items-center justify-between rounded-lg border px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">
                {t("admin.scheduler.field_active", { defaultValue: "Active" })}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("admin.scheduler.active_hint", {
                  defaultValue: "Enable the job to fire at the scheduled time",
                })}
              </p>
            </div>
            <Switch
              checked={form.is_active}
              onCheckedChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
            />
          </div>

          {selectedType && (
            <div className="space-y-1.5">
              <p className="text-sm font-medium">
                {t("admin.scheduler.field_params", {
                  defaultValue: "Parameters",
                })}
              </p>
              <div className="rounded-lg border p-3 space-y-4">
                <SchemaFields
                  schema={selectedType.create_schema}
                  values={form.params}
                  onChange={(key, val) =>
                    setForm((f) => ({
                      ...f,
                      params: { ...f.params, [key]: val },
                    }))
                  }
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending || !form.job_type || !form.scheduled_at}
            >
              {mutation.isPending
                ? t("common.saving", { defaultValue: "Saving…" })
                : t("common.save", { defaultValue: "Save" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const COLUMNS: Column<SchedulerJob>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (j) => <IdCell id={j.id} />,
    className: "w-32",
  },
  {
    key: "name",
    header: "Name",
    cell: (j) => <span className="font-medium">{j.name}</span>,
  },
  {
    key: "job_type",
    header: "Type",
    cell: (j) => (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
        <Clock className="size-3" />
        {j.job_type}
      </span>
    ),
  },
  {
    key: "scheduled_at",
    header: "Scheduled at",
    sortable: true,
    cell: (j) => (
      <span className="text-sm tabular-nums">{new Date(j.scheduled_at).toLocaleString()}</span>
    ),
  },
  {
    key: "is_active",
    header: "Status",
    cell: (j) => <JobStatusBadge job={j} />,
  },
  {
    key: "last_run",
    header: "Last run",
    cell: (j) =>
      j.last_run ? (
        <span className="text-sm tabular-nums text-muted-foreground">
          {new Date(j.last_run).toLocaleString()}
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function SchedulerPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "scheduler", "jobs", table.queryString],
    queryFn: () => getAdminSchedulerJobs(table.queryString),
    placeholderData: (prev) => prev,
  });

  function handleCreated() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "scheduler", "jobs"],
    });
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          {t("admin.nav.scheduler", { defaultValue: "Scheduler" })}
        </h1>
        <CreateJobDialog onCreated={handleCreated} />
      </div>

      <DataTable
        columns={COLUMNS}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(j) => j.id}
        onRefresh={() => void refetch()}
        onRowClick={(j) =>
          void navigate({
            to: "/admin/scheduler/$jobId",
            params: { jobId: j.id },
          })
        }
      />
    </div>
  );
}
