import { Autocomplete } from "@base-ui/react/autocomplete";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { normaliseLabel } from "@/lib/utils";

interface LabelInputProps extends Omit<React.ComponentProps<typeof Input>, "value" | "onChange"> {
  value: string;
  onValueChange: (value: string) => void;
  /** Called instead of onValueChange when an existing value is picked from the list. */
  onPick?: (value: string) => void;
  suggestions?: string[];
  /** What this field holds, for the "will be created" hint (e.g. "category"). */
  noun: string;
}

/** Free-text label entry: type to create, or pick an existing value. */
export function LabelInput({
  value,
  onValueChange,
  onPick,
  suggestions = [],
  noun,
  onBlur,
  ...props
}: LabelInputProps) {
  const { t } = useTranslation();
  const draft = normaliseLabel(value);

  return (
    <Autocomplete.Root
      items={suggestions}
      value={value}
      onValueChange={(v, details) =>
        details.reason === "item-press" && onPick ? onPick(v) : onValueChange(v)
      }
      openOnInputClick
    >
      <Autocomplete.Input
        render={
          <Input
            {...props}
            className={props.className ? `${props.className} capitalize` : "capitalize"}
            onBlur={(e) => {
              onValueChange(draft);
              onBlur?.(e);
            }}
          />
        }
      />
      <Autocomplete.Portal>
        <Autocomplete.Positioner className="z-50 w-[var(--anchor-width)] min-w-44" sideOffset={4}>
          <Autocomplete.Popup className="w-full rounded-lg border bg-popover text-popover-foreground shadow-md outline-none">
            <Autocomplete.Empty className="px-3 py-2 text-xs text-muted-foreground empty:p-0">
              {draft && t("admin.labels.will_create", { noun, value: draft })}
            </Autocomplete.Empty>
            <Autocomplete.List className="max-h-52 overflow-y-auto py-1">
              {(item: string) => (
                <Autocomplete.Item
                  key={item}
                  value={item}
                  className="w-full cursor-default px-3 py-1.5 text-sm capitalize transition-colors data-[highlighted]:bg-muted/60"
                >
                  {item}
                </Autocomplete.Item>
              )}
            </Autocomplete.List>
          </Autocomplete.Popup>
        </Autocomplete.Positioner>
      </Autocomplete.Portal>
    </Autocomplete.Root>
  );
}
