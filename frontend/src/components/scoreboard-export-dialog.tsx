import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  adminScoreboardExportUrl,
  type ScoreboardCustomField,
  type ScoreboardExportFormat,
} from "@/lib/api";

interface ExportColumn {
  id: string;
  label: string;
}

interface ScoreboardExportDialogProps {
  bracket: string | undefined;
  /** Column ids in export order, as listed by the backend. */
  columnIds: string[];
  customFields: ScoreboardCustomField[];
  onClose: () => void;
}

/** Label each backend column id; unknown ids fall back to the raw id. */
function useExportColumns(
  columnIds: string[],
  customFields: ScoreboardCustomField[],
): ExportColumn[] {
  const { t } = useTranslation();
  const labels: Record<string, string> = {
    rank: t("scoreboard.col_rank"),
    team_name: t("scoreboard.col_team"),
    team_bracket: t("scoreboard.bracket_label"),
    total: t("scoreboard.col_total"),
    solve_points: t("scoreboard.col_solve_points", { defaultValue: "Solve points" }),
    hint_points: t("scoreboard.col_hints", { defaultValue: "Hints" }),
    adjustment_points: t("scoreboard.col_adjustments", { defaultValue: "Adjustments" }),
    solve_count: t("scoreboard.col_solves", { defaultValue: "Solves" }),
    last_solve_at: t("admin.scoreboard.col_last_solve", { defaultValue: "Last solve" }),
  };
  for (const f of customFields) labels[`custom.${f.name}`] = f.label;
  return columnIds.map((id) => ({ id, label: labels[id] ?? id }));
}

function FormatPicker({
  value,
  onChange,
}: {
  value: ScoreboardExportFormat;
  onChange: (format: ScoreboardExportFormat) => void;
}) {
  const { t } = useTranslation();
  const formats: { id: ScoreboardExportFormat; label: string }[] = [
    { id: "csv", label: t("admin.scoreboard.export_format_csv", { defaultValue: "CSV" }) },
    { id: "json", label: t("admin.scoreboard.export_format_json", { defaultValue: "JSON" }) },
    {
      id: "ctftime",
      label: t("admin.scoreboard.export_format_ctftime", { defaultValue: "CTFtime JSON" }),
    },
  ];
  return (
    <fieldset className="flex flex-wrap gap-4">
      <legend className="mb-2 text-sm font-medium">
        {t("admin.scoreboard.export_format", { defaultValue: "Format" })}
      </legend>
      {formats.map((f) => (
        <label key={f.id} className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name="scoreboard-export-format"
            checked={value === f.id}
            onChange={() => onChange(f.id)}
          />
          {f.label}
        </label>
      ))}
    </fieldset>
  );
}

function ColumnPicker({
  columns,
  selected,
  onChange,
}: {
  columns: ExportColumn[];
  selected: Set<string>;
  onChange: (selected: Set<string>) => void;
}) {
  const { t } = useTranslation();
  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    onChange(next);
  };
  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 text-sm font-medium">
        {t("admin.scoreboard.export_columns", { defaultValue: "Columns" })}
      </legend>
      <div className="grid grid-cols-2 gap-2">
        {columns.map((c) => (
          <label key={c.id} className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={selected.has(c.id)}
              onChange={(e) => toggle(c.id, e.target.checked)}
              className="rounded border-input"
            />
            {c.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Pick a format (and CSV columns), then download the current scoreboard view. */
export function ScoreboardExportDialog({
  bracket,
  columnIds,
  customFields,
  onClose,
}: ScoreboardExportDialogProps) {
  const { t } = useTranslation();
  const columns = useExportColumns(columnIds, customFields);
  const [format, setFormat] = useState<ScoreboardExportFormat>("csv");
  const [selected, setSelected] = useState<Set<string>>(() => new Set(columns.map((c) => c.id)));

  const isCsv = format === "csv";
  const ordered = columns.filter((c) => selected.has(c.id)).map((c) => c.id);
  const disabled = isCsv && ordered.length === 0;
  const href = adminScoreboardExportUrl({ format, bracket, columns: ordered });

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t("admin.scoreboard.export_title", { defaultValue: "Export scoreboard" })}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <FormatPicker value={format} onChange={setFormat} />
          {isCsv && <ColumnPicker columns={columns} selected={selected} onChange={setSelected} />}
        </div>
        <DialogFooter>
          <a
            href={disabled ? undefined : href}
            download
            aria-disabled={disabled}
            className={buttonVariants({
              className: disabled ? "pointer-events-none opacity-50" : undefined,
            })}
          >
            <Download className="size-4" />
            {t("admin.scoreboard.export_download", { defaultValue: "Download" })}
          </a>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
