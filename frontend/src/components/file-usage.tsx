import { useNavigate } from "@tanstack/react-router";
import { Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { FileUsage, FileUsageKind } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Translated name of the place a file is used. */
export function useUsageKindLabel(): (kind: FileUsageKind) => string {
  const { t } = useTranslation();
  return (kind) => {
    switch (kind) {
      case "challenge":
        return t("files.usage.challenge", { defaultValue: "Challenge file" });
      case "question":
        return t("files.usage.question", { defaultValue: "Question file" });
      case "challenge_text":
        return t("files.usage.challenge_text", { defaultValue: "Challenge text" });
      case "question_text":
        return t("files.usage.question_text", { defaultValue: "Question text" });
      case "hint_text":
        return t("files.usage.hint_text", { defaultValue: "Hint" });
      case "page_text":
        return t("files.usage.page_text", { defaultValue: "Page" });
      case "notification_text":
        return t("files.usage.notification_text", { defaultValue: "Notification" });
      case "config":
        return t("files.usage.config", { defaultValue: "Setting" });
    }
  };
}

/** One line per usage, for a tooltip. */
export function useUsageSummary(): (usages: FileUsage[]) => string {
  const kindLabel = useUsageKindLabel();
  return (usages) => usages.map((u) => `${kindLabel(u.kind)}: ${u.label}`).join("\n");
}

function useUsageNavigation(): (usage: FileUsage) => void {
  const navigate = useNavigate();
  return (usage) => {
    if (usage.challenge_id) {
      void navigate({
        to: "/admin/challenges/$challengeId",
        params: { challengeId: usage.challenge_id },
      });
    } else if (usage.kind === "page_text" && usage.target_id) {
      void navigate({ to: "/admin/pages/$pageId", params: { pageId: usage.target_id } });
    } else if (usage.kind === "notification_text") {
      void navigate({ to: "/admin/notifications" });
    } else if (usage.kind === "config") {
      void navigate({ to: "/admin/settings" });
    }
  };
}

/** Count of a file's usages, opening a menu that jumps to each one. */
export function FileUsageBadge({ usages }: { usages: FileUsage[] }) {
  const { t } = useTranslation();
  const kindLabel = useUsageKindLabel();
  const go = useUsageNavigation();

  if (usages.length === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        {t("files.usage.unused", { defaultValue: "Unused" })}
      </span>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-6 gap-1 px-2 text-xs")}
      >
        <Link2 className="size-3" />
        {t("files.usage.count", { n: usages.length, defaultValue: "Used ({{n}})" })}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-auto max-w-sm">
        {usages.map((u) => (
          <DropdownMenuItem key={`${u.kind}:${u.target_id ?? u.label}`} onClick={() => go(u)}>
            <span className="text-muted-foreground">{kindLabel(u.kind)}</span>
            <span className="truncate">{u.label}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
