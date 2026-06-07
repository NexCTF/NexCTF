import { Popover } from "@base-ui/react/popover";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Team } from "@/lib/api";
import { useTeamSearch } from "@/lib/use-team-search";
import { cn } from "@/lib/utils";

interface TeamMultiSelectProps {
  value: string[];
  onChange: (ids: string[]) => void;
}

export function TeamMultiSelect({ value, onChange }: TeamMultiSelectProps) {
  const { t } = useTranslation();
  const { search, teams, query, nameCache, handleSearchInput } = useTeamSearch();

  function toggle(team: Team) {
    nameCache.current[team.id] = team.name;
    onChange(value.includes(team.id) ? value.filter((id) => id !== team.id) : [...value, team.id]);
  }

  const triggerLabel =
    value.length === 0
      ? t("admin.notifications.teams_placeholder", {
          defaultValue: "Select teams…",
        })
      : t("admin.notifications.n_teams_selected", {
          count: value.length,
          defaultValue: "{{count}} team(s) selected",
        });

  return (
    <div className="space-y-2">
      <Popover.Root>
        <Popover.Trigger
          className={cn(
            "flex h-8 w-full items-center justify-between rounded-lg border border-input bg-transparent px-2.5 text-sm transition-colors outline-none",
            "hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
            value.length === 0 && "text-muted-foreground",
          )}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronDown className="size-4 shrink-0 opacity-50" />
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Positioner className="z-50 w-[var(--anchor-width)] min-w-56">
            <Popover.Popup className="w-full rounded-lg border bg-popover text-popover-foreground shadow-md outline-none data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0">
              <div className="flex items-center border-b px-2.5">
                <Search className="size-3.5 shrink-0 text-muted-foreground" />
                <input
                  className="h-8 w-full bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
                  placeholder={t("table.search", { defaultValue: "Search…" })}
                  value={search}
                  onChange={(e) => handleSearchInput(e.target.value)}
                  // biome-ignore lint/a11y/noAutofocus: intentional — focus search on dropdown open
                  autoFocus
                />
              </div>

              <div className="max-h-52 overflow-y-auto py-1">
                {query.isLoading ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    {t("common.loading", { defaultValue: "Loading…" })}
                  </p>
                ) : teams.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    {t("admin.notifications.no_teams", {
                      defaultValue: "No teams found",
                    })}
                  </p>
                ) : (
                  teams.map((team) => {
                    const selected = value.includes(team.id);
                    return (
                      <button
                        key={team.id}
                        type="button"
                        onClick={() => toggle(team)}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted/60 transition-colors"
                      >
                        <span
                          className={cn(
                            "flex size-4 shrink-0 items-center justify-center rounded-sm border",
                            selected
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-input",
                          )}
                        >
                          {selected && <Check className="size-3" />}
                        </span>
                        {team.name}
                      </button>
                    );
                  })
                )}

                {query.hasNextPage && (
                  <button
                    type="button"
                    onClick={() => void query.fetchNextPage()}
                    disabled={query.isFetchingNextPage}
                    className="w-full px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {query.isFetchingNextPage
                      ? t("common.loading", { defaultValue: "Loading…" })
                      : t("admin.notifications.load_more", {
                          defaultValue: "Load more",
                        })}
                  </button>
                )}
              </div>
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-xs"
            >
              {nameCache.current[id] ?? id}
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== id))}
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
