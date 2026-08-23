const TONES = {
  green: "border-green-500/40 bg-green-500/10 text-green-600 dark:text-green-400",
  red: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
  amber: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

/** Small inline pill: optional icon plus a label, tinted by tone. */
export function StatusBadge({
  tone,
  icon: Icon,
  title,
  children,
}: {
  tone: keyof typeof TONES;
  icon?: React.ElementType;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      title={title}
      className={`shrink-0 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs tabular-nums ${TONES[tone]}`}
    >
      {Icon && <Icon className="size-3" />}
      {children}
    </span>
  );
}
