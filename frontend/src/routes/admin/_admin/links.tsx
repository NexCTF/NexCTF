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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  type AdminLink,
  apiErrorMessage,
  createLink,
  deleteLink,
  getAdminLinks,
  type LinkVisibility,
  updateLink,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/links")({
  component: LinksPage,
});

// ── Form ──────────────────────────────────────────────────────────────────────

type LinkForm = { name: string; url: string; visibility: LinkVisibility; is_enabled: boolean };

const EMPTY_FORM: LinkForm = { name: "", url: "", visibility: "public", is_enabled: true };

function LinkFormFields({
  form,
  onChange,
}: {
  form: LinkForm;
  onChange: (patch: Partial<LinkForm>) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>{t("admin.links.field_name", { defaultValue: "Name" })}</Label>
        <Input value={form.name} onChange={(e) => onChange({ name: e.target.value })} required />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.links.field_url", { defaultValue: "URL" })}</Label>
        <Input
          type="url"
          value={form.url}
          onChange={(e) => onChange({ url: e.target.value })}
          placeholder="https://example.com"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.links.field_visibility", { defaultValue: "Visibility" })}</Label>
        <Select
          value={form.visibility}
          onValueChange={(v) => onChange({ visibility: v as LinkVisibility })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="public">
              {t("admin.links.visibility_public", { defaultValue: "Public" })}
            </SelectItem>
            <SelectItem value="admin">
              {t("admin.links.visibility_admin", { defaultValue: "Admin only" })}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center justify-between rounded-lg border px-3 py-2.5">
        <p className="text-sm font-medium">
          {t("admin.links.field_enabled", { defaultValue: "Enabled" })}
        </p>
        <Switch
          checked={form.is_enabled}
          onCheckedChange={(checked) => onChange({ is_enabled: checked })}
        />
      </div>
    </div>
  );
}

// ── Create dialog ─────────────────────────────────────────────────────────────

function CreateLinkDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<LinkForm>(EMPTY_FORM);

  const mutation = useMutation({
    mutationFn: () => createLink(form),
    onSuccess: () => {
      toast.success(t("admin.links.created", { defaultValue: "Link created" }));
      setOpen(false);
      setForm(EMPTY_FORM);
      onCreated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.links.create_error", { defaultValue: "Failed to create link" }),
        ),
      ),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.links.create", { defaultValue: "New link" })}
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("admin.links.create", { defaultValue: "New link" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <LinkFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending
                ? t("common.saving", { defaultValue: "Creating…" })
                : t("admin.links.create", { defaultValue: "Create" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Edit dialog ───────────────────────────────────────────────────────────────

function EditLinkDialog({ link, onSaved }: { link: AdminLink; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<LinkForm>({
    name: link.name,
    url: link.url,
    visibility: link.visibility,
    is_enabled: link.is_enabled,
  });

  const mutation = useMutation({
    mutationFn: () => updateLink(link.id, form),
    onSuccess: () => {
      toast.success(t("admin.links.saved", { defaultValue: "Link saved" }));
      setOpen(false);
      onSaved();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.links.save_error", { defaultValue: "Save failed" })),
      ),
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
          <DialogTitle>{t("admin.links.edit", { defaultValue: "Edit link" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <LinkFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
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

// ── Page ──────────────────────────────────────────────────────────────────────

function LinksPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "links", table.queryString],
    queryFn: () => getAdminLinks(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "links"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteLink(id),
    onSuccess: () => {
      toast.success(t("admin.links.deleted", { defaultValue: "Link deleted" }));
      invalidate();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.links.delete_error", { defaultValue: "Delete failed" })),
      ),
  });

  const columns: Column<AdminLink>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (l) => <IdCell id={l.id} />,
      className: "w-32",
    },
    {
      key: "name",
      header: t("admin.links.col_name", { defaultValue: "Name" }),
      cell: (l) => <span className="font-medium">{l.name}</span>,
    },
    {
      key: "url",
      header: t("admin.links.col_url", { defaultValue: "URL" }),
      cell: (l) => (
        <span className="text-xs text-muted-foreground truncate block max-w-xs">{l.url}</span>
      ),
    },
    {
      key: "visibility",
      header: t("admin.links.col_visibility", { defaultValue: "Visibility" }),
      cell: (l) => (
        <span className="text-xs">
          {l.visibility === "public"
            ? t("admin.links.visibility_public", { defaultValue: "Public" })
            : t("admin.links.visibility_admin", { defaultValue: "Admin only" })}
        </span>
      ),
    },
    {
      key: "is_enabled",
      header: t("admin.links.col_status", { defaultValue: "Status" }),
      cell: (l) =>
        l.is_enabled ? (
          <span className="text-xs text-green-600">
            {t("admin.links.enabled", { defaultValue: "Enabled" })}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">
            {t("admin.links.disabled", { defaultValue: "Disabled" })}
          </span>
        ),
    },
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (link) => (
        <div className="flex gap-1 justify-end">
          <EditLinkDialog link={link} onSaved={invalidate} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(t("admin.links.delete_confirm", { name: link.name }))) {
                deleteMutation.mutate(link.id);
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
        <h1 className="text-2xl font-bold">{t("admin.nav.links", { defaultValue: "Links" })}</h1>
        <CreateLinkDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(l) => l.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
