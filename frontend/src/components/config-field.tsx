import { useTranslation } from "react-i18next";
import { ImageUploadInput } from "@/components/image-upload-input";
import { CardDescription } from "@/components/ui/card";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { type ConfigItem, SECRET_MASK } from "@/lib/api";

function FieldWrapper({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <CardDescription className="whitespace-pre-line">{description}</CardDescription>
      {children}
    </div>
  );
}

/** Input for one config setting, chosen by its type. */
export function ConfigField({
  item,
  value,
  onChange,
  timezone,
}: {
  item: ConfigItem;
  value: string;
  onChange: (v: string) => void;
  timezone: string;
}) {
  const { t } = useTranslation();
  const label = t(item.label, { defaultValue: item.label });
  const description = t(item.description, { defaultValue: item.description });

  switch (item.type) {
    case "bool":
      return (
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-0.5">
            <Label>{label}</Label>
            <CardDescription className="whitespace-pre-line">{description}</CardDescription>
          </div>
          <Switch checked={value === "true"} onCheckedChange={(v) => onChange(String(v))} />
        </div>
      );
    case "choice":
      return (
        <FieldWrapper label={label} description={description}>
          <Select value={value} onValueChange={(v) => v && onChange(v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {item.choices.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldWrapper>
      );
    case "datetime":
      return (
        <FieldWrapper label={label} description={description}>
          <DateTimePicker value={value ?? ""} onChange={onChange} echoTimezone={timezone} />
        </FieldWrapper>
      );
    case "color":
      return (
        <FieldWrapper label={label} description={description}>
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={value || "#000000"}
              onChange={(e) => onChange(e.target.value)}
              className="h-9 w-12 cursor-pointer rounded-md border border-input bg-transparent p-0.5"
            />
            <Input
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="#RRGGBB"
              className="flex-1"
            />
          </div>
        </FieldWrapper>
      );
    case "secret": {
      // The server sends "***" when a secret is set; never show it in the
      // input or the admin can append to the mask and store it verbatim.
      const isSet = value === SECRET_MASK;
      return (
        <FieldWrapper label={label} description={description}>
          <Input
            type="password"
            autoComplete="new-password"
            value={isSet ? "" : value}
            placeholder={isSet ? "••••••••" : ""}
            onChange={(e) => onChange(e.target.value)}
          />
        </FieldWrapper>
      );
    }
    case "url":
      return (
        <FieldWrapper label={label} description={description}>
          <Input
            type="url"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="https://"
          />
        </FieldWrapper>
      );
    case "image":
      return (
        <FieldWrapper label={label} description={description}>
          <ImageUploadInput value={value} onChange={onChange} />
        </FieldWrapper>
      );
    case "text":
      return (
        <FieldWrapper label={label} description={description}>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldWrapper>
      );
    case "int":
    case "float":
      return (
        <FieldWrapper label={label} description={description}>
          <Input
            type="number"
            step={item.type === "int" ? "1" : "any"}
            min={item.min ?? undefined}
            max={item.max ?? undefined}
            value={value}
            onChange={(e) => onChange(e.target.value)}
          />
        </FieldWrapper>
      );
    default:
      return (
        <FieldWrapper label={label} description={description}>
          <Input type="text" value={value} onChange={(e) => onChange(e.target.value)} />
        </FieldWrapper>
      );
  }
}
