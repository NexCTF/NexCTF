/**
 * DateTimePicker
 *
 * Wraps a single native datetime-local input, rendered in the user's local
 * timezone. The parent receives UTC ISO strings back, so no conversion is
 * needed at the call site.
 *
 * Why local time?  The user thinks in local time; the backend stores UTC.
 * We convert transparently here so neither side has to worry about it.
 */

import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toLocalValue(utcIso: string): string {
  if (!utcIso) return "";
  const d = new Date(utcIso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return `${date}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalValue(local: string): string {
  if (!local) return "";
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString();
}

function localTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function formatIn(utcIso: string, timeZone: string): string | null {
  const d = new Date(utcIso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    timeZone,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DateTimePickerProps {
  /** UTC ISO string, or empty string when unset */
  value: string;
  /** Called with a UTC ISO string on every change */
  onChange: (utcIso: string) => void;
  label?: string;
  /** IANA zone to echo the value in, alongside UTC. Omit to show no echo. */
  echoTimezone?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export function DateTimePicker({
  value,
  onChange,
  label,
  echoTimezone,
  required,
  disabled,
  className,
}: DateTimePickerProps) {
  const { t } = useTranslation();
  const id = useId();
  const zone = localTimezone();
  const utcEcho = value ? formatIn(value, "UTC") : null;
  const eventEcho =
    value && echoTimezone && echoTimezone !== "UTC" ? formatIn(value, echoTimezone) : null;

  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <Label htmlFor={id}>
          {label}
          {required && " *"}
        </Label>
      )}
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="datetime-local"
          value={toLocalValue(value)}
          onChange={(e) => onChange(fromLocalValue(e.target.value))}
          required={required}
          disabled={disabled}
          className="w-auto flex-1"
        />
        <span className="text-xs text-muted-foreground shrink-0">{zone}</span>
      </div>
      {utcEcho && (
        <p className="text-xs text-muted-foreground">
          {t("datetime.echo_utc", { time: utcEcho, defaultValue: "= {{time}} UTC" })}
          {eventEcho &&
            t("datetime.echo_event", {
              time: eventEcho,
              zone: echoTimezone,
              defaultValue: " · {{time}} {{zone}} (scheduler timezone)",
            })}
        </p>
      )}
    </div>
  );
}
