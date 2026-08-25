import { Input } from "@/components/ui/input";
import type { CustomFieldDefinition } from "@/lib/api";

interface CustomFieldInputProps {
  id?: string;
  fieldType: CustomFieldDefinition["field_type"];
  value: string;
  onChange: (value: string) => void;
}

export function CustomFieldInput({ id, fieldType, value, onChange }: CustomFieldInputProps) {
  if (fieldType === "boolean") {
    return (
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
      >
        <option value="">—</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }
  return (
    <Input
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      type={fieldType === "url" ? "url" : fieldType === "integer" ? "number" : "text"}
    />
  );
}
