// ponytail: substring matching on the UA string, enough for a device label.
// Swap in a real parser only if the labels start being wrong for real users.
// Order is significant: first match wins, so narrower patterns come first.
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/Firefox\//, "Firefox"],
  [/Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const OSES: [RegExp, string][] = [
  [/Windows/, "Windows"],
  [/Android/, "Android"],
  [/iPhone|iPad|iPod/, "iOS"],
  [/Mac OS X/, "macOS"],
  [/Linux/, "Linux"],
];

const matchUa = (ua: string, table: [RegExp, string][]): string | null =>
  table.find(([re]) => re.test(ua))?.[1] ?? null;

export function describeDevice(ua: string | null): {
  browser: string | null;
  os: string | null;
  mobile: boolean;
} {
  const os = ua ? matchUa(ua, OSES) : null;
  return {
    browser: ua ? matchUa(ua, BROWSERS) : null,
    os,
    mobile: os === "Android" || os === "iOS",
  };
}

export function formatLastSeen(iso: string, locale: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, secs] of units) {
    if (seconds >= secs) return rtf.format(-Math.floor(seconds / secs), unit);
  }
  return rtf.format(-Math.max(seconds, 0), "second");
}
