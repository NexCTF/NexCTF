import { type KeyboardEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { LabelInput } from "@/components/label-input";
import { TagBadge } from "@/components/tag-badge";
import { normaliseLabel } from "@/lib/utils";

interface TagMultiSelectProps {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions?: string[];
}

/** Free-text tag entry: type to create, pick from existing values, Enter to add. */
export function TagMultiSelect({ value, onChange, suggestions = [] }: TagMultiSelectProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");

  function add(raw: string) {
    const tag = normaliseLabel(raw);
    if (tag && !value.includes(tag)) onChange([...value, tag]);
    setDraft("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="space-y-2">
      <LabelInput
        value={draft}
        placeholder={t("admin.tags.input_placeholder")}
        noun={t("admin.labels.noun_tag")}
        suggestions={suggestions.filter((s) => !value.includes(s))}
        onValueChange={setDraft}
        onPick={add}
        onKeyDown={onKeyDown}
        onBlur={() => add(draft)}
      />

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <TagBadge
              key={tag}
              tag={tag}
              removeLabel={t("admin.tags.remove", { name: tag })}
              onRemove={() => onChange(value.filter((v) => v !== tag))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
