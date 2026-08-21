import { Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import { DeleteButton } from "@/components/confirm-dialog";
import type { Column } from "@/components/data-table";
import {
  ActionsCell,
  ChallengeLink,
  idColumn,
  SignedPoints,
  TeamLink,
  UserLink,
} from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import type { ScoreAdjustment } from "@/lib/api";

/**
 * Score adjustment columns, shared with the team detail page.
 *
 * `showTeam` is off there, and the actions column only appears when the page
 * can edit and delete.
 */
export function useScoreAdjustmentColumns({
  showTeam = true,
  onEdit,
  onDelete,
}: {
  showTeam?: boolean;
  onEdit?: (adj: ScoreAdjustment) => void;
  onDelete?: (id: string) => void;
} = {}): Column<ScoreAdjustment>[] {
  const { t } = useTranslation();

  return [
    idColumn<ScoreAdjustment>(t),
    ...(showTeam
      ? [
          {
            key: "team_name",
            header: t("table.col_team", { defaultValue: "Team" }),
            cell: (adj: ScoreAdjustment) => <TeamLink id={adj.team_id} name={adj.team_name} />,
          },
        ]
      : []),
    {
      key: "amount",
      header: t("admin.scoreboard.col_amount"),
      sortable: true,
      cell: (adj) => <SignedPoints amount={adj.amount} />,
    },
    {
      key: "reason",
      header: t("admin.scoreboard.col_reason"),
    },
    {
      key: "challenge_title",
      header: t("table.col_challenge", { defaultValue: "Challenge" }),
      cell: (adj) => <ChallengeLink id={adj.challenge_id} name={adj.challenge_title} />,
    },
    {
      key: "created_by_username",
      header: t("table.col_created_by", { defaultValue: "Created by" }),
      cell: (adj) => <UserLink id={adj.created_by_id} name={adj.created_by_username} />,
    },
    ...(onEdit && onDelete
      ? [
          {
            key: "actions",
            header: "",
            sortable: false,
            cell: (adj: ScoreAdjustment) => (
              <ActionsCell>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => onEdit(adj)}
                  aria-label={t("common.edit")}
                >
                  <Pencil className="size-3.5" />
                </Button>
                <DeleteButton
                  description={t("admin.scoreboard.adjustment_delete_confirm")}
                  onConfirm={() => onDelete(adj.id)}
                />
              </ActionsCell>
            ),
            className: "w-20",
          },
        ]
      : []),
  ];
}
