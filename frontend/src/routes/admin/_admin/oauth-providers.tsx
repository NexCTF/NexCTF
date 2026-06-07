import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, Pencil, Plus, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
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
import {
  type AdminOAuthProvider,
  apiErrorMessage,
  createAdminOAuthProvider,
  deleteAdminOAuthProvider,
  getAdminOAuthProviders,
  updateAdminOAuthProvider,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/oauth-providers")({
  component: OAuthProvidersPage,
});

// ── Columns ───────────────────────────────────────────────────────────────────

const COLUMNS: Column<AdminOAuthProvider>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (p) => <IdCell id={p.id} />,
    className: "w-32",
  },
  {
    key: "name",
    header: "Name",
    cell: (p) => (
      <div className="flex items-center gap-2">
        {p.icon_url && <img src={p.icon_url} alt="" className="size-4 rounded-sm object-contain" />}
        <span className="font-medium">{p.name}</span>
        <span className="font-mono text-xs text-muted-foreground">{p.slug}</span>
      </div>
    ),
  },
  {
    key: "discovery_url",
    header: "Discovery URL",
    cell: (p) => (
      <span className="font-mono text-xs text-muted-foreground truncate max-w-xs block">
        {p.discovery_url}
      </span>
    ),
  },
  {
    key: "is_active",
    header: "Active",
    cell: (p) =>
      p.is_active ? (
        <CheckCircle2 className="size-4 text-green-500" />
      ) : (
        <XCircle className="size-4 text-muted-foreground" />
      ),
    className: "w-20",
  },
];

// ── Shared form type ──────────────────────────────────────────────────────────

type ProviderForm = {
  slug: string;
  name: string;
  client_id: string;
  client_secret: string;
  discovery_url: string;
  scopes: string;
  icon_url: string;
  is_active: boolean;
};

// ── Form fields ───────────────────────────────────────────────────────────────

function ProviderFormFields({
  form,
  onChange,
  secretPlaceholder,
}: {
  form: ProviderForm;
  onChange: (patch: Partial<ProviderForm>) => void;
  secretPlaceholder?: string;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Name *</Label>
          <Input value={form.name} onChange={(e) => onChange({ name: e.target.value })} required />
        </div>
        <div className="space-y-1.5">
          <Label>Slug *</Label>
          <Input
            value={form.slug}
            onChange={(e) => onChange({ slug: e.target.value })}
            className="font-mono"
            required
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Discovery URL *</Label>
        <Input
          value={form.discovery_url}
          onChange={(e) => onChange({ discovery_url: e.target.value })}
          placeholder="https://accounts.example.com/.well-known/openid-configuration"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Client ID *</Label>
          <Input
            value={form.client_id}
            onChange={(e) => onChange({ client_id: e.target.value })}
            className="font-mono"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label>Client Secret {secretPlaceholder ? "(leave blank to keep)" : "*"}</Label>
          <Input
            type="password"
            value={form.client_secret}
            onChange={(e) => onChange({ client_secret: e.target.value })}
            placeholder={secretPlaceholder}
            className="font-mono"
            required={!secretPlaceholder}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Scopes</Label>
        <Input
          value={form.scopes}
          onChange={(e) => onChange({ scopes: e.target.value })}
          className="font-mono"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Icon URL</Label>
        <Input
          value={form.icon_url}
          onChange={(e) => onChange({ icon_url: e.target.value })}
          placeholder="https://example.com/icon.png"
        />
      </div>
      <div className="flex items-center justify-between rounded-lg border px-3 py-2.5">
        <p className="text-sm font-medium">Active</p>
        <Switch checked={form.is_active} onCheckedChange={(v) => onChange({ is_active: v })} />
      </div>
    </div>
  );
}

// ── Create dialog ─────────────────────────────────────────────────────────────

const EMPTY_FORM: ProviderForm = {
  slug: "",
  name: "",
  client_id: "",
  client_secret: "",
  discovery_url: "",
  scopes: "openid email profile",
  icon_url: "",
  is_active: true,
};

function CreateProviderDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ProviderForm>({ ...EMPTY_FORM });

  const mutation = useMutation({
    mutationFn: () =>
      createAdminOAuthProvider({
        ...form,
        icon_url: form.icon_url || null,
      }),
    onSuccess: () => {
      toast.success("Provider created");
      setOpen(false);
      setForm({ ...EMPTY_FORM });
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to create provider")),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            New Provider
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New OAuth provider</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <ProviderFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Edit dialog ───────────────────────────────────────────────────────────────

function EditProviderDialog({
  provider,
  onSaved,
}: {
  provider: AdminOAuthProvider;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ProviderForm>({
    slug: provider.slug,
    name: provider.name,
    client_id: provider.client_id,
    client_secret: "",
    discovery_url: provider.discovery_url,
    scopes: provider.scopes,
    icon_url: provider.icon_url ?? "",
    is_active: provider.is_active,
  });

  const mutation = useMutation({
    mutationFn: () => {
      const patch: Parameters<typeof updateAdminOAuthProvider>[1] = {
        slug: form.slug,
        name: form.name,
        client_id: form.client_id,
        discovery_url: form.discovery_url,
        scopes: form.scopes,
        icon_url: form.icon_url || null,
        is_active: form.is_active,
      };
      if (form.client_secret) patch.client_secret = form.client_secret;
      return updateAdminOAuthProvider(provider.id, patch);
    },
    onSuccess: () => {
      toast.success("Provider saved");
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to save provider")),
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
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit OAuth provider</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <ProviderFormFields
            form={form}
            onChange={(p) => setForm((f) => ({ ...f, ...p }))}
            secretPlaceholder="••••••••"
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function OAuthProvidersPage() {
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "oauth-providers", table.queryString],
    queryFn: () => getAdminOAuthProviders(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "oauth-providers"],
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdminOAuthProvider(id),
    onSuccess: () => {
      toast.success("Provider deleted");
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to delete provider")),
  });

  const columnsWithActions: Column<AdminOAuthProvider>[] = [
    ...COLUMNS,
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (provider) => (
        <div className="flex gap-1 justify-end">
          <EditProviderDialog provider={provider} onSaved={invalidate} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(`Delete provider "${provider.name}"?`)) {
                deleteMutation.mutate(provider.id);
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
        <h1 className="text-2xl font-bold">OAuth Providers</h1>
        <CreateProviderDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columnsWithActions}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(p) => p.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
