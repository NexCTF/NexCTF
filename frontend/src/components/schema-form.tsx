/**
 * Schema-driven form fields, shared across challenge, solution, and scheduler forms.
 *
 * The JSON schemas come from the backend (via resolve_dynamic_defaults) and carry
 * UI hints like x-ui-options (InlineSelect) and x-ui-widget (code editor).
 */

import { Plus, Trash2 } from "lucide-react";
import { TeamMultiSelect } from "@/components/team-multi-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MarkdownEditor } from "@/components/ui/markdown-editor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { JsonSchema, JsonSchemaProperty } from "@/lib/api";

// ---------------------------------------------------------------------------
// Type helpers
// ---------------------------------------------------------------------------

export function getEffectiveType(prop: JsonSchemaProperty): string {
  if (prop.type) return prop.type;
  if (prop.anyOf) {
    const nonNull = prop.anyOf.find((t) => t.type !== "null");
    return nonNull?.type ?? "string";
  }
  return "string";
}

export function isUuidProp(prop: JsonSchemaProperty): boolean {
  return prop.format === "uuid" || (prop.anyOf?.some((t) => t.format === "uuid") ?? false);
}

function getUIWidget(prop: JsonSchemaProperty): string | undefined {
  if (prop["x-ui-widget"]) return prop["x-ui-widget"];
  if (prop.anyOf) {
    const nonNull = prop.anyOf.find((t) => t.type !== "null");
    return nonNull?.["x-ui-widget"];
  }
  return undefined;
}

function resolveRef(ref: string, defs: Record<string, JsonSchema>): JsonSchema {
  const name = ref.replace("#/$defs/", "");
  return defs[name] ?? { properties: {} };
}

function resolveItemSchema(prop: JsonSchemaProperty, defs: Record<string, JsonSchema>): JsonSchema {
  const items = prop.items ?? prop.anyOf?.find((t) => t.type === "array")?.items;
  if (!items) return { properties: {} };
  // biome-ignore lint/style/noNonNullAssertion: $ref existence confirmed by `"$ref" in items` guard
  if ("$ref" in items) return resolveRef(items.$ref!, defs);
  return items as JsonSchema;
}

// ---------------------------------------------------------------------------
// initFromSchema — build initial form values from a JSON schema
//
// Skips:
//   - keys in the `skip` set
//   - UUID / _id fields that have no x-ui-options (they are FKs, not user-editable)
//
// Pass `current` to pre-fill from an existing record.
// ---------------------------------------------------------------------------

export function initFromSchema(
  schema: JsonSchema,
  skip: Set<string> | string[] = new Set(),
  current?: Record<string, unknown>,
): Record<string, unknown> {
  const skipSet = skip instanceof Set ? skip : new Set(skip);
  const values: Record<string, unknown> = {};

  for (const [key, prop] of Object.entries(schema.properties ?? {})) {
    const hasOptions = !!prop["x-ui-options"];
    if (skipSet.has(key) || (!hasOptions && (key.endsWith("_id") || isUuidProp(prop)))) {
      continue;
    }
    if (current && key in current) {
      values[key] = current[key];
    } else if (prop.default !== undefined) {
      values[key] = prop.default;
    } else if (prop.anyOf?.some((t) => t.type === "null")) {
      values[key] = null;
    } else {
      const t = getEffectiveType(prop);
      values[key] =
        t === "boolean" ? false : t === "integer" || t === "number" ? 0 : t === "array" ? [] : "";
    }
  }
  return values;
}

// ---------------------------------------------------------------------------
// ArrayField — renders a list of items with add/remove controls
// ---------------------------------------------------------------------------

function emptyItem(itemSchema: JsonSchema): Record<string, unknown> {
  const item: Record<string, unknown> = {};
  for (const [k, p] of Object.entries(itemSchema.properties ?? {})) {
    item[k] = p.default !== undefined ? p.default : "";
  }
  return item;
}

function ArrayField({
  label,
  description,
  itemSchema,
  value,
  onChange,
}: {
  label: string;
  description?: string;
  itemSchema: JsonSchema;
  value: Record<string, unknown>[];
  onChange: (v: Record<string, unknown>[]) => void;
}) {
  const items = value ?? [];
  const isStringArray = !itemSchema.properties && itemSchema.type === "string";
  const itemProps = Object.entries(itemSchema.properties ?? {});

  function updateItem(i: number, key: string, val: unknown) {
    onChange(items.map((item, idx) => (idx === i ? { ...item, [key]: val } : item)));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <Label>{label}</Label>
          {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-6 text-xs px-2"
          onClick={() =>
            onChange([
              ...items,
              isStringArray ? ("" as unknown as Record<string, unknown>) : emptyItem(itemSchema),
            ])
          }
        >
          <Plus className="size-3" />
          Add
        </Button>
      </div>
      {items.length === 0 && <p className="text-xs text-muted-foreground py-1">No items yet.</p>}
      {isStringArray
        ? items.map((item, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: schema array items have no stable id
            <div key={i} className="flex items-center gap-2">
              <Input
                value={String(item ?? "")}
                onChange={(e) =>
                  onChange(
                    items.map((v, idx) =>
                      idx === i ? (e.target.value as unknown as Record<string, unknown>) : v,
                    ),
                  )
                }
                className="flex-1 text-sm"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 text-muted-foreground hover:text-destructive shrink-0"
                onClick={() => onChange(items.filter((_, idx) => idx !== i))}
              >
                <Trash2 className="size-3" />
              </Button>
            </div>
          ))
        : items.map((item, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: schema array items have no stable id
            <div key={i} className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">#{i + 1}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-5 text-muted-foreground hover:text-destructive"
                  onClick={() => onChange(items.filter((_, idx) => idx !== i))}
                >
                  <Trash2 className="size-3" />
                </Button>
              </div>
              {itemProps.map(([key, prop]) => (
                <div key={key} className="space-y-1">
                  <Label className="text-xs">{prop.title ?? key}</Label>
                  <Textarea
                    value={String(item[key] ?? "")}
                    onChange={(e) => updateItem(i, key, e.target.value)}
                    rows={2}
                    className="font-mono text-xs resize-y"
                  />
                </div>
              ))}
            </div>
          ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SchemaFields — render all fields of a JSON schema
//
// Props:
//   schema    — the JSON schema to render
//   skip      — field keys to omit (Set or array)
//   values    — current form values
//   onChange  — (key, value) called on each change
//   defs      — $defs from the root schema, for resolving $ref inside arrays
//   richText  — when true, "description"/"content" string fields use MarkdownEditor
//               (pass true for challenge/solution forms, leave false for scheduler)
// ---------------------------------------------------------------------------

export function SchemaFields({
  schema,
  skip,
  values,
  onChange,
  defs = {},
  richText = false,
}: {
  schema: JsonSchema;
  skip?: Set<string> | string[];
  values: Record<string, unknown>;
  onChange: (key: string, val: unknown) => void;
  defs?: Record<string, JsonSchema>;
  richText?: boolean;
}) {
  const skipSet = skip instanceof Set ? skip : new Set(skip ?? []);
  const required = new Set(schema.required ?? []);

  const entries = Object.entries(schema.properties ?? {}).filter(([k, p]) => {
    if (skipSet.has(k)) return false;
    if (p["x-ui-options"]) return true; // always show inline-select fields
    return !k.endsWith("_id") && !isUuidProp(p);
  });

  if (entries.length === 0) return null;

  return (
    <>
      {entries.map(([key, prop]) => {
        const label = prop.title ?? key;
        const t = getEffectiveType(prop);
        const req = required.has(key);

        // InlineSelect: options embedded in schema
        if (prop["x-ui-options"]) {
          // biome-ignore lint/style/noNonNullAssertion: guarded by `if (prop["x-ui-options"])` above
          const opts = prop["x-ui-options"]!;
          const strVal = values[key] != null ? String(values[key]) : "";
          const selectedLabel = opts.find((o) => o.value === strVal)?.label;
          return (
            <div key={key} className="space-y-1.5">
              <Label>
                {label}
                {req && " *"}
              </Label>
              {prop.description && (
                <p className="text-xs text-muted-foreground">{prop.description}</p>
              )}
              <Select value={strVal} onValueChange={(v) => onChange(key, v)}>
                <SelectTrigger>
                  <SelectValue placeholder={`Select ${label.toLowerCase()}…`}>
                    {selectedLabel ?? `Select ${label.toLowerCase()}…`}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {opts.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        }

        // team_ids: array of UUIDs → TeamMultiSelect
        if (key === "team_ids" && t === "array") {
          return (
            <div key={key} className="space-y-1.5">
              <Label>{label}</Label>
              {prop.description && (
                <p className="text-xs text-muted-foreground">{prop.description}</p>
              )}
              <TeamMultiSelect
                value={(values[key] as string[]) ?? []}
                onChange={(v) => onChange(key, v)}
              />
            </div>
          );
        }

        // Generic array
        if (t === "array") {
          const itemSchema = resolveItemSchema(prop, defs);
          return (
            <ArrayField
              key={key}
              label={label}
              description={prop.description}
              itemSchema={itemSchema}
              value={(values[key] as Record<string, unknown>[]) ?? []}
              onChange={(v) => onChange(key, v)}
            />
          );
        }

        // Boolean → Switch
        if (t === "boolean") {
          return (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border px-3 py-2.5"
            >
              <div>
                <p className="text-sm font-medium">{label}</p>
                {prop.description && (
                  <p className="text-xs text-muted-foreground mt-0.5">{prop.description}</p>
                )}
              </div>
              <Switch checked={Boolean(values[key])} onCheckedChange={(v) => onChange(key, v)} />
            </div>
          );
        }

        // Enum → Select
        if (prop.enum) {
          const strVal = String(values[key] ?? prop.enum[0] ?? "");
          return (
            <div key={key} className="space-y-1.5">
              <Label>
                {label}
                {req && " *"}
              </Label>
              {prop.description && (
                <p className="text-xs text-muted-foreground">{prop.description}</p>
              )}
              <Select value={strVal} onValueChange={(v) => onChange(key, v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {prop.enum.map((opt) => (
                    <SelectItem key={String(opt)} value={String(opt)}>
                      {String(opt)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        }

        // Number/integer → Input[number]
        if (t === "integer" || t === "number") {
          return (
            <div key={key} className="space-y-1.5">
              <Label>
                {label}
                {req && " *"}
              </Label>
              {prop.description && (
                <p className="text-xs text-muted-foreground">{prop.description}</p>
              )}
              <Input
                type="number"
                value={values[key] === null || values[key] === undefined ? "" : String(values[key])}
                onChange={(e) =>
                  onChange(key, e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>
          );
        }

        // String: code widget, long text, or plain input
        const isCode = getUIWidget(prop) === "code";
        const isLong = key === "description" || key === "content";
        const strVal = values[key] === null || values[key] === undefined ? "" : String(values[key]);

        return (
          <div key={key} className="space-y-1.5">
            <Label>
              {label}
              {req && " *"}
            </Label>
            {prop.description && (
              <p className="text-xs text-muted-foreground">{prop.description}</p>
            )}
            {isCode ? (
              <Textarea
                value={strVal}
                onChange={(e) => onChange(key, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Tab") {
                    e.preventDefault();
                    const el = e.currentTarget;
                    const start = el.selectionStart;
                    const end = el.selectionEnd;
                    const next = `${strVal.substring(0, start)}    ${strVal.substring(end)}`;
                    onChange(key, next);
                    requestAnimationFrame(() => {
                      el.selectionStart = el.selectionEnd = start + 4;
                    });
                  }
                }}
                className="font-mono text-xs resize-y"
                rows={12}
                spellCheck={false}
                required={req}
              />
            ) : isLong && richText ? (
              <MarkdownEditor rows={3} value={strVal} onChange={(v) => onChange(key, v || null)} />
            ) : isLong ? (
              <Textarea
                rows={3}
                value={strVal}
                onChange={(e) => onChange(key, e.target.value)}
                required={req}
              />
            ) : (
              <Input
                value={strVal}
                onChange={(e) => onChange(key, e.target.value)}
                required={req}
              />
            )}
          </div>
        );
      })}
    </>
  );
}
