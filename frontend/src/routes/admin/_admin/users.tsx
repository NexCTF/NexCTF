import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { getAdminUsers, type User } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/users")({
  component: UsersPage,
});

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
      <h1 className="text-2xl font-bold">{t("admin.nav.users", { defaultValue: "Users" })}</h1>

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
