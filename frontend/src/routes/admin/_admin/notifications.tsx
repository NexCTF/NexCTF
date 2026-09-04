import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Bell, Plus, Radio } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { idColumn, UserLink } from "@/components/table-cells";
import { TeamMultiSelect } from "@/components/team-multi-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type AdminNotification,
  apiErrorMessage,
  createAdminNotification,
  getAdminNotifications,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/admin/_admin/notifications")({
  component: NotificationsPage,
});

const EMPTY_FORM = {
  title: "",
  content: "",
  is_broadcast: false,
  team_ids: [] as string[],
};

function CreateNotificationDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const mutation = useMutation({
    mutationFn: createAdminNotification,
    onSuccess: () => {
      toast.success(
        t("admin.notifications.created", {
          defaultValue: "Notification created",
        }),
      );
      setOpen(false);
      setForm(EMPTY_FORM);
      onCreated();
    },
    onError: (err) => {
      toast.error(
        apiErrorMessage(
          err,
          t("admin.notifications.create_error", {
            defaultValue: "Failed to create notification",
          }),
        ),
      );
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.content.trim()) return;
    if (!form.is_broadcast && form.team_ids.length === 0) return;
    mutation.mutate({
      title: form.title,
      content: form.content,
      is_broadcast: form.is_broadcast,
      team_ids: form.is_broadcast ? [] : form.team_ids,
      // biome-ignore lint/style/noNonNullAssertion: admin panel requires authentication
      created_by_id: user!.id,
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.notifications.create", {
              defaultValue: "New notification",
            })}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("admin.notifications.create", {
              defaultValue: "New notification",
            })}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="notif-title">
              {t("admin.notifications.field_title", { defaultValue: "Title" })}
            </Label>
            <Input
              id="notif-title"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder={t("admin.notifications.title_placeholder", {
                defaultValue: "Notification title",
              })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="notif-content">
              {t("admin.notifications.field_content", {
                defaultValue: "Content",
              })}
            </Label>
            <Textarea
              id="notif-content"
              rows={4}
              value={form.content}
              onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
              placeholder={t("admin.notifications.content_placeholder", {
                defaultValue: "Notification message…",
              })}
              required
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border px-3 py-2.5">
            <div>
              <p className="text-sm font-medium">
                {t("admin.notifications.field_broadcast", {
                  defaultValue: "Broadcast",
                })}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("admin.notifications.broadcast_hint", {
                  defaultValue: "Send to all users instead of specific teams",
                })}
              </p>
            </div>
            <Switch
              checked={form.is_broadcast}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_broadcast: checked, team_ids: [] }))
              }
            />
          </div>

          {!form.is_broadcast && (
            <div className="space-y-1.5">
              <Label>
                {t("admin.notifications.field_teams", {
                  defaultValue: "Teams",
                })}
              </Label>
              <TeamMultiSelect
                value={form.team_ids}
                onChange={(ids) => setForm((f) => ({ ...f, team_ids: ids }))}
              />
              {form.team_ids.length === 0 && (
                <p className="text-xs text-destructive">
                  {t("admin.notifications.teams_required", {
                    defaultValue: "Select at least one team",
                  })}
                </p>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending || (!form.is_broadcast && form.team_ids.length === 0)}
            >
              {mutation.isPending ? t("common.saving") : t("common.save", { defaultValue: "Save" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function NotificationsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();
  const columns: Column<AdminNotification>[] = [
    idColumn<AdminNotification>(t),
    {
      key: "title",
      header: t("table.col_title", { defaultValue: "Title" }),
      cell: (n) => <span className="font-medium">{n.title}</span>,
    },
    {
      key: "is_broadcast",
      header: t("table.col_type", { defaultValue: "Type" }),
      cell: (n) =>
        n.is_broadcast ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            <Radio className="size-3" />
            {t("admin.notifications.type_broadcast", { defaultValue: "Broadcast" })}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {t("admin.notifications.type_targeted", { defaultValue: "Targeted" })}
          </span>
        ),
    },
    {
      key: "created_by_username",
      header: t("table.col_created_by", { defaultValue: "Created by" }),
      cell: (n) => <UserLink id={n.created_by_id} name={n.created_by_username} />,
    },
  ];

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "notifications", table.queryString],
    queryFn: () => getAdminNotifications(table.queryString),
    placeholderData: (prev) => prev,
  });

  function handleCreated() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "notifications"],
    });
  }

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={Bell}
        title={t("admin.nav.notifications", { defaultValue: "Notifications" })}
        actions={<CreateNotificationDialog onCreated={handleCreated} />}
      />

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(n) => n.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
