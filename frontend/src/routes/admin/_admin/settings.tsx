import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import * as LucideIcons from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
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
import { type ConfigItem, getConfig, updateConfig } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/settings")({
  component: SettingsPage,
});

function toStringMap(items: ConfigItem[]): Record<string, string> {
  const m: Record<string, string> = {};
  for (const item of items) m[item.key] = String(item.value);
  return m;
}

function SettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: getConfig,
  });

  const baselineJson = useMemo(() => JSON.stringify(toStringMap(items)), [items]);
  const baseline = useMemo(
    () => JSON.parse(baselineJson) as Record<string, string>,
    [baselineJson],
  );
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  // biome-ignore lint/correctness/useExhaustiveDependencies: setOverrides is stable, baselineJson triggers the reset
  useEffect(() => {
    setOverrides({});
  }, [baselineJson]);

  function getValue(key: string) {
    return key in overrides ? overrides[key] : (baseline[key] ?? "");
  }

  const dirtyKeys = Object.keys(overrides).filter((k) => overrides[k] !== baseline[k]);
  const isDirty = dirtyKeys.length > 0;

  const mutation = useMutation({
    mutationFn: (changed: Record<string, string>) => updateConfig(changed),
    onSuccess: (updatedItems) => {
      qc.setQueryData(["config"], updatedItems);
      setOverrides({});
      toast.success(t("common.saved"));
    },
  });

  function setValue(key: string, value: string) {
    setOverrides((prev) => ({ ...prev, [key]: value }));
  }

  function handleSave() {
    const changed: Record<string, string> = {};
    for (const key of dirtyKeys) changed[key] = overrides[key];
    mutation.mutate(changed);
  }

  // Build ordered category map
  const categories = useMemo(() => {
    const map = new Map<
      string,
      {
        label: string;
        icon: string | null;
        section: string;
        items: ConfigItem[];
      }
    >();
    for (const item of items) {
      if (!map.has(item.category)) {
        map.set(item.category, {
          label: item.category_label,
          icon: item.category_icon,
          section: item.category_section,
          items: [],
        });
      }
      // biome-ignore lint/style/noNonNullAssertion: key inserted just above in the same loop
      map.get(item.category)!.items.push(item);
    }
    return map;
  }, [items]);

  const categoryKeys = Array.from(categories.keys());
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const currentCategory = activeCategory ?? categoryKeys[0] ?? null;

  // Which categories have unsaved changes
  const dirtyCategorySet = useMemo(() => {
    const s = new Set<string>();
    for (const key of dirtyKeys) {
      const item = items.find((i) => i.key === key);
      if (item) s.add(item.category);
    }
    return s;
  }, [dirtyKeys, items]);

  // Group by section for tab separators
  const sections = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const [slug, meta] of categories) {
      if (!map.has(meta.section)) map.set(meta.section, []);
      // biome-ignore lint/style/noNonNullAssertion: key inserted just above in the same loop
      map.get(meta.section)!.push(slug);
    }
    return map;
  }, [categories]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  const currentMeta = currentCategory ? categories.get(currentCategory) : null;
  const currentItems = currentMeta?.items ?? [];

  return (
    <div className="flex flex-col flex-1">
      {/* Header */}
      <div className="border-b px-8 pt-6 pb-0">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">{t("config.title")}</h1>
          <Button onClick={handleSave} disabled={!isDirty || mutation.isPending}>
            {mutation.isPending ? t("common.saving") : t("common.save")}
          </Button>
        </div>

        {/* Tab bar */}
        <div className="flex items-end gap-0 -mb-px">
          {Array.from(sections.entries()).map(([sectionSlug, catSlugs], sectionIdx) => (
            <div key={sectionSlug} className="flex items-end">
              {/* Separator between sections */}
              {sectionIdx > 0 && <div className="mx-2 mb-2 h-4 w-px bg-border self-center" />}
              {catSlugs.map((slug) => {
                // biome-ignore lint/style/noNonNullAssertion: slug comes from categories.keys()
                const meta = categories.get(slug)!;
                const isActive = currentCategory === slug;
                const isDirtyTab = dirtyCategorySet.has(slug);
                return (
                  <button
                    type="button"
                    key={slug}
                    onClick={() => setActiveCategory(slug)}
                    className={cn(
                      "relative flex items-center gap-1.5 px-4 py-2 text-sm transition-colors border-b-2",
                      isActive
                        ? "border-primary text-foreground font-medium"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <CategoryIcon name={meta.icon} />
                    {t(meta.label, { defaultValue: meta.label })}
                    {isDirtyTab && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 px-8 py-8 max-w-2xl space-y-6">
        {currentMeta && (
          <Card>
            <CardContent className="pt-6 space-y-6">
              {currentItems.map((item) => (
                <ConfigField
                  key={item.key}
                  item={item}
                  value={getValue(item.key)}
                  onChange={(v) => setValue(item.key, v)}
                />
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function CategoryIcon({ name }: { name: string | null }) {
  if (!name) return null;
  const pascal = name
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join("");
  const Icon = (LucideIcons as Record<string, unknown>)[pascal] as
    | React.FC<{ className?: string }>
    | undefined;
  if (!Icon) return null;
  return <Icon className="h-3.5 w-3.5 shrink-0" />;
}

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
      <CardDescription>{description}</CardDescription>
      {children}
    </div>
  );
}

function ConfigField({
  item,
  value,
  onChange,
}: {
  item: ConfigItem;
  value: string;
  onChange: (v: string) => void;
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
            <CardDescription>{description}</CardDescription>
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
          <DateTimePicker value={value ?? ""} onChange={onChange} />
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
      return (
        <FieldWrapper label={label} description={description}>
          <Input type="number" step="1" value={value} onChange={(e) => onChange(e.target.value)} />
        </FieldWrapper>
      );
    case "float":
      return (
        <FieldWrapper label={label} description={description}>
          <Input
            type="number"
            step="any"
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
