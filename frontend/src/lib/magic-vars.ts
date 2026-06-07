export interface MagicVarDoc {
  key: string;
  labelKey: string;
  descKey: string;
  example: string;
}

export const MAGIC_VAR_DOCS: MagicVarDoc[] = [
  {
    key: "event_name",
    labelKey: "pages.magic.event_name_label",
    descKey: "pages.magic.event_name_desc",
    example: "NexCTF 2026",
  },
  {
    key: "event_start",
    labelKey: "pages.magic.event_start_label",
    descKey: "pages.magic.event_start_desc",
    example: "May 10, 2026, 10:00 AM",
  },
  {
    key: "event_end",
    labelKey: "pages.magic.event_end_label",
    descKey: "pages.magic.event_end_desc",
    example: "May 12, 2026, 10:00 AM",
  },
  {
    key: "countdown_to_start",
    labelKey: "pages.magic.countdown_start_label",
    descKey: "pages.magic.countdown_start_desc",
    example: "2d 3h 15m 22s",
  },
  {
    key: "countdown_to_end",
    labelKey: "pages.magic.countdown_end_label",
    descKey: "pages.magic.countdown_end_desc",
    example: "1d 6h 30m 05s",
  },
];

export function applyMagicVars(content: string, vars: Record<string, string>): string {
  return content.replace(/\{\{(\w+)\}\}/g, (match, key: string) => vars[key] || match);
}
