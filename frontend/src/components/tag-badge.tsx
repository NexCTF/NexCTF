import { X } from "lucide-react";

interface TagBadgeProps {
  tag: string;
  /** When both are given, the badge renders a remove button. */
  onRemove?: () => void;
  removeLabel?: string;
}

export function TagBadge({ tag, onRemove, removeLabel }: TagBadgeProps) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground capitalize">
      {tag}
      {onRemove && (
        <button
          type="button"
          aria-label={removeLabel}
          onClick={onRemove}
          className="opacity-70 hover:opacity-100 transition-opacity"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  );
}
