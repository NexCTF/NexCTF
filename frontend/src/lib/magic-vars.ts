export interface MagicVarDoc {
  key: string;
  example: string;
}

export const MAGIC_VAR_DOCS: MagicVarDoc[] = [
  {
    key: "event_name",
    example: "NexCTF 2026",
  },
  {
    key: "event_start",
    example: "May 10, 2026, 10:00 AM",
  },
  {
    key: "event_end",
    example: "May 12, 2026, 10:00 AM",
  },
  {
    key: "countdown_to_start",
    example: "2d 3h 15m 22s",
  },
  {
    key: "countdown_to_end",
    example: "1d 6h 30m 05s",
  },
];

export function applyMagicVars(content: string, vars: Record<string, string>): string {
  return content.replace(/\{\{(\w+)\}\}/g, (match, key: string) => vars[key] || match);
}
