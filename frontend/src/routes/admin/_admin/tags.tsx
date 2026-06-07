import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
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
import { MarkdownEditor } from "@/components/ui/markdown-editor";
import {
  apiErrorMessage,
  createAdminTag,
  deleteAdminTag,
  getAdminTags,
  type Tag,
  updateAdminTag,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/tags")({
  component: TagsPage,
});

// ── Columns ───────────────────────────────────────────────────────────────────

function useColumns(t: (key: string) => string): Column<Tag>[] {
  return [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (tag) => <IdCell id={tag.id} />,
      className: "w-32",
    },
    {
      key: "name",
      header: t("admin.tags.col_name"),
      cell: (tag) => (
        <div className="flex items-center gap-2">
          <span
            className="size-3 rounded-full shrink-0 border border-white/20"
            style={{ backgroundColor: tag.color }}
          />
          <span className="font-medium">{tag.name}</span>
        </div>
      ),
    },
    {
      key: "description",
      header: t("admin.tags.col_description"),
      cell: (tag) => <span className="text-muted-foreground">{tag.description || "—"}</span>,
    },
    {
      key: "color",
      header: t("admin.tags.col_color"),
      cell: (tag) => <span className="font-mono text-xs text-muted-foreground">{tag.color}</span>,
    },
  ];
}

// ── Tag form fields ───────────────────────────────────────────────────────────

function TagFormFields({
  form,
  onChange,
}: {
  form: { name: string; description: string; color: string };
  onChange: (patch: Partial<typeof form>) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>{t("admin.tags.field_name")} *</Label>
        <Input value={form.name} onChange={(e) => onChange({ name: e.target.value })} required />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.tags.field_description")}</Label>
        <MarkdownEditor
          rows={2}
          value={form.description}
          onChange={(v) => onChange({ description: v })}
        />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.tags.field_color")} *</Label>
        <div className="flex gap-2 items-center">
          <input
            type="color"
            value={form.color}
            onChange={(e) => onChange({ color: e.target.value })}
            className="h-9 w-12 cursor-pointer rounded border bg-transparent p-1"
          />
          <Input
            value={form.color}
            onChange={(e) => onChange({ color: e.target.value })}
            placeholder="#3b82f6"
            className="font-mono"
          />
        </div>
      </div>
    </div>
  );
}

// ── Create dialog ─────────────────────────────────────────────────────────────

function CreateTagDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    color: "#3b82f6",
  });

  const mutation = useMutation({
    mutationFn: () => createAdminTag(form),
    onSuccess: () => {
      toast.success(t("admin.tags.created"));
      setOpen(false);
      setForm({ name: "", description: "", color: "#3b82f6" });
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.tags.create_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.tags.create")}
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("admin.tags.create")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <TagFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
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

// ── Edit dialog ───────────────────────────────────────────────────────────────

function EditTagDialog({ tag, onSaved }: { tag: Tag; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: tag.name,
    description: tag.description,
    color: tag.color,
  });

  const mutation = useMutation({
    mutationFn: () => updateAdminTag(tag.id, form),
    onSuccess: () => {
      toast.success(t("admin.tags.saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.tags.save_error"))),
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
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("admin.tags.edit")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <TagFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
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

// ── Page ──────────────────────────────────────────────────────────────────────

function TagsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "tags", table.queryString],
    queryFn: () => getAdminTags(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdminTag(id),
    onSuccess: () => {
      toast.success(t("admin.tags.deleted"));
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.tags.delete_error"))),
  });

  const columns = useColumns(t);
  const columnsWithActions: Column<Tag>[] = [
    ...columns,
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (tag) => (
        <div className="flex gap-1 justify-end">
          <EditTagDialog tag={tag} onSaved={invalidate} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(t("admin.tags.delete_confirm", { name: tag.name }))) {
                deleteMutation.mutate(tag.id);
              }
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("admin.tags.title")}</h1>
        <CreateTagDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columnsWithActions}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(tag) => tag.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
