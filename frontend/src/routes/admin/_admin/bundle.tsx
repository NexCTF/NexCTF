import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download, FolderSync, GitBranch, Package, TriangleAlert, Upload, X } from "lucide-react";
import { type ReactNode, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Banner } from "@/components/banner";
import { BetaBadge } from "@/components/beta-badge";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import {
  adminBundleExportUrl,
  apiErrorMessage,
  applyAdminBundleImport,
  type BundleAction,
  type BundleEntityKind,
  type BundlePlan,
  type BundlePlanEntry,
  planAdminBundleImport,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/bundle")({
  component: BundlePage,
});

const PILL = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";

/** Actions that refuse the whole import until an author resolves them. */
const REFUSED = new Set<BundleAction>(["conflict", "blocked"]);

/** Actions that write. "skipped" is shown but changes nothing, so it is absent. */
const WRITING = new Set<BundleAction>(["create", "update", "event_state", "recreate", "delete"]);

interface Labels {
  actions: Record<BundleAction, string>;
  kinds: Record<BundleEntityKind, string>;
}

const ACTION_STYLES: Record<BundleAction, string> = {
  create: "bg-green-500/10 text-green-600 dark:text-green-400",
  update: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  event_state: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  recreate: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  delete: "bg-red-500/10 text-red-600 dark:text-red-400",
  conflict: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  blocked: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  skipped: "bg-zinc-500/10 text-zinc-500",
  unchanged: "bg-zinc-500/10 text-zinc-500",
};

/** Plan vocabulary. Written out so the i18n parser can see every key. */
function useLabels(): Labels {
  const { t } = useTranslation();

  const actions: Record<BundleAction, string> = {
    create: t("admin.bundle.action_create", { defaultValue: "Create" }),
    update: t("admin.bundle.action_update", { defaultValue: "Update" }),
    event_state: t("admin.bundle.action_event_state", { defaultValue: "Event state" }),
    recreate: t("admin.bundle.action_recreate", { defaultValue: "Recreate" }),
    delete: t("admin.bundle.action_delete", { defaultValue: "Delete" }),
    conflict: t("admin.bundle.action_conflict", { defaultValue: "Conflict" }),
    blocked: t("admin.bundle.action_blocked", { defaultValue: "Blocked" }),
    skipped: t("admin.bundle.action_skipped", { defaultValue: "Left alone" }),
    unchanged: t("admin.bundle.action_unchanged", { defaultValue: "Unchanged" }),
  };

  const kinds: Record<BundleEntityKind, string> = {
    challenge: t("admin.bundle.kind_challenge", { defaultValue: "Challenge" }),
    question: t("admin.bundle.kind_question", { defaultValue: "Question" }),
    hint: t("admin.bundle.kind_hint", { defaultValue: "Hint" }),
    solution: t("admin.bundle.kind_solution", { defaultValue: "Solution" }),
    file: t("admin.bundle.kind_file", { defaultValue: "File" }),
    page: t("admin.bundle.kind_page", { defaultValue: "Page" }),
    link: t("admin.bundle.kind_link", { defaultValue: "Link" }),
    custom_field: t("admin.bundle.kind_custom_field", { defaultValue: "Custom field" }),
    config: t("admin.bundle.kind_config", { defaultValue: "Setting" }),
  };

  return { actions, kinds };
}

function ActionPill({
  action,
  labels,
  count,
}: {
  action: BundleAction;
  labels: Labels;
  count?: number;
}) {
  return (
    <span className={cn(PILL, ACTION_STYLES[action])}>
      {labels.actions[action]}
      {count !== undefined && ` · ${count}`}
    </span>
  );
}

/** Single full-width row standing in for a table body. */
function MessageRow({ span, children }: { span: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={span} className="px-4 py-8 text-center text-muted-foreground">
        {children}
      </td>
    </tr>
  );
}

function ChangeList({ changes }: { changes: BundlePlanEntry["changes"] }) {
  const entries = Object.entries(changes);
  if (!entries.length) return null;
  return (
    <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-muted-foreground">
      {entries.map(([field, [before, after]]) => (
        <li key={field}>
          <span className="text-foreground">{field}</span>: {JSON.stringify(before)} →{" "}
          {JSON.stringify(after)}
        </li>
      ))}
    </ul>
  );
}

function PlanRow({ entry, labels }: { entry: BundlePlanEntry; labels: Labels }) {
  return (
    <tr className="hover:bg-muted/20 transition-colors align-top">
      <td className="px-4 py-3 text-xs text-muted-foreground">{labels.kinds[entry.kind]}</td>
      <td className="px-4 py-3 text-xs">
        <div className="font-medium">{entry.label}</div>
        <ChangeList changes={entry.changes} />
        {entry.reason && <p className="mt-1 text-[11px] text-amber-600">{entry.reason}</p>}
      </td>
      <td className="px-4 py-3">
        <ActionPill action={entry.action} labels={labels} />
      </td>
    </tr>
  );
}

/** Review dialog: inspect the complete plan, then apply it atomically. */
function PlanReview({
  plan,
  onApplied,
  onClose,
}: {
  plan: BundlePlan | null;
  onApplied: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Dialog
      open={plan !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            {t("admin.bundle.plan_title", { defaultValue: "Review the import" })}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {plan &&
              t("admin.bundle.plan_manifest", {
                version: plan.manifest.nexctf_version,
                defaultValue: "Built by NexCTF {{version}}. Nothing is written until you apply.",
              })}
          </p>
        </DialogHeader>
        {plan && <PlanBody plan={plan} onApplied={onApplied} onCancel={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

/** The dialog's body. Importing writes the whole reviewed plan atomically. */
function PlanBody({
  plan,
  onApplied,
  onCancel,
}: {
  plan: BundlePlan;
  onApplied: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const labels = useLabels();

  const apply = useMutation({
    mutationFn: () => applyAdminBundleImport(plan.import_key, plan.prune),
    onSuccess: (result) => {
      toast.success(
        t("admin.bundle.applied", {
          total: Object.values(result.counts).reduce((a, b) => a + b, 0),
          defaultValue: "Imported {{total}} change(s)",
        }),
      );
      onApplied();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.bundle.apply_error", { defaultValue: "Import failed" })),
      ),
  });

  const { applicableCount, shown, refusedCount } = useMemo(() => {
    const rows: BundlePlanEntry[] = [];
    let writing = 0;
    let refused = 0;
    for (const entry of plan.entries) {
      if (entry.action !== "unchanged") rows.push(entry);
      if (WRITING.has(entry.action)) writing += 1;
      if (REFUSED.has(entry.action)) refused += 1;
    }
    return { applicableCount: writing, shown: rows, refusedCount: refused };
  }, [plan.entries]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-xs">
        {Object.entries(plan.counts).map(([action, count]) => (
          <ActionPill key={action} action={action as BundleAction} labels={labels} count={count} />
        ))}
      </div>

      {refusedCount > 0 && (
        <Banner tone="amber" icon={TriangleAlert}>
          {t("admin.bundle.refused_warning", {
            total: refusedCount,
            defaultValue:
              "{{total}} entries cannot be applied: a unique title or slug is taken, or solve history still references what would be deleted.",
          })}
        </Banner>
      )}

      <div className="max-h-[55vh] overflow-y-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 border-b bg-muted z-10">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                {t("admin.bundle.col_kind", { defaultValue: "Kind" })}
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                {t("admin.bundle.col_entity", { defaultValue: "Entity" })}
              </th>
              <th className="w-32 px-4 py-2.5 text-left font-medium text-muted-foreground">
                {t("admin.bundle.col_action", { defaultValue: "Action" })}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {!shown.length && (
              <MessageRow span={3}>
                {t("admin.bundle.plan_empty", {
                  defaultValue: "This archive matches the instance exactly.",
                })}
              </MessageRow>
            )}
            {shown.map((entry) => (
              <PlanRow key={`${entry.kind}:${entry.id}`} entry={entry} labels={labels} />
            ))}
          </tbody>
        </table>
      </div>

      <DialogFooter>
        <Button variant="ghost" onClick={onCancel}>
          <X className="size-3.5" />
          {t("common.cancel", { defaultValue: "Cancel" })}
        </Button>
        <Button
          disabled={apply.isPending || applicableCount === 0 || refusedCount > 0}
          onClick={() => apply.mutate()}
        >
          {apply.isPending
            ? t("admin.bundle.applying", { defaultValue: "Importing…" })
            : t("admin.bundle.apply", {
                total: applicableCount,
                defaultValue: "Apply {{total}} change(s)",
              })}
        </Button>
      </DialogFooter>
    </div>
  );
}

/** One section of the page. The three read as one system. */
function Panel({
  icon: Icon,
  title,
  description,
  muted = false,
  children,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  /** Dims a section that is not usable yet. */
  muted?: boolean;
  children?: ReactNode;
}) {
  return (
    <section className={cn("space-y-3 rounded-lg border p-4", muted && "opacity-70")}>
      <div className="flex items-center gap-2">
        <Icon className="size-4 shrink-0 text-muted-foreground" />
        <h2 className="font-medium">{title}</h2>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
      {children}
    </section>
  );
}

/** A labelled option. The Switch is not a native input, so it carries the name. */
function Toggle({
  checked,
  onCheckedChange,
  label,
  hint,
}: {
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
  label: string;
  hint?: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <Switch
        className="mt-0.5"
        checked={checked}
        onCheckedChange={onCheckedChange}
        aria-label={label}
      />
      <div className="space-y-1">
        <span>{label}</span>
        {hint}
      </div>
    </div>
  );
}

/** Export panel: choose what travels, then download the archive. */
function ExportPanel() {
  const { t } = useTranslation();
  const [includeFiles, setIncludeFiles] = useState(true);
  const [includeSecrets, setIncludeSecrets] = useState(false);

  return (
    <Panel
      icon={Download}
      title={t("admin.bundle.export_title", { defaultValue: "Export" })}
      description={t("admin.bundle.export_hint", {
        defaultValue:
          "Builds an archive of the authored content and downloads it. Nothing is kept on the server.",
      })}
    >
      <Toggle
        checked={includeFiles}
        onCheckedChange={setIncludeFiles}
        label={t("admin.bundle.include_files", {
          defaultValue: "Include uploaded file attachments",
        })}
      />
      <Toggle
        checked={includeSecrets}
        onCheckedChange={setIncludeSecrets}
        label={t("admin.bundle.include_secrets", {
          defaultValue: "Include secret settings",
        })}
        hint={
          includeSecrets ? (
            <p className="text-xs text-amber-600">
              {t("admin.bundle.include_secrets_warning", {
                defaultValue:
                  "Secret settings, such as the SMTP password, go into the archive in clear text. Only do this for an archive you keep yourself.",
              })}
            </p>
          ) : undefined
        }
      />

      <Button
        render={<a href={adminBundleExportUrl({ includeFiles, includeSecrets })} download />}
        title={t("admin.bundle.export_now_hint", {
          defaultValue: "Build an archive of the authored content and download it",
        })}
      >
        <Download className="size-4" />
        {t("admin.bundle.export_now", { defaultValue: "Export" })}
      </Button>
    </Panel>
  );
}

/** Import panel: pick an archive, choose pruning, ask for a plan. */
function ImportPanel({ onPlanned }: { onPlanned: (plan: BundlePlan) => void }) {
  const { t } = useTranslation();
  const [prune, setPrune] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const plan = useMutation({
    mutationFn: (file: File) => planAdminBundleImport(file, prune),
    onSuccess: onPlanned,
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.bundle.plan_error", { defaultValue: "Could not read the archive" }),
        ),
      ),
  });

  return (
    <Panel
      icon={Upload}
      title={t("admin.bundle.import_title", { defaultValue: "Import" })}
      description={t("admin.bundle.import_hint", {
        defaultValue:
          "Uploading only builds a plan. You review every change before anything is written.",
      })}
    >
      <Toggle
        checked={prune}
        onCheckedChange={setPrune}
        label={t("admin.bundle.prune", {
          defaultValue: "Delete what the archive does not carry",
        })}
      />

      <div className="flex items-center gap-3">
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          disabled={plan.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) plan.mutate(file);
          }}
        />
        <Button
          variant="outline"
          disabled={plan.isPending}
          onClick={() => fileInput.current?.click()}
        >
          <Upload className="size-4" />
          {plan.isPending
            ? t("admin.bundle.planning", { defaultValue: "Reading…" })
            : t("admin.bundle.choose_file", { defaultValue: "Choose an archive" })}
        </Button>
      </div>
    </Panel>
  );
}

/** Git sync panel. Nothing to drive yet; the panel says what will live here. */
function SyncPanel() {
  const { t } = useTranslation();
  return (
    <Panel
      muted
      icon={GitBranch}
      title={t("admin.bundle.sync_title", { defaultValue: "Git remote" })}
      description={t("admin.bundle.sync_hint", {
        defaultValue:
          "Push this instance's content to a git repository and pull it back, reviewing the same plan as an import. Runs when you ask it to, never on a timer.",
      })}
    >
      <p className="text-xs text-muted-foreground">
        {t("admin.bundle.sync_planned", {
          defaultValue: "Not available yet.",
        })}
      </p>
    </Panel>
  );
}

function BundlePage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [plan, setPlan] = useState<BundlePlan | null>(null);

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={FolderSync}
        title={t("admin.nav.bundle", { defaultValue: "Sync" })}
        badge={<BetaBadge />}
      />

      <Banner tone="blue" icon={Package}>
        {t("admin.bundle.scope_hint", {
          defaultValue:
            "An archive carries the authored content: challenges, questions, hints, flags, files, pages, links, custom fields and settings. Players, teams and solve history stay behind, so use Backups for those.",
        })}
      </Banner>

      <div className="grid gap-4 lg:grid-cols-3 items-start">
        <ExportPanel />
        <ImportPanel onPlanned={setPlan} />
        <SyncPanel />
      </div>

      <PlanReview
        plan={plan}
        onApplied={() => {
          setPlan(null);
          void queryClient.invalidateQueries();
        }}
        onClose={() => setPlan(null)}
      />
    </div>
  );
}
