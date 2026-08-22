import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { DATE_FORMAT } from "@/components/table-cells";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, getAdminSchedulerCronNext } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Cron expression field with a live preview of the next fire times. */
export function CronInput({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const [debounced, setDebounced] = useState(value.trim());

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value.trim()), 400);
    return () => clearTimeout(timer);
  }, [value]);

  // A cron expression is 5 or 6 fields; anything shorter is still being typed.
  const complete = /^\S+(\s+\S+){4,5}$/.test(debounced);
  const { data: preview, error } = useQuery({
    queryKey: ["admin", "scheduler", "cron", debounced],
    queryFn: () => getAdminSchedulerCronNext(debounced),
    enabled: complete,
    retry: false,
  });

  function message(): { tone: string; text: string } | null {
    if (!debounced)
      return {
        tone: "text-muted-foreground",
        text: t("admin.scheduler.cron_hint", {
          defaultValue:
            "Leave empty for a job that fires once. Schedules are read in the event timezone (Settings → Competition).",
        }),
      };
    if (!complete) return null;
    if (error)
      return error instanceof ApiError && error.status === 422
        ? {
            tone: "text-destructive",
            text: t("admin.scheduler.cron_invalid", {
              defaultValue: "Invalid cron expression.",
            }),
          }
        : {
            tone: "text-muted-foreground",
            text: t("admin.scheduler.cron_check_failed", {
              defaultValue: "Could not check this expression right now.",
            }),
          };
    if (!preview) return null;
    return {
      tone: "text-muted-foreground",
      text: t("admin.scheduler.cron_preview", {
        zone: preview.timezone,
        runs: preview.next_runs.map((f) => DATE_FORMAT.format(new Date(f))).join(", "),
        defaultValue: "Read in {{zone}} · next runs, in your timezone: {{runs}}",
      }),
    };
  }

  const hint = message();

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {t("admin.scheduler.field_cron", { defaultValue: "Repeat (cron)" })}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0 0 * * *"
        className="font-mono"
      />
      {hint && <p className={cn("text-xs", hint.tone)}>{hint.text}</p>}
    </div>
  );
}
