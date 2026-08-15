import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldsSection, useCustomFieldDefs } from "@/components/custom-fields-section";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { LabelInput } from "@/components/label-input";
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
import { apiErrorMessage, createAdminTeam, getAdminTeams, type Team } from "@/lib/api";
import { useFacetValues } from "@/lib/use-facet-values";

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

function CreateTeamDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [bracket, setBracket] = useState("");
  const [cfValues, setCfValues] = useState<Record<string, string>>({});
  const brackets = useFacetValues("/admin/team", "bracket");
  const defs = useCustomFieldDefs("team", open);

  const mutation = useMutation({
    mutationFn: () =>
      createAdminTeam({
        name,
        country: country.toUpperCase() || null,
        bracket: bracket || null,
        custom_fields: cfValues,
      }),
    onSuccess: () => {
      toast.success(t("admin.teams.created", { defaultValue: "Team created" }));
      setOpen(false);
      setName("");
      setCountry("");
      setBracket("");
      setCfValues({});
      onCreated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.teams.create_error", { defaultValue: "Failed to create team" }),
        ),
      ),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.teams.create", { defaultValue: "New team" })}
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("admin.teams.create", { defaultValue: "New team" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_name", { defaultValue: "Name" })}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_country")}</Label>
            <Input
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase().slice(0, 2))}
              placeholder="FR"
              maxLength={2}
              className="font-mono uppercase w-24"
            />
            <p className="text-xs text-muted-foreground">{t("admin.teams.country_hint")}</p>
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_bracket")}</Label>
            <LabelInput
              suggestions={brackets}
              value={bracket}
              onValueChange={setBracket}
              placeholder="student"
              noun={t("admin.labels.noun_bracket")}
              className="w-44"
            />
            <p className="text-xs text-muted-foreground">{t("admin.teams.bracket_hint")}</p>
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

function TeamsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("admin.nav.teams", { defaultValue: "Teams" })}</h1>
        <CreateTeamDialog
          onCreated={() => void queryClient.invalidateQueries({ queryKey: ["admin", "teams"] })}
        />
      </div>

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
