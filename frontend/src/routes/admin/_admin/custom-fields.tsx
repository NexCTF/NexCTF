import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ListChecks, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DeleteButton } from "@/components/confirm-dialog";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { ActionsCell, BoolCell, idColumn } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
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
  apiErrorMessage,
  type CustomFieldDefinition,
  createAdminCustomField,
  deleteAdminCustomField,
  getAdminCustomFields,
  updateAdminCustomField,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/custom-fields")({
  component: CustomFieldsPage,
});

type FieldType = CustomFieldDefinition["field_type"];
type FieldTarget = CustomFieldDefinition["target"];

const FIELD_TYPES: FieldType[] = ["string", "integer", "boolean", "url"];
const FIELD_TARGETS: FieldTarget[] = ["user", "team"];

interface FieldForm {
  name: string;
  label: string;
  field_type: FieldType;
  target: FieldTarget;
  is_required: boolean;
  is_public: boolean;
  is_self_editable: boolean;
  show_in_scoreboard: boolean;
}

const EMPTY_FORM: FieldForm = {
  name: "",
  label: "",
  field_type: "string",
  target: "user",
  is_required: false,
  is_public: true,
  is_self_editable: true,
  show_in_scoreboard: false,
};

function FieldFormFields({
  form,
  onChange,
  disableTarget,
}: {
  form: FieldForm;
  onChange: (patch: Partial<FieldForm>) => void;
  disableTarget?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>{t("admin.custom_fields.field_name")} *</Label>
          <Input
            value={form.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="school"
            required
          />
          <p className="text-xs text-muted-foreground">{t("admin.custom_fields.name_hint")}</p>
        </div>
        <div className="space-y-1.5">
          <Label>{t("admin.custom_fields.field_label")} *</Label>
          <Input
            value={form.label}
            onChange={(e) => onChange({ label: e.target.value })}
            placeholder="School"
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>{t("admin.custom_fields.field_type")}</Label>
          <select
            value={form.field_type}
            onChange={(e) => onChange({ field_type: e.target.value as FieldType })}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {FIELD_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label>{t("admin.custom_fields.field_target")}</Label>
          <select
            value={form.target}
            onChange={(e) => onChange({ target: e.target.value as FieldTarget })}
            disabled={disableTarget}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          >
            {FIELD_TARGETS.map((tgt) => (
              <option key={tgt} value={tgt}>
                {tgt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_required}
            onChange={(e) => onChange({ is_required: e.target.checked })}
            className="rounded border-input"
          />
          {t("admin.custom_fields.field_required")}
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => onChange({ is_public: e.target.checked })}
            className="rounded border-input"
          />
          {t("admin.custom_fields.field_public")}
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_self_editable}
            onChange={(e) => onChange({ is_self_editable: e.target.checked })}
            className="rounded border-input"
          />
          {t("admin.custom_fields.field_self_editable", { defaultValue: "Self-editable" })}
        </label>
        {form.target === "team" && (
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={form.show_in_scoreboard}
              onChange={(e) => onChange({ show_in_scoreboard: e.target.checked })}
              className="rounded border-input"
            />
            {t("admin.custom_fields.field_scoreboard")}
          </label>
        )}
      </div>
    </div>
  );
}

function CreateFieldDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FieldForm>(EMPTY_FORM);

  const mutation = useMutation({
    mutationFn: () => createAdminCustomField(form),
    onSuccess: () => {
      toast.success(t("admin.custom_fields.created"));
      setOpen(false);
      setForm(EMPTY_FORM);
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.custom_fields.create_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.custom_fields.create")}
          </Button>
        }
      />
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("admin.custom_fields.create")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <FieldFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditFieldDialog({
  field,
  onSaved,
}: {
  field: CustomFieldDefinition;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FieldForm>({
    name: field.name,
    label: field.label,
    field_type: field.field_type,
    target: field.target,
    is_required: field.is_required,
    is_public: field.is_public,
    is_self_editable: field.is_self_editable,
    show_in_scoreboard: field.show_in_scoreboard,
  });

  const mutation = useMutation({
    mutationFn: () =>
      updateAdminCustomField(field.id, {
        name: form.name,
        label: form.label,
        field_type: form.field_type,
        is_required: form.is_required,
        is_public: form.is_public,
        is_self_editable: form.is_self_editable,
        show_in_scoreboard: form.show_in_scoreboard,
      }),
    onSuccess: () => {
      toast.success(t("admin.custom_fields.saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.custom_fields.save_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="size-7">
            <Pencil className="size-3.5" />
          </Button>
        }
      />
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("admin.custom_fields.edit")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <FieldFormFields
            form={form}
            onChange={(p) => setForm((f) => ({ ...f, ...p }))}
            disableTarget
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CustomFieldsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "custom-fields", table.queryString],
    queryFn: () => getAdminCustomFields(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "custom-fields"],
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdminCustomField(id),
    onSuccess: () => {
      toast.success(t("admin.custom_fields.deleted"));
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.custom_fields.delete_error"))),
  });

  const columns: Column<CustomFieldDefinition>[] = [
    idColumn<CustomFieldDefinition>(t),
    {
      key: "name",
      header: t("admin.custom_fields.col_key", { defaultValue: "Key" }),
      cell: (f) => <span className="font-mono text-sm">{f.name}</span>,
    },
    {
      key: "label",
      header: t("admin.custom_fields.col_label"),
      cell: (f) => <span className="font-medium">{f.label}</span>,
    },
    {
      key: "target",
      header: t("admin.custom_fields.col_target"),
      cell: (f) => (
        <span className="capitalize rounded-full bg-muted px-2 py-0.5 text-xs">{f.target}</span>
      ),
    },
    {
      key: "field_type",
      header: t("table.col_type", { defaultValue: "Type" }),
      cell: (f) => <span className="font-mono text-xs text-muted-foreground">{f.field_type}</span>,
    },
    {
      key: "is_public",
      header: t("table.col_public", { defaultValue: "Public" }),
      cell: (f) => <BoolCell value={f.is_public} />,
    },
    {
      key: "is_self_editable",
      header: t("admin.custom_fields.field_self_editable"),
      cell: (f) => <BoolCell value={f.is_self_editable} />,
    },
    {
      key: "show_in_scoreboard",
      header: t("admin.custom_fields.col_scoreboard"),
      cell: (f) => <BoolCell value={f.show_in_scoreboard} />,
    },
    {
      key: "is_required",
      header: t("admin.custom_fields.col_required"),
      cell: (f) => <BoolCell value={f.is_required} />,
    },
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (f) => (
        <ActionsCell>
          <EditFieldDialog field={f} onSaved={invalidate} />
          <DeleteButton
            description={t("admin.custom_fields.delete_confirm", { name: f.label })}
            disabled={deleteMutation.isPending}
            onConfirm={() => deleteMutation.mutate(f.id)}
          />
        </ActionsCell>
      ),
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={ListChecks}
        title={t("admin.custom_fields.title")}
        actions={<CreateFieldDialog onCreated={invalidate} />}
      />

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(f) => f.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
