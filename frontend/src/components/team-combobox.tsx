import { Combobox } from "@base-ui/react/combobox";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Check, Search } from "lucide-react";
import { type UIEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { searchAdminTeamsCursor, type Team } from "@/lib/api";
import { cn } from "@/lib/utils";

type TeamOption = Pick<Team, "id" | "name">;

type TeamSearchQuery = ReturnType<typeof useTeamOptions>["query"];

export const teamTriggerClassName = cn(
  "flex h-8 w-full items-center justify-between rounded-lg border border-input bg-transparent px-2.5 text-sm transition-colors outline-none",
  "hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
);

const optionProps = {
  itemToStringLabel: (team: TeamOption) => team.name,
  isItemEqualToValue: (a: TeamOption, b: TeamOption) => a.id === b.id,
};

/** Debounced server-side team search for a Combobox, keeping the selected teams labelled. */
export function useTeamOptions(selectedIds: readonly string[]) {
  const [search, setSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nameCache = useRef<Record<string, string>>({});

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const query = useInfiniteQuery({
    queryKey: ["admin", "teams", "cursor", search],
    queryFn: ({ pageParam }) => searchAdminTeamsCursor(search, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.pagination.next_cursor ?? null,
  });

  const teams = useMemo(() => {
    const loaded = query.data?.pages.flatMap((p) => p.data) ?? [];
    for (const team of loaded) nameCache.current[team.id] = team.name;
    return loaded;
  }, [query.data]);

  const selectedKey = selectedIds.join(",");
  const { selected, items } = useMemo(() => {
    const ids = selectedKey ? selectedKey.split(",") : [];
    const selected = ids.map((id) => ({ id, name: nameCache.current[id] ?? id }));
    const loaded = new Set(teams.map((t) => t.id));
    const items: TeamOption[] = [...selected.filter((s) => !loaded.has(s.id)), ...teams];
    return { selected, items };
  }, [selectedKey, teams]);

  function onInputValueChange(value: string, details: Combobox.Root.ChangeEventDetails) {
    if (details.reason === "input-clear" && details.isItemPress) {
      details.cancel();
      return;
    }
    if (details.reason === "input-change" || details.reason === "input-clear") {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => setSearch(value), 300);
    }
  }

  return {
    rootProps: { items, filteredItems: teams, onInputValueChange, ...optionProps },
    selected,
    query,
  };
}

interface TeamComboboxPopupProps {
  query: TeamSearchQuery;
  multiple?: boolean;
}

/** Search input and infinitely scrolling team list for a team Combobox. */
export function TeamComboboxPopup({ query, multiple = false }: TeamComboboxPopupProps) {
  const { t } = useTranslation();

  function handleScroll(e: UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
    if (nearBottom && query.hasNextPage && !query.isFetchingNextPage) {
      void query.fetchNextPage();
    }
  }

  return (
    <Combobox.Portal>
      <Combobox.Positioner className="z-50 w-[var(--anchor-width)] min-w-56" sideOffset={4}>
        <Combobox.Popup className="w-full rounded-lg border bg-popover text-popover-foreground shadow-md outline-none data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0">
          <div className="flex items-center border-b px-2.5">
            <Search className="size-3.5 shrink-0 text-muted-foreground" />
            <Combobox.Input
              className="h-8 w-full bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
              placeholder={t("table.search", { defaultValue: "Search…" })}
            />
          </div>

          <Combobox.Empty className="px-3 py-2 text-xs text-muted-foreground empty:p-0">
            {!query.isLoading && t("admin.notifications.no_teams")}
          </Combobox.Empty>

          <Combobox.List
            className="max-h-52 overflow-y-auto py-1 empty:p-0"
            onScroll={handleScroll}
          >
            {(team: TeamOption) => (
              <Combobox.Item
                key={team.id}
                value={team}
                className="group flex w-full cursor-default items-center gap-2 px-3 py-1.5 text-sm transition-colors data-[highlighted]:bg-muted/60"
              >
                <span
                  className={cn(
                    "flex size-4 shrink-0 items-center justify-center border border-input",
                    "group-data-[selected]:border-primary group-data-[selected]:bg-primary group-data-[selected]:text-primary-foreground",
                    multiple ? "rounded-sm" : "rounded-full",
                  )}
                >
                  <Combobox.ItemIndicator>
                    <Check className={multiple ? "size-3" : "size-2.5"} />
                  </Combobox.ItemIndicator>
                </span>
                {team.name}
              </Combobox.Item>
            )}
          </Combobox.List>

          <Combobox.Status className="px-3 py-2 text-xs text-muted-foreground empty:p-0">
            {(query.isLoading || query.isFetchingNextPage) && t("common.loading")}
          </Combobox.Status>
        </Combobox.Popup>
      </Combobox.Positioner>
    </Combobox.Portal>
  );
}
