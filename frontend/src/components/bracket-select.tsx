import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const GLOBAL_BRACKET = "__global__";

interface BracketSelectProps {
  brackets: string[];
  value: string | undefined;
  onChange: (bracket: string | undefined) => void;
}

/** Sub-scoreboard picker: "Global" plus one entry per team bracket in play. */
export function BracketSelect({ brackets, value, onChange }: BracketSelectProps) {
  const { t } = useTranslation();

  if (brackets.length === 0) return null;

  return (
    <Select
      value={value ?? GLOBAL_BRACKET}
      onValueChange={(v) => onChange(!v || v === GLOBAL_BRACKET ? undefined : v)}
    >
      <SelectTrigger className="w-44" aria-label={t("scoreboard.bracket_label")}>
        <SelectValue className="capitalize">{value ?? t("scoreboard.bracket_global")}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={GLOBAL_BRACKET}>{t("scoreboard.bracket_global")}</SelectItem>
        {brackets.map((b) => (
          <SelectItem key={b} value={b} className="capitalize">
            {b}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
