import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Clock, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CronInput } from "@/components/cron-input";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { JobStatusBadge } from "@/components/scheduler-status";
import { initFromSchema, SchemaFields } from "@/components/schema-form";
import { DateCell, idColumn } from "@/components/table-cells";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  cron_expression: "",
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

  const cron = form.cron_expression.trim();
  const canSubmit = !!form.job_type && (!!form.scheduled_at || !!cron);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !canSubmit) return;
    mutation.mutate({
      ...form,
      scheduled_at: form.scheduled_at || undefined,
      cron_expression: cron || null,
    });
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
            <Select value={form.job_type || null} onValueChange={(v) => handleTypeChange(v ?? "")}>
              <SelectTrigger id="job-type">
                <SelectValue
                  placeholder={t("admin.scheduler.type_placeholder", {
                    defaultValue: "Select a job type…",
                  })}
                />
              </SelectTrigger>
              <SelectContent>
                {jobTypes.map((jt) => (
                  <SelectItem key={jt.type_name} value={jt.type_name}>
                    {jt.type_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DateTimePicker
            label={
              cron
                ? t("admin.scheduler.field_first_run", {
                    defaultValue: "First run (optional)",
                  })
                : t("admin.scheduler.field_scheduled_at", {
                    defaultValue: "Scheduled at",
                  })
            }
            value={form.scheduled_at}
            onChange={(utcIso) => setForm((f) => ({ ...f, scheduled_at: utcIso }))}
            required={!cron}
          />

          <CronInput
            id="job-cron"
            value={form.cron_expression}
            onChange={(v) => setForm((f) => ({ ...f, cron_expression: v }))}
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
            <Button type="submit" disabled={mutation.isPending || !canSubmit}>
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

function SchedulerPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const table = useTableState();
  const columns: Column<SchedulerJob>[] = [
    idColumn<SchedulerJob>(t),
    {
      key: "name",
      header: t("table.col_name", { defaultValue: "Name" }),
      cell: (j) => <span className="font-medium">{j.name}</span>,
    },
    {
      key: "job_type",
      header: t("table.col_type", { defaultValue: "Type" }),
      cell: (j) => (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          <Clock className="size-3" />
          {j.job_type}
        </span>
      ),
    },
    {
      key: "scheduled_at",
      header: t("table.col_next_run", { defaultValue: "Next run" }),
      sortable: true,
      cell: (j) => (
        <div className="space-y-0.5">
          <DateCell value={j.scheduled_at} />
          {j.cron_expression && (
            <code className="block text-xs text-muted-foreground">{j.cron_expression}</code>
          )}
        </div>
      ),
    },
    {
      key: "is_active",
      header: t("table.col_status", { defaultValue: "Status" }),
      cell: (j) => <JobStatusBadge job={j} />,
    },
    {
      key: "last_run",
      header: t("table.col_last_run", { defaultValue: "Last run" }),
      cell: (j) => <DateCell value={j.last_run} />,
    },
  ];

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

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={Clock}
        title={t("admin.nav.scheduler", { defaultValue: "Scheduler" })}
        actions={
          <CreateJobDialog
            onCreated={() =>
              void queryClient.invalidateQueries({ queryKey: ["admin", "scheduler", "jobs"] })
            }
          />
        }
      />

      <DataTable
        columns={columns}
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
