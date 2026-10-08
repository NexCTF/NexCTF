import type { TableState } from "@/components/data-table";
import type { PaginatedResponse } from "@/lib/api";

interface ClientFilter<T> {
  options: string[];
  matches: (row: T, value: string) => boolean;
}

/** How to search, filter and sort the rows of one unpaginated endpoint. */
export interface ClientPageSpec<T> {
  searchText: (row: T) => string;
  filters?: Record<string, ClientFilter<T>>;
  sorters: Record<string, (row: T) => string | number>;
  defaultSort: (a: T, b: T) => number;
}

function compareBy<T>(key: (row: T) => string | number, dir: number) {
  return (a: T, b: T) => {
    const av = key(a);
    const bv = key(b);
    return av > bv ? dir : av < bv ? -dir : 0;
  };
}

function matchesFilters<T>(row: T, state: TableState, spec: ClientPageSpec<T>): boolean {
  return Object.entries(state.filters).every(([key, values]) => {
    const filter = spec.filters?.[key];
    return !filter || values.length === 0 || values.some((v) => filter.matches(row, v));
  });
}

/** Feed DataTable from an unpaginated endpoint: search, filter, sort and slice here. */
export function clientPage<T>(
  rows: T[],
  state: TableState,
  spec: ClientPageSpec<T>,
): PaginatedResponse<T> {
  const needle = state.search.trim().toLowerCase();
  const matched = rows.filter(
    (row) =>
      matchesFilters(row, state, spec) &&
      (needle === "" || spec.searchText(row).toLowerCase().includes(needle)),
  );

  const sorter = state.sortColumn ? spec.sorters[state.sortColumn] : undefined;
  const dir = state.sortDirection === "asc" ? 1 : -1;
  const sorted = [...matched].sort(sorter ? compareBy(sorter, dir) : spec.defaultSort);

  const start = (state.page - 1) * state.perPage;
  return {
    status: "SUCCESS",
    message: "",
    error_code: null,
    data: sorted.slice(start, start + state.perPage),
    pagination: {
      total_count: sorted.length,
      items_per_page: state.perPage,
      page: state.page,
      has_more: start + state.perPage < sorted.length,
      pages: Math.max(1, Math.ceil(sorted.length / state.perPage)),
    },
    pagination_type: "offset",
    filter_attributes: Object.fromEntries(
      Object.entries(spec.filters ?? {}).map(([key, filter]) => [key, filter.options]),
    ),
    search_columns: [],
    order_columns: Object.keys(spec.sorters),
  };
}
