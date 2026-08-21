import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { DataTable, useTableState } from "@/components/data-table";
import { EventDetailsDialog, useEventColumns } from "@/components/event-table";
import { PageHeader } from "@/components/page-header";
import { useSSEEvent } from "@/hooks/use-sse-event";
import { type AdminEvent, getAdminEvents } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/events")({
  component: EventsPage,
});

function EventsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();
  const columns = useEventColumns();
  const [selected, setSelected] = useState<AdminEvent | null>(null);

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "events", table.queryString],
    queryFn: () => getAdminEvents(table.queryString),
    placeholderData: (prev) => prev,
  });

  // Refresh when a new event arrives via SSE
  useSSEEvent("event", () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "events"] });
  });

  return (
    <div className="p-8 space-y-6">
      <PageHeader icon={CalendarDays} title={t("admin.nav.events", { defaultValue: "Events" })} />

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(e) => e.id}
        onRefresh={() => void refetch()}
        onRowClick={(e) => setSelected(e)}
      />

      <EventDetailsDialog event={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
