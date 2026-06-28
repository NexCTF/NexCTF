import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, CheckCircle2, Copy, Link, Pencil, Plus, Trash2, XCircle } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type AdminOAuthClient,
  type AdminOAuthClientCreated,
  apiErrorMessage,
  createAdminOAuthClient,
  deleteAdminOAuthClient,
  getAdminOAuthClients,
  updateAdminOAuthClient,
} from "@/lib/api";
import { copyToClipboard } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/oauth-clients")({
  component: OAuthClientsPage,
});

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={copy}>
      {copied ? <Check className="size-3.5 text-green-500" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

// ── Columns ───────────────────────────────────────────────────────────────────

function getColumns(t: ReturnType<typeof useTranslation>["t"]): Column<AdminOAuthClient>[] {
  return [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (c) => <IdCell id={c.id} />,
      className: "w-32",
    },
    {
      key: "name",
      header: t("admin.oauth_client.col_name"),
      cell: (c) => (
        <div>
          <p className="font-medium">{c.name}</p>
          {c.description && (
            <p className="text-xs text-muted-foreground truncate max-w-64">{c.description}</p>
          )}
        </div>
      ),
    },
    {
      key: "client_id",
      header: t("admin.oauth_client.col_client_id"),
      cell: (c) => <code className="font-mono text-xs text-muted-foreground">{c.client_id}</code>,
    },
    {
      key: "allowed_scopes",
      header: t("admin.oauth_client.col_scopes"),
      cell: (c) => <span className="text-xs text-muted-foreground">{c.allowed_scopes}</span>,
    },
    {
      key: "is_active",
      header: t("admin.oauth_client.col_active"),
      cell: (c) =>
        c.is_active ? (
          <CheckCircle2 className="size-4 text-green-500" />
        ) : (
          <XCircle className="size-4 text-muted-foreground" />
        ),
      className: "w-20",
    },
  ];
}

// ── Form fields ───────────────────────────────────────────────────────────────

type ClientForm = {
  name: string;
  description: string;
  redirect_uris: string;
  allowed_scopes: string;
  allowed_roles: string;
  is_active: boolean;
};

function ClientFormFields({
  form,
  onChange,
}: {
  form: ClientForm;
  onChange: (patch: Partial<ClientForm>) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>{t("admin.oauth_client.field_name")} *</Label>
        <Input value={form.name} onChange={(e) => onChange({ name: e.target.value })} required />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.oauth_client.field_description")}</Label>
        <Input
          value={form.description}
          onChange={(e) => onChange({ description: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.oauth_client.field_redirect_uris")} *</Label>
        <Textarea
          value={form.redirect_uris}
          onChange={(e) => onChange({ redirect_uris: e.target.value })}
          placeholder="https://example.com/callback"
          rows={3}
          className="font-mono text-xs"
          required
        />
        <p className="text-xs text-muted-foreground">
          {t("admin.oauth_client.redirect_uris_hint")}
        </p>
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.oauth_client.field_allowed_scopes")}</Label>
        <Input
          value={form.allowed_scopes}
          onChange={(e) => onChange({ allowed_scopes: e.target.value })}
          placeholder="openid profile email roles"
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">{t("admin.oauth_client.scopes_hint")}</p>
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.oauth_client.field_allowed_roles")}</Label>
        <Input
          value={form.allowed_roles}
          onChange={(e) => onChange({ allowed_roles: e.target.value })}
          placeholder="admin moderator user"
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">{t("admin.oauth_client.roles_hint")}</p>
      </div>
      <div className="flex items-center gap-3">
        <Switch checked={form.is_active} onCheckedChange={(v) => onChange({ is_active: v })} />
        <Label>{t("admin.oauth_client.field_active")}</Label>
      </div>
    </div>
  );
}

// ── Endpoints dialog ──────────────────────────────────────────────────────────

function EndpointsDialog({ client }: { client: AdminOAuthClient }) {
  const { t } = useTranslation();
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            title={t("admin.oauth_client.endpoints")}
          >
            <Link className="size-3.5" />
          </Button>
        }
      />
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("admin.oauth_client.endpoints")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              {t("admin.oauth_client.col_client_id")}
            </p>
            <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
              <code className="flex-1 text-xs font-mono break-all">{client.client_id}</code>
              <CopyButton value={client.client_id} />
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">
              {t("admin.oauth_client.endpoints")}
            </p>
            <div className="rounded-lg border bg-muted/40 divide-y text-xs font-mono">
              {Object.entries(client.endpoints).map(([key, url]) => (
                <div key={key} className="flex items-center gap-2 px-3 py-2">
                  <span className="w-20 shrink-0 text-muted-foreground capitalize">{key}</span>
                  <span className="flex-1 break-all">{url}</span>
                  <CopyButton value={url} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Create dialog ─────────────────────────────────────────────────────────────

const EMPTY_FORM: ClientForm = {
  name: "",
  description: "",
  redirect_uris: "",
  allowed_scopes: "openid profile email roles",
  allowed_roles: "",
  is_active: true,
};

function CreateClientDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ClientForm>(EMPTY_FORM);
  const [created, setCreated] = useState<AdminOAuthClientCreated | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createAdminOAuthClient({
        ...form,
        description: form.description || null,
        allowed_roles: form.allowed_roles || null,
      }),
    onSuccess: (data) => {
      setCreated(data);
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.oauth_client.create_error"))),
  });

  function handleClose() {
    setOpen(false);
    setCreated(null);
    setForm(EMPTY_FORM);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.oauth_client.create")}
          </Button>
        }
      />
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {created ? t("admin.oauth_client.created_title") : t("admin.oauth_client.new_title")}
          </DialogTitle>
        </DialogHeader>

        {created ? (
          <div className="space-y-4 mt-2">
            <p className="text-sm text-muted-foreground">{t("admin.oauth_client.secret_hint")}</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  {t("admin.oauth_client.col_client_id")}
                </p>
                <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
                  <code className="flex-1 text-xs font-mono break-all">{created.client_id}</code>
                  <CopyButton value={created.client_id} />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  {t("admin.oauth_client.client_secret")}
                </p>
                <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
                  <code className="flex-1 text-xs font-mono break-all">
                    {created.client_secret}
                  </code>
                  <CopyButton value={created.client_secret} />
                </div>
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                {t("admin.oauth_client.endpoints")}
              </p>
              <div className="rounded-lg border bg-muted/40 divide-y text-xs font-mono">
                {Object.entries(created.endpoints).map(([key, url]) => (
                  <div key={key} className="flex items-center gap-2 px-3 py-2">
                    <span className="w-20 shrink-0 text-muted-foreground capitalize">{key}</span>
                    <span className="flex-1 break-all">{url}</span>
                    <CopyButton value={url} />
                  </div>
                ))}
              </div>
            </div>
            <DialogFooter>
              <Button onClick={handleClose}>{t("common.done")}</Button>
            </DialogFooter>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate();
            }}
            className="space-y-4 mt-2"
          >
            <ClientFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? t("common.saving") : t("common.save")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Edit dialog ───────────────────────────────────────────────────────────────

function EditClientDialog({ client, onSaved }: { client: AdminOAuthClient; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ClientForm>({
    name: client.name,
    description: client.description ?? "",
    redirect_uris: client.redirect_uris,
    allowed_scopes: client.allowed_scopes,
    allowed_roles: client.allowed_roles ?? "",
    is_active: client.is_active,
  });

  const mutation = useMutation({
    mutationFn: () =>
      updateAdminOAuthClient(client.id, {
        ...form,
        description: form.description || null,
        allowed_roles: form.allowed_roles || null,
      }),
    onSuccess: () => {
      toast.success(t("admin.oauth_client.saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.oauth_client.save_error"))),
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
          <DialogTitle>{t("admin.oauth_client.edit_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <ClientFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
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

function OAuthClientsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "oauth-clients", table.queryString],
    queryFn: () => getAdminOAuthClients(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "oauth-clients"],
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdminOAuthClient(id),
    onSuccess: () => {
      toast.success(t("admin.oauth_client.deleted"));
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.oauth_client.delete_error"))),
  });

  const columns = getColumns(t);
  const columnsWithActions: Column<AdminOAuthClient>[] = [
    ...columns,
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (client) => (
        <div className="flex gap-1 justify-end">
          <EndpointsDialog client={client} />
          <EditClientDialog client={client} onSaved={invalidate} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(t("admin.oauth_client.delete_confirm", { name: client.name }))) {
                deleteMutation.mutate(client.id);
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
        <div>
          <h1 className="text-2xl font-bold">{t("admin.oauth_client.title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("admin.oauth_client.subtitle")}</p>
        </div>
        <CreateClientDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columnsWithActions}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(c) => c.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
