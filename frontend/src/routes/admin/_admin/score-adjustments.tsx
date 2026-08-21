import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { useScoreAdjustmentColumns } from "@/components/score-adjustment-table";
import { TeamSingleSelect } from "@/components/team-single-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  createAdminScoreAdjustment,
  deleteAdminScoreAdjustment,
  getAdminScoreAdjustments,
  type ScoreAdjustment,
  updateAdminScoreAdjustment,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/score-adjustments")({
  component: ScoreAdjustmentsPage,
});

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

interface AdjustmentFormState {
  team_id: string;
  amount: string;
  reason: string;
  challenge_id: string;
}

const EMPTY_FORM: AdjustmentFormState = {
  team_id: "",
  amount: "",
  reason: "",
  challenge_id: "",
};

function AddAdjustmentDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState<AdjustmentFormState>(EMPTY_FORM);

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      createAdminScoreAdjustment({
        team_id: form.team_id,
        amount: Number(form.amount),
        reason: form.reason,
        challenge_id: form.challenge_id || null,
      }),
    onSuccess: () => {
      toast.success(t("admin.scoreboard.adjustment_created"));
      setForm(EMPTY_FORM);
      onCreated();
      onClose();
    },
    onError: (err) =>
      toast.error(apiErrorMessage(err, t("admin.scoreboard.adjustment_create_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("admin.scoreboard.add_adjustment")}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_team")}</Label>
            <TeamSingleSelect
              value={form.team_id || null}
              onChange={(id) => setForm((f) => ({ ...f, team_id: id ?? "" }))}
            />
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_amount")}</Label>
            <Input
              type="number"
              placeholder={t("admin.scoreboard.amount_placeholder")}
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">{t("admin.scoreboard.amount_hint")}</p>
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_reason")}</Label>
            <Input
              placeholder={t("admin.scoreboard.reason_placeholder")}
              value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            onClick={() => mutate()}
            disabled={isPending || !form.team_id || !form.amount || !form.reason}
          >
            {isPending ? t("common.adding") : t("common.add")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditAdjustmentDialog({
  adjustment,
  onClose,
  onSaved,
}: {
  adjustment: ScoreAdjustment;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [amount, setAmount] = useState(String(adjustment.amount));
  const [reason, setReason] = useState(adjustment.reason);

  const { mutate, isPending } = useMutation({
    mutationFn: () => updateAdminScoreAdjustment(adjustment.id, { amount: Number(amount), reason }),
    onSuccess: () => {
      toast.success(t("admin.scoreboard.adjustment_saved"));
      onSaved();
      onClose();
    },
    onError: (err) =>
      toast.error(apiErrorMessage(err, t("admin.scoreboard.adjustment_save_error"))),
  });

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("admin.scoreboard.edit_adjustment")}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_team")}</Label>
            <p className="text-sm font-medium">{adjustment.team_name ?? adjustment.team_id}</p>
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_amount")}</Label>
            <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.scoreboard.field_reason")}</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutate()} disabled={isPending || !amount || !reason}>
            {isPending ? t("common.saving") : t("common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ScoreAdjustmentsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<ScoreAdjustment | null>(null);

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "score-adjustments", table.queryString],
    queryFn: () => getAdminScoreAdjustments(table.queryString),
    placeholderData: (prev) => prev,
  });

  const { mutate: remove } = useMutation({
    mutationFn: (id: string) => deleteAdminScoreAdjustment(id),
    onSuccess: () => {
      toast.success(t("admin.scoreboard.adjustment_deleted"));
      void queryClient.invalidateQueries({ queryKey: ["admin", "score-adjustments"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
    },
    onError: (err) =>
      toast.error(apiErrorMessage(err, t("admin.scoreboard.adjustment_delete_error"))),
  });

  const COLUMNS = useScoreAdjustmentColumns({ onEdit: setEditing, onDelete: remove });

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={SlidersHorizontal}
        title={t("admin.scoreboard.adjustments_title", { defaultValue: "Score Adjustments" })}
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus />
            {t("admin.scoreboard.add_adjustment")}
          </Button>
        }
      />

      <DataTable
        columns={COLUMNS}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(adj) => adj.id}
        onRefresh={() => void refetch()}
      />

      <AddAdjustmentDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: ["admin", "score-adjustments"] });
          void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
        }}
      />

      {editing && (
        <EditAdjustmentDialog
          adjustment={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ["admin", "score-adjustments"] });
            void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
          }}
        />
      )}
    </div>
  );
}
