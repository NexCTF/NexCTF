import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Check, Copy, Plus, RefreshCw, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldsSection, useCustomFieldDefs } from "@/components/custom-fields-section";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { EmptyCell, idColumn, RoleBadge, StatusCell, TeamLink } from "@/components/table-cells";
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
import { copyToClipboard, generatePassword } from "@/lib/utils";

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
                ? t("common.creating", { defaultValue: "Creating…" })
                : t("common.create", { defaultValue: "Create" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function UsersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const columns: Column<User>[] = [
    idColumn<User>(t),
    {
      key: "username",
      header: t("table.col_username", { defaultValue: "Username" }),
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
      header: t("table.col_email", { defaultValue: "Email" }),
      cell: (u) =>
        u.email ? <span className="text-muted-foreground">{u.email}</span> : <EmptyCell />,
    },
    {
      key: "team",
      header: t("table.col_team", { defaultValue: "Team" }),
      cell: (u) => <TeamLink id={u.team_id} name={u.team_name} />,
    },
    {
      key: "role",
      header: t("table.col_role", { defaultValue: "Role" }),
      cell: (u) => <RoleBadge role={u.role} />,
    },
    {
      key: "is_active",
      header: t("table.col_status", { defaultValue: "Status" }),
      cell: (u) => <StatusCell active={u.is_active} />,
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
      <PageHeader
        icon={Users}
        title={t("admin.nav.users", { defaultValue: "Users" })}
        actions={
          <CreateUserDialog
            onCreated={() => void queryClient.invalidateQueries({ queryKey: ["admin", "users"] })}
          />
        }
      />

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
