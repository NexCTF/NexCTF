import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, Check, Copy, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldsSection, useCustomFieldDefs } from "@/components/custom-fields-section";
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
import { apiErrorMessage, createAdminUser, getAdminUsers, USER_ROLES, type User } from "@/lib/api";
import { cn, copyToClipboard, generatePassword } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/users")({
  component: UsersPage,
});

type UserForm = { username: string; email: string; password: string; role: string };

const EMPTY_FORM: UserForm = { username: "", email: "", password: "", role: "user" };

function CreateUserDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<UserForm>(() => ({
    ...EMPTY_FORM,
    password: generatePassword(),
  }));
  const [cfValues, setCfValues] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);
  const defs = useCustomFieldDefs("user", open);

  function change(patch: Partial<UserForm>) {
    setForm((f) => ({ ...f, ...patch }));
  }

  function reset() {
    setForm({ ...EMPTY_FORM, password: generatePassword() });
    setCfValues({});
    setCopied(false);
  }

  const mutation = useMutation({
    mutationFn: () =>
      createAdminUser({
        ...form,
        email: form.email || null,
        custom_fields: cfValues,
      }),
    onSuccess: () => {
      toast.success(t("admin.users.created", { defaultValue: "User created" }));
      setOpen(false);
      reset();
      onCreated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.users.create_error", { defaultValue: "Failed to create user" }),
        ),
      ),
  });

  function handleCopy() {
    copyToClipboard(form.password);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.users.create", { defaultValue: "New user" })}
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("admin.users.create", { defaultValue: "New user" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.users.field_username", { defaultValue: "Username" })}</Label>
            <Input
              value={form.username}
              onChange={(e) => change({ username: e.target.value })}
              autoComplete="off"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.users.field_email", { defaultValue: "Email" })}</Label>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => change({ email: e.target.value })}
              autoComplete="off"
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.users.field_password", { defaultValue: "Password" })}</Label>
            <div className="flex gap-1.5">
              <Input
                value={form.password}
                onChange={(e) => change({ password: e.target.value })}
                className="font-mono"
                autoComplete="new-password"
                required
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => change({ password: generatePassword() })}
                aria-label={t("admin.users.regenerate_password", { defaultValue: "Regenerate" })}
              >
                <RefreshCw className="size-4" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handleCopy}
                aria-label={t("common.copy", { defaultValue: "Copy" })}
              >
                {copied ? <Check className="size-4 text-green-500" /> : <Copy className="size-4" />}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("admin.users.password_hint", {
                defaultValue: "Copy it before creating: it is not shown again.",
              })}
            </p>
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.users.field_role", { defaultValue: "Role" })}</Label>
            <Select value={form.role} onValueChange={(v) => change({ role: v ?? "user" })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {USER_ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <CustomFieldsSection defs={defs} values={cfValues} onChange={setCfValues} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending
                ? t("common.creating", { defaultValue: "Creating..." })
                : t("common.create", { defaultValue: "Create" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RoleCell(user: User) {
  const isAdmin = user.role === "admin";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        isAdmin ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
      )}
    >
      {isAdmin && <ShieldCheck className="size-3" />}
      {user.role}
    </span>
  );
}

function UsersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const columns: Column<User>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (u) => <IdCell id={u.id} />,
      className: "w-32",
    },
    {
      key: "username",
      header: "Username",
      cell: (u) => (
        <div className="flex items-center gap-2">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium uppercase">
            {u.username[0]}
          </span>
          <span className="font-medium">{u.username}</span>
        </div>
      ),
    },
    {
      key: "email",
      header: "Email",
      cell: (u) => <span className="text-muted-foreground">{u.email ?? "—"}</span>,
    },
    {
      key: "team",
      header: "Team",
      cell: (u) =>
        u.team_id ? (
          <Link
            to="/admin/teams/$teamId"
            params={{ teamId: u.team_id }}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-sm font-medium text-primary underline-offset-2 hover:underline hover:bg-primary/10 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            {u.team_name}
            <ArrowUpRight className="size-3 opacity-60" />
          </Link>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "role",
      header: "Role",
      cell: RoleCell,
    },
    {
      key: "is_active",
      header: "Status",
      cell: (u) => (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-xs",
            u.is_active ? "text-green-600 dark:text-green-400" : "text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              u.is_active ? "bg-green-500" : "bg-muted-foreground/50",
            )}
          />
          {u.is_active ? t("admin.users.status_active") : t("admin.users.status_disabled")}
        </span>
      ),
    },
  ];

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "users", table.queryString],
    queryFn: () => getAdminUsers(table.queryString),
    placeholderData: (prev) => prev,
  });

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("admin.nav.users", { defaultValue: "Users" })}</h1>
        <CreateUserDialog
          onCreated={() => void queryClient.invalidateQueries({ queryKey: ["admin", "users"] })}
        />
      </div>

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(u) => u.id}
        onRefresh={() => void refetch()}
        onRowClick={(u) =>
          void navigate({
            to: "/admin/users/$userId",
            params: { userId: u.id },
          })
        }
      />
    </div>
  );
}
