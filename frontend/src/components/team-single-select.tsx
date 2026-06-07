import { Popover } from "@base-ui/react/popover";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useTeamSearch } from "@/lib/use-team-search";
import { cn } from "@/lib/utils";

interface TeamSingleSelectProps {
  value: string | null;
  onChange: (id: string | null) => void;
}

export function TeamSingleSelect({ value, onChange }: TeamSingleSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const { search, teams, query, nameCache, handleSearchInput } = useTeamSearch();

  function select(id: string, name: string) {
    nameCache.current[id] = name;
    onChange(id);
    setOpen(false);
  }

  const selectedName = value ? (nameCache.current[value] ?? value) : null;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 text-sm transition-colors outline-none",
          "hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring",
          !selectedName && "text-muted-foreground",
        )}
      >
        <span className="truncate">{selectedName ?? t("admin.users.team_placeholder")}</span>
        <div className="flex items-center gap-1 shrink-0 ml-2">
          {value && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="size-3.5" />
            </button>
          )}
          <ChevronDown className="size-4 opacity-50" />
        </div>
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
                <p className="px-3 py-2 text-xs text-muted-foreground">{t("common.loading")}</p>
              ) : teams.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  {t("admin.notifications.no_teams")}
                </p>
              ) : (
                teams.map((team) => (
                  <button
                    key={team.id}
                    type="button"
                    onClick={() => select(team.id, team.name)}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted/60 transition-colors"
                  >
                    <span
                      className={cn(
                        "flex size-4 shrink-0 items-center justify-center rounded-full border",
                        value === team.id
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-input",
                      )}
                    >
                      {value === team.id && <Check className="size-2.5" />}
                    </span>
                    {team.name}
                  </button>
                ))
              )}

              {query.hasNextPage && (
                <button
                  type="button"
                  onClick={() => void query.fetchNextPage()}
                  disabled={query.isFetchingNextPage}
                  className="w-full px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {query.isFetchingNextPage
                    ? t("common.loading")
                    : t("admin.notifications.load_more")}
                </button>
              )}
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
