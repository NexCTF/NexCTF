import { Combobox } from "@base-ui/react/combobox";
import { ChevronDown, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  TeamComboboxPopup,
  teamTriggerClassName,
  useTeamOptions,
} from "@/components/team-combobox";
import { cn } from "@/lib/utils";

interface TeamMultiSelectProps {
  value: string[];
  onChange: (ids: string[]) => void;
}

export function TeamMultiSelect({ value, onChange }: TeamMultiSelectProps) {
  const { t } = useTranslation();
  const { rootProps, selected, query } = useTeamOptions(value);

  const triggerLabel =
    selected.length === 0
      ? t("admin.notifications.teams_placeholder", {
          defaultValue: "Select teams…",
        })
      : t("admin.notifications.n_teams_selected", {
          count: selected.length,
          defaultValue: "{{count}} team(s) selected",
        });

  return (
    <div className="space-y-2">
      <Combobox.Root
        {...rootProps}
        multiple
        value={selected}
        onValueChange={(teams) => onChange(teams.map((team) => team.id))}
      >
        <Combobox.Trigger
          className={cn(teamTriggerClassName, selected.length === 0 && "text-muted-foreground")}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronDown className="size-4 shrink-0 opacity-50" />
        </Combobox.Trigger>

        <TeamComboboxPopup query={query} multiple />
      </Combobox.Root>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((team) => (
            <span
              key={team.id}
              className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-xs"
            >
              {team.name}
              <button
                type="button"
                aria-label={t("admin.team_select.remove", {
                  name: team.name,
                  defaultValue: "Remove {{name}}",
                })}
                onClick={() => onChange(value.filter((id) => id !== team.id))}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
