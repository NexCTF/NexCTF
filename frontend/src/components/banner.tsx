const TONES = {
  amber: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  yellow: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  zinc: "border-zinc-500/30 bg-zinc-500/10 text-zinc-400",
  blue: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

/** Inline notice strip. */
export function Banner({
  tone,
  icon: Icon,
  children,
}: {
  tone: keyof typeof TONES;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${TONES[tone]}`}>
      <Icon className="size-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
