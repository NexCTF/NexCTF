import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  ChevronUp,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { PaginatedResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Constants ─────────────────────────────────────────────────────────────────

const FILTER_ALL = "__all__";
const PER_PAGE_OPTIONS = [10, 20, 50, 100];
const SKELETON_ROWS = 5;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  cell?: (row: T) => ReactNode;
  className?: string;
}

export interface TableState {
  page: number;
  perPage: number;
  search: string;
  searchColumn: string;
  /** Active filters. Each key maps to a list of selected values. */
  filters: Record<string, string[]>;
  sortColumn: string | null;
  sortDirection: "asc" | "desc";
}

// ── useTableState ─────────────────────────────────────────────────────────────

export function useTableState(defaults?: Partial<TableState>) {
  const [state, setState] = useState<TableState>({
    page: 1,
    perPage: 20,
    search: "",
    searchColumn: "",
    filters: {},
    sortColumn: null,
    sortDirection: "asc",
    ...defaults,
  });

  const setPage = useCallback((page: number) => {
    setState((s) => ({ ...s, page }));
  }, []);

  const setSearch = useCallback((search: string) => {
    setState((s) => ({ ...s, page: 1, search }));
  }, []);

  const setSearchColumn = useCallback((searchColumn: string) => {
    setState((s) => ({ ...s, page: 1, searchColumn }));
  }, []);

  /** Replace all selected values for a filter key. Empty array = clear. */
  const setFilterValues = useCallback((key: string, values: string[]) => {
    setState((s) => {
      const filters = { ...s.filters };
      if (values.length === 0) {
        delete filters[key];
      } else {
        filters[key] = values;
      }
      return { ...s, page: 1, filters };
    });
  }, []);

  const resetFilters = useCallback(() => {
    setState((s) => ({ ...s, page: 1, filters: {} }));
  }, []);

  const setSort = useCallback((column: string) => {
    setState((s) => ({
      ...s,
      sortColumn: column,
      sortDirection: s.sortColumn === column && s.sortDirection === "asc" ? "desc" : "asc",
    }));
  }, []);

  const setPerPage = useCallback((perPage: number) => {
    setState((s) => ({ ...s, page: 1, perPage }));
  }, []);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", state.page.toString());
    params.set("items_per_page", state.perPage.toString());
    if (state.search) {
      params.set("search", state.search);
      if (state.searchColumn) params.set("search_by", state.searchColumn);
    }
    if (state.sortColumn) {
      params.set("order_by", state.sortColumn);
      params.set("order", state.sortDirection);
    }
    for (const [key, values] of Object.entries(state.filters)) {
      for (const value of values) {
        params.append(key, value);
      }
    }
    return params.toString();
  }, [state]);

  return {
    state,
    queryString,
    setPage,
    setSearch,
    setSearchColumn,
    setFilterValues,
    resetFilters,
    setSort,
    setPerPage,
  };
}

export type UseTableStateResult = ReturnType<typeof useTableState>;

// ── DataTable ─────────────────────────────────────────────────────────────────

interface DataTableProps<T> {
  columns: Column<T>[];
  response: PaginatedResponse<T> | undefined;
  table: UseTableStateResult;
  isLoading: boolean;
  isFetching?: boolean;
  rowKey?: (row: T) => string | number;
  onRefresh: () => void;
  onRowClick?: (row: T) => void;
}

function humanizeKey(key: string): string {
  return key
    .replace(/__/g, " ")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function humanizeValue(v: unknown): string {
  if (v === true || v === "true") return "Yes";
  if (v === false || v === "false") return "No";
  const s = String(v);
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function DataTable<T>({
  columns,
  response,
  table,
  isLoading,
  isFetching = false,
  rowKey,
  onRefresh,
  onRowClick,
}: DataTableProps<T>) {
  const { t } = useTranslation();
  const {
    state,
    setPage,
    setSearch,
    setSearchColumn,
    setFilterValues,
    resetFilters,
    setSort,
    setPerPage,
  } = table;

  // ── Search debounce ──────────────────────────────────────────────────────────

  const [searchInput, setSearchInput] = useState(state.search);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setSearchInput(state.search);
  }, [state.search]);

  function handleSearchInput(value: string) {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(value), 300);
  }

  // ── Pending filter state ─────────────────────────────────────────────────────
  //
  // While a filter dropdown is open, selections are held in pendingFilters
  // (local state). The parent state only updates when the dropdown closes.
  // This lets the user tick multiple values before triggering a new API call.

  const [pendingFilters, setPendingFilters] = useState<Record<string, string[]>>({});
  // Ref mirrors state so the onOpenChange callback never captures a stale value.
  const pendingRef = useRef(pendingFilters);
  pendingRef.current = pendingFilters;

  function handleFilterOpenChange(key: string, committedValues: string[], open: boolean) {
    if (open) {
      // Seed pending with currently committed values for this filter.
      setPendingFilters((prev) => ({ ...prev, [key]: [...committedValues] }));
    } else {
      // Commit to parent only when the dropdown closes.
      const pending = pendingRef.current[key];
      if (pending !== undefined) {
        setFilterValues(key, pending);
        setPendingFilters((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    }
  }

  function togglePending(key: string, value: string) {
    setPendingFilters((prev) => {
      const current = prev[key] ?? [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [key]: next };
    });
  }

  function clearFilter(key: string) {
    // Clear both pending (so the close handler won't re-apply) and committed.
    const next = { ...pendingRef.current };
    delete next[key];
    pendingRef.current = next;
    setPendingFilters(next);
    setFilterValues(key, []);
  }

  function handleResetFilters() {
    pendingRef.current = {};
    setPendingFilters({});
    resetFilters();
  }

  // ── Derived values ───────────────────────────────────────────────────────────

  const resolvedFilters = useMemo(() => {
    const attrs = response?.filter_attributes ?? {};
    return Object.entries(attrs)
      .map(([key, rawValues]) => ({
        key,
        label: humanizeKey(key),
        options: (rawValues as unknown[]).map((v) => ({
          value: String(v),
          label: humanizeValue(v),
        })),
      }))
      .filter((f) => f.options.length > 0);
  }, [response?.filter_attributes]);

  const searchColumns = response?.search_columns ?? [];
  const orderColumns = response?.order_columns ?? [];
  const hasActiveFilters = Object.values(state.filters).some((v) => v.length > 0);
  const data = response?.data ?? [];
  const pagination = response?.pagination;
  const totalCount = pagination?.total_count ?? 0;
  const pages = pagination?.pages ?? 1;
  const from = totalCount === 0 ? 0 : (state.page - 1) * state.perPage + 1;
  const to = Math.min(state.page * state.perPage, totalCount);
  const showSkeleton = isLoading && !response;

  function isColumnSortable(col: Column<T>) {
    if (col.sortable === false) return false;
    if (orderColumns.length > 0 && !orderColumns.includes(col.key)) return false;
    return true;
  }

  function getSortIcon(key: string) {
    if (state.sortColumn !== key) return <ChevronsUpDown className="size-3.5 opacity-40" />;
    return state.sortDirection === "asc" ? (
      <ChevronUp className="size-3.5" />
    ) : (
      <ChevronDown className="size-3.5" />
    );
  }

  return (
    <div className="space-y-3">
      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search input + optional column scope selector */}
        <div className="flex flex-1 min-w-48 max-w-sm">
          {searchColumns.length > 1 && (
            <Select
              value={state.searchColumn || FILTER_ALL}
              onValueChange={(v) => setSearchColumn(v === FILTER_ALL ? "" : (v as string))}
            >
              <SelectTrigger className="w-fit rounded-r-none border-r-0 shrink-0">
                <SelectValue>
                  {state.searchColumn || t("table.all_columns", { defaultValue: "All columns" })}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FILTER_ALL}>
                  {t("table.all_columns", { defaultValue: "All columns" })}
                </SelectItem>
                {searchColumns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
            <Input
              placeholder={t("table.search", { defaultValue: "Search…" })}
              value={searchInput}
              onChange={(e) => handleSearchInput(e.target.value)}
              className={cn("pl-8", searchColumns.length > 1 && "rounded-l-none")}
            />
          </div>
        </div>

        {/* Multi-select filter dropdowns */}
        {resolvedFilters.map((filter) => {
          const committedValues = state.filters[filter.key] ?? [];
          // While open, show pending selections; otherwise show committed.
          const isOpen = filter.key in pendingFilters;
          const activeValues = isOpen ? (pendingFilters[filter.key] ?? []) : committedValues;
          const hasActive = activeValues.length > 0;
          const singleOption = filter.options.length <= 1;

          // "Role: All" / "Role: Admin" / "Role: Admin, User" / "Role: 2 selected"
          const valuesLabel = (() => {
            if (!hasActive) return t("table.filter_all", { defaultValue: "All" });
            if (activeValues.length <= 2) {
              return activeValues
                .map((v) => filter.options.find((o) => o.value === v)?.label ?? humanizeValue(v))
                .join(", ");
            }
            return t("table.n_selected", {
              count: activeValues.length,
              defaultValue: "{{count}} selected",
            });
          })();

          const displayLabel = `${filter.label}: ${valuesLabel}`;

          return (
            <div key={filter.key} className="flex items-center">
              <DropdownMenu
                onOpenChange={(open) => handleFilterOpenChange(filter.key, committedValues, open)}
              >
                <DropdownMenuTrigger
                  disabled={singleOption}
                  className={cn(
                    "flex h-8 items-center gap-1.5 rounded-lg border border-input bg-transparent px-2.5 text-sm whitespace-nowrap transition-colors outline-none select-none",
                    "hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50",
                    "data-popup-open:ring-3 data-popup-open:ring-ring/50 data-popup-open:border-ring",
                    !hasActive && "text-muted-foreground",
                    committedValues.length > 0 && "rounded-r-none border-r-0",
                  )}
                >
                  <span className="truncate">{displayLabel}</span>
                  <ChevronDown className="size-4 shrink-0 opacity-50" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  {filter.options.map((opt) => (
                    <DropdownMenuCheckboxItem
                      key={opt.value}
                      checked={activeValues.includes(opt.value)}
                      onCheckedChange={() => togglePending(filter.key, opt.value)}
                      closeOnClick={false}
                    >
                      {opt.label}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>

              {committedValues.length > 0 && (
                <button
                  type="button"
                  onClick={() => clearFilter(filter.key)}
                  className="flex h-8 items-center border border-input px-1.5 rounded-r-lg bg-transparent hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  aria-label={t("table.clear_filter", {
                    defaultValue: "Clear filter",
                  })}
                >
                  <X className="size-3.5" />
                </button>
              )}
            </div>
          );
        })}

        {/* Reset all filters */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetFilters}
            className="text-muted-foreground gap-1"
          >
            <X className="size-3.5" />
            {t("table.reset_filters", { defaultValue: "Reset filters" })}
          </Button>
        )}

        {/* Right side: refresh + per-page */}
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              onRefresh();
              toast.success(t("table.refreshed", { defaultValue: "Table refreshed" }));
            }}
            disabled={isFetching}
            title={t("table.refresh", { defaultValue: "Refresh" })}
          >
            <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("table.per_page", { defaultValue: "Per page" })}
          </span>
          <Select value={state.perPage.toString()} onValueChange={(v) => setPerPage(Number(v))}>
            <SelectTrigger className="w-[70px]">
              <SelectValue>{state.perPage}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {PER_PAGE_OPTIONS.map((n) => (
                <SelectItem key={n} value={n.toString()}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* ── Table ── */}
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left font-medium text-muted-foreground",
                    isColumnSortable(col) && "cursor-pointer select-none hover:text-foreground",
                    col.className,
                  )}
                  onClick={() => isColumnSortable(col) && setSort(col.key)}
                >
                  <div className="flex items-center gap-1.5">
                    {col.header}
                    {isColumnSortable(col) && getSortIcon(col.key)}
                  </div>
                </th>
              ))}
              {onRowClick && <th className="w-8" />}
            </tr>
          </thead>

          <tbody
            className={cn(
              "divide-y",
              isFetching && response && "opacity-50 transition-opacity duration-150",
            )}
          >
            {showSkeleton ? (
              Array.from({ length: SKELETON_ROWS }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows, never reorder
                <tr key={i}>
                  {columns.map((col) => (
                    <td key={col.key} className={cn("px-4 py-3", col.className)}>
                      <div className="h-4 bg-muted animate-pulse rounded" />
                    </td>
                  ))}
                  {onRowClick && <td className="w-8" />}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  {t("table.no_results", { defaultValue: "No results found." })}
                </td>
              </tr>
            ) : (
              data.map((row, i) => (
                <tr
                  key={rowKey ? rowKey(row) : i}
                  className={cn(
                    "transition-colors",
                    onRowClick
                      ? "group cursor-pointer hover:bg-accent/60 border-l-2 border-l-transparent hover:border-l-primary"
                      : "hover:bg-muted/30",
                  )}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={cn("px-4 py-3", col.className)}>
                      {col.cell
                        ? col.cell(row)
                        : String((row as Record<string, unknown>)[col.key] ?? "")}
                    </td>
                  ))}
                  {onRowClick && (
                    <td className="px-3 py-3 w-8 text-muted-foreground/30 group-hover:text-primary transition-colors">
                      <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination footer ── */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {t("table.showing", {
            from,
            to,
            total: totalCount,
            defaultValue: "Showing {{from}}–{{to}} of {{total}}",
          })}
        </span>
        <div className="flex items-center gap-2">
          <span>
            {t("table.page_of", {
              page: state.page,
              pages,
              defaultValue: "Page {{page}} of {{pages}}",
            })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(state.page - 1)}
            disabled={state.page <= 1 || isFetching}
          >
            <ChevronLeft className="size-4" />
            {t("table.previous", { defaultValue: "Previous" })}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(state.page + 1)}
            disabled={!pagination?.has_more || isFetching}
          >
            {t("table.next", { defaultValue: "Next" })}
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
