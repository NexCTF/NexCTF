/**
 * DateTimePicker
 *
 * Splits a UTC ISO string into separate date + time inputs rendered in the
 * user's local timezone. The parent receives UTC ISO strings back, so no
 * conversion is needed at the call site.
 *
 * Why local time?  The user thinks in local time; the backend stores UTC.
 * We convert transparently here so neither side has to worry about it.
 */

import { useId } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toLocalParts(utcIso: string): { date: string; time: string } {
  if (!utcIso) return { date: "", time: "" };
  const d = new Date(utcIso);
  if (Number.isNaN(d.getTime())) return { date: "", time: "" };
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

function fromLocalParts(date: string, time: string): string {
  if (!date) return "";
  return new Date(`${date}T${time || "00:00"}`).toISOString();
}

function localTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
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
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export function DateTimePicker({
  value,
  onChange,
  label,
  required,
  disabled,
  className,
}: DateTimePickerProps) {
  const id = useId();
  const { date, time } = toLocalParts(value);

  function handleDate(newDate: string) {
    onChange(fromLocalParts(newDate, time));
  }

  function handleTime(newTime: string) {
    onChange(fromLocalParts(date, newTime));
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <Label htmlFor={`${id}-date`}>
          {label}
          {required && " *"}
        </Label>
      )}
      <div className="flex items-center gap-2">
        <Input
          id={`${id}-date`}
          type="date"
          value={date}
          onChange={(e) => handleDate(e.target.value)}
          required={required}
          disabled={disabled}
          className="w-auto flex-1"
        />
        <Input
          id={`${id}-time`}
          type="time"
          value={time}
          onChange={(e) => handleTime(e.target.value)}
          disabled={disabled || !date}
          className="w-32 shrink-0"
        />
        <span className="text-xs text-muted-foreground shrink-0">{localTimezone()}</span>
      </div>
    </div>
  );
}
