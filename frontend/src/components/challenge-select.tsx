import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getAdminChallenges } from "@/lib/api";

const NO_CHALLENGE = "__none__";

interface ChallengeSelectProps {
  value: string | null;
  onChange: (id: string | null) => void;
}

/** Optional challenge picker: "None" plus every challenge, by title. */
export function ChallengeSelect({ value, onChange }: ChallengeSelectProps) {
  const { t } = useTranslation();
  // ponytail: one page of challenges, truncated past 100. Switch to the cursor
  // search in use-team-search.ts if a CTF ever runs more than that.
  const { data } = useQuery({
    queryKey: ["admin", "challenges", "picker"],
    queryFn: () => getAdminChallenges("items_per_page=100&order_by=title&order=asc"),
  });
  const noneLabel = t("admin.scoreboard.no_challenge", { defaultValue: "None" });

  return (
    <Select
      value={value ?? NO_CHALLENGE}
      onValueChange={(v) => onChange(!v || v === NO_CHALLENGE ? null : v)}
    >
      <SelectTrigger className="w-full">
        <SelectValue>{data?.data.find((c) => c.id === value)?.title ?? noneLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NO_CHALLENGE}>{noneLabel}</SelectItem>
        {(data?.data ?? []).map((c) => (
          <SelectItem key={c.id} value={c.id}>
            {c.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
