import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { searchAdminTeamsCursor } from "@/lib/api";

export function useTeamSearch() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nameCache = useRef<Record<string, string>>({});

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const query = useInfiniteQuery({
    queryKey: ["admin", "teams", "cursor", debouncedSearch],
    queryFn: ({ pageParam }) => searchAdminTeamsCursor(debouncedSearch, pageParam as string | null),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.pagination.next_cursor ?? null,
  });

  const teams = query.data?.pages.flatMap((p) => p.data) ?? [];
  for (const team of teams) {
    nameCache.current[team.id] = team.name;
  }

  function handleSearchInput(v: string) {
    setSearch(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(v), 300);
  }

  return { search, teams, query, nameCache, handleSearchInput };
}
