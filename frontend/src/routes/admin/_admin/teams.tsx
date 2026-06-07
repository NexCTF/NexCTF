import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { getAdminTeams, type Team } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/teams")({
  component: TeamsPage,
  validateSearch: (search: Record<string, unknown>) => ({
    search: typeof search.search === "string" ? search.search : undefined,
  }),
});

const COLUMNS: Column<Team>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (team) => <IdCell id={team.id} />,
    className: "w-32",
  },
  {
    key: "name",
    header: "Name",
    cell: (team) => <span className="font-medium">{team.name}</span>,
  },
];

function TeamsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { search: initialSearch } = Route.useSearch();

  const table = useTableState({ search: initialSearch ?? "" });

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "teams", table.queryString],
    queryFn: () => getAdminTeams(table.queryString),
    placeholderData: (prev) => prev,
  });

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">{t("admin.nav.teams", { defaultValue: "Teams" })}</h1>

      <DataTable
        columns={COLUMNS}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(team) => team.id}
        onRefresh={() => void refetch()}
        onRowClick={(team) =>
          void navigate({
            to: "/admin/teams/$teamId",
            params: { teamId: team.id },
          })
        }
      />
    </div>
  );
}
