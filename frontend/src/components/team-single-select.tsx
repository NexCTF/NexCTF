import { Combobox } from "@base-ui/react/combobox";
import { ChevronDown, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  TeamComboboxPopup,
  teamTriggerClassName,
  useTeamOptions,
} from "@/components/team-combobox";
import { cn } from "@/lib/utils";

interface TeamSingleSelectProps {
  value: string | null;
  onChange: (id: string | null) => void;
}

export function TeamSingleSelect({ value, onChange }: TeamSingleSelectProps) {
  const { t } = useTranslation();
  const { rootProps, selected, query } = useTeamOptions(value ? [value] : []);

  return (
    <Combobox.Root
      {...rootProps}
      value={selected[0] ?? null}
      onValueChange={(team) => onChange(team?.id ?? null)}
    >
      <div className="relative">
        <Combobox.Trigger
          className={cn(teamTriggerClassName, "pr-14 data-[placeholder]:text-muted-foreground")}
        >
          <span className="truncate">
            <Combobox.Value placeholder={t("admin.users.team_placeholder")} />
          </span>
          <ChevronDown className="absolute right-2.5 size-4 shrink-0 opacity-50" />
        </Combobox.Trigger>
        <Combobox.Clear
          aria-label={t("admin.team_select.clear", { defaultValue: "Clear team" })}
          className="absolute top-1/2 right-8 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="size-3.5" />
        </Combobox.Clear>
      </div>

      <TeamComboboxPopup query={query} />
    </Combobox.Root>
  );
}
