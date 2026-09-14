import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  DatabaseBackup as BackupIcon,
  Download,
  RotateCcw,
  RotateCw,
  TriangleAlert,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Banner } from "@/components/banner";
import { BetaBadge } from "@/components/beta-badge";
import { ConfirmDialog, DeleteButton } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { ActionsCell, DateCell, EmptyCell } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import {
  adminBackupDownloadUrl,
  apiErrorMessage,
  type BackupSource,
  createAdminBackup,
  type DatabaseBackup,
  deleteAdminBackup,
  getAdminBackups,
  getPublicInfo,
  restoreAdminBackup,
} from "@/lib/api";
import { cn, formatBytes } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/backups")({
  component: BackupsPage,
});

const POLL_MS = 3000;
const PREFIX = /^backups\//;
const PILL = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";

const SOURCE_STYLES: Record<BackupSource, string> = {
  manual: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  auto: "bg-green-500/10 text-green-600 dark:text-green-400",
  pre_restore: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

/** What triggered a dump. Dumps taken before sources were recorded have none. */
function SourceCell({ source }: { source: BackupSource | null }) {
  const { t } = useTranslation();
  if (!source) return <EmptyCell />;

  const labels: Record<BackupSource, string> = {
    manual: t("admin.backups.source_manual", { defaultValue: "Manual" }),
    auto: t("admin.backups.source_auto", { defaultValue: "Scheduled" }),
    pre_restore: t("admin.backups.source_pre_restore", { defaultValue: "Pre-restore" }),
  };

  return <span className={cn(PILL, SOURCE_STYLES[source])}>{labels[source]}</span>;
}

/** Overlay covering the page while a restore runs, until the API answers again. */
function RestoringOverlay() {
  const { t } = useTranslation();
  const sawDowntime = useRef(false);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        await getPublicInfo();
        // Reload only once the API has been seen down and has come back.
        if (sawDowntime.current) window.location.reload();
      } catch {
        sawDowntime.current = true;
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-background/95">
      <RotateCw className="size-8 animate-spin text-muted-foreground" />
      <p className="text-lg font-medium">
        {t("admin.backups.restoring", { defaultValue: "Restoring the database…" })}
      </p>
      <p className="text-sm text-muted-foreground max-w-md text-center">
        {t("admin.backups.restoring_hint", {
          defaultValue:
            "The platform is restarting and everyone has been signed out. This page reloads on its own.",
        })}
      </p>
    </div>
  );
}

/** Single full-width row standing in for the table body. */
function MessageRow({ children }: { children: ReactNode }) {
  return (
    <tr>
      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
        {children}
      </td>
    </tr>
  );
}

function BackupRow({
  backup,
  onRestore,
  onChanged,
}: {
  backup: DatabaseBackup;
  onRestore: (key: string) => void;
  onChanged: () => void;
}) {
  const { t } = useTranslation();

  const remove = useMutation({
    mutationFn: () => deleteAdminBackup(backup.key),
    onSuccess: () => {
      toast.success(t("admin.backups.deleted", { defaultValue: "Backup deleted" }));
      onChanged();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.backups.delete_error", { defaultValue: "Delete failed" })),
      ),
  });

  const name = backup.key.replace(PREFIX, "");

  return (
    <tr className="hover:bg-muted/20 transition-colors">
      <td className="px-4 py-3 font-mono text-xs">{name}</td>
      <td className="px-4 py-3 text-muted-foreground text-xs tabular-nums">
        {formatBytes(backup.size)}
      </td>
      <td className="px-4 py-3 text-xs">
        <DateCell value={backup.created_at} />
      </td>
      <td className="px-4 py-3 text-xs">
        <SourceCell source={backup.source} />
      </td>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
        {backup.revision ?? <EmptyCell />}
      </td>
      <td className="px-4 py-3 text-right">
        <ActionsCell>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("admin.backups.download", { defaultValue: "Download" })}
            title={t("admin.backups.download_hint", {
              defaultValue: "Download this dump to your computer",
            })}
            onClick={() => {
              window.location.href = adminBackupDownloadUrl(backup.key);
            }}
          >
            <Download className="size-3.5" />
          </Button>
          <ConfirmDialog
            description={t("admin.backups.restore_confirm", {
              name,
              defaultValue:
                'Restore "{{name}}"? This replaces the entire database and signs out every user. The current database is backed up first, so this can be rolled back. The platform will be unavailable for a moment.',
            })}
            confirmLabel={t("admin.backups.restore", { defaultValue: "Restore" })}
            onConfirm={() => onRestore(backup.key)}
            trigger={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("admin.backups.restore", { defaultValue: "Restore" })}
                title={t("admin.backups.restore_hint", {
                  defaultValue: "Replace the database with this dump and restart",
                })}
              >
                <RotateCcw className="size-3.5" />
              </Button>
            }
          />
          <DeleteButton
            description={t("admin.backups.delete_confirm", {
              name,
              defaultValue: 'Delete backup "{{name}}"?',
            })}
            label={t("admin.backups.delete_hint", {
              defaultValue: "Delete this dump from storage",
            })}
            disabled={remove.isPending}
            onConfirm={() => remove.mutate()}
          />
        </ActionsCell>
      </td>
    </tr>
  );
}

function BackupsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [restoring, setRestoring] = useState(false);

  const { data: listing, isLoading } = useQuery({
    queryKey: ["admin", "backups"],
    queryFn: getAdminBackups,
  });
  const backups = listing?.backups;
  const lastRestore = listing?.last_restore;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "backups"] });
  }

  const create = useMutation({
    mutationFn: createAdminBackup,
    onSuccess: () => {
      toast.success(t("admin.backups.created", { defaultValue: "Backup created" }));
      invalidate();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.backups.create_error", { defaultValue: "Backup failed" })),
      ),
  });

  const restore = useMutation({
    mutationFn: restoreAdminBackup,
    onSuccess: () => setRestoring(true),
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.backups.restore_error", { defaultValue: "Restore failed" })),
      ),
  });

  if (restoring) return <RestoringOverlay />;

  const headers = [
    t("admin.backups.col_name", { defaultValue: "Backup" }),
    t("admin.files.col_size", { defaultValue: "Size" }),
    t("table.col_created_at", { defaultValue: "Created at" }),
    t("admin.backups.col_source", { defaultValue: "Source" }),
    t("admin.backups.col_revision", { defaultValue: "Revision" }),
  ];

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={BackupIcon}
        title={t("admin.nav.backups", { defaultValue: "Backups" })}
        badge={<BetaBadge />}
        actions={
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending}
            title={t("admin.backups.backup_now_hint", {
              defaultValue: "Dump the database now and store it in S3",
            })}
          >
            <BackupIcon className="size-4" />
            {create.isPending
              ? t("admin.backups.creating", { defaultValue: "Backing up…" })
              : t("admin.backups.backup_now", { defaultValue: "Backup now" })}
          </Button>
        }
      />

      {lastRestore?.startsWith("failed") && (
        <Banner tone="amber" icon={TriangleAlert}>
          {t("admin.backups.last_restore_failed", {
            status: lastRestore,
            defaultValue: "The last restore did not complete: {{status}}",
          })}
        </Banner>
      )}

      <Banner tone="amber" icon={TriangleAlert}>
        {t("admin.backups.scope_warning", {
          defaultValue:
            "Backups cover the database only, not uploaded files. Restoring an older backup can leave challenge attachments pointing at files that no longer exist.",
        })}
      </Banner>

      <p className="text-sm text-muted-foreground">
        {t("admin.backups.schedule_hint", {
          defaultValue:
            "Schedule recurring backups with a “backup_database” job in the Scheduler. Its keep_last parameter prunes older dumps; pre-restore copies are always kept.",
        })}
      </p>

      <div className="rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  className="px-4 py-2.5 text-left font-medium text-muted-foreground"
                >
                  {header}
                </th>
              ))}
              <th className="w-28" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && <MessageRow>{t("common.loading")}</MessageRow>}
            {!isLoading && !backups?.length && (
              <MessageRow>
                {t("admin.backups.empty", { defaultValue: "No backups yet." })}
              </MessageRow>
            )}
            {backups?.map((b) => (
              <BackupRow key={b.key} backup={b} onRestore={restore.mutate} onChanged={invalidate} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
