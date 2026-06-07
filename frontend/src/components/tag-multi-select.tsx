import { Popover } from "@base-ui/react/popover";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getAdminTags, type Tag } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TagMultiSelectProps {
  value: string[];
  onChange: (ids: string[]) => void;
}

export function TagMultiSelect({ value, onChange }: TagMultiSelectProps) {
  const { t } = useTranslation();
  const { data: resp } = useQuery({
    queryKey: ["admin", "tags"],
    queryFn: () => getAdminTags("items_per_page=100"),
    staleTime: 30_000,
  });
  const allTags = resp?.data ?? [];

  const tagMap = Object.fromEntries(allTags.map((t) => [t.id, t]));

  function toggle(tag: Tag) {
    if (value.includes(tag.id)) {
      onChange(value.filter((id) => id !== tag.id));
    } else {
      onChange([...value, tag.id]);
    }
  }

  function remove(id: string) {
    onChange(value.filter((v) => v !== id));
  }

  const triggerLabel =
    value.length === 0
      ? t("admin.tags.select_placeholder")
      : t("admin.tags.n_selected", { count: value.length });

  return (
    <div className="space-y-2">
      <Popover.Root>
        <Popover.Trigger
          className={cn(
            "flex h-8 w-full items-center justify-between rounded-lg border border-input bg-transparent px-2.5 text-sm transition-colors outline-none",
            "hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
            value.length === 0 && "text-muted-foreground",
          )}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronDown className="size-4 shrink-0 opacity-50" />
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Positioner className="z-50 w-[var(--anchor-width)] min-w-56">
            <Popover.Popup className="w-full rounded-lg border bg-popover text-popover-foreground shadow-md outline-none data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0">
              <div className="max-h-52 overflow-y-auto py-1">
                {allTags.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    {t("admin.tags.no_tags")}
                  </p>
                ) : (
                  allTags.map((tag) => {
                    const selected = value.includes(tag.id);
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        onClick={() => toggle(tag)}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted/60 transition-colors"
                      >
                        <span
                          className={cn(
                            "flex size-4 shrink-0 items-center justify-center rounded-sm border",
                            selected
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-input",
                          )}
                        >
                          {selected && <Check className="size-3" />}
                        </span>
                        <span
                          className="size-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: tag.color }}
                        />
                        {tag.name}
                      </button>
                    );
                  })
                )}
              </div>
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((id) => {
            const tag = tagMap[id];
            return (
              <span
                key={id}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
                style={{ backgroundColor: tag?.color ?? "#6b7280" }}
              >
                {tag?.name ?? id}
                <button
                  type="button"
                  onClick={() => remove(id)}
                  className="opacity-70 hover:opacity-100 transition-opacity"
                >
                  <X className="size-3" />
                </button>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
