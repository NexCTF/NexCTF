import { Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Link } from "@/lib/api";

interface LinksFormSectionProps {
  links: Link[];
  onChange: (links: Link[]) => void;
}

export function LinksFormSection({ links, onChange }: LinksFormSectionProps) {
  const { t } = useTranslation();

  function add() {
    onChange([...links, { label: "", url: "" }]);
  }

  function remove(i: number) {
    onChange(links.filter((_, idx) => idx !== i));
  }

  function update(i: number, patch: Partial<Link>) {
    onChange(links.map((lnk, idx) => (idx === i ? { ...lnk, ...patch } : lnk)));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{t("admin.teams.field_links")}</Label>
        <Button type="button" variant="outline" size="sm" onClick={add}>
          <Plus className="size-3.5 mr-1" />
          {t("admin.teams.add_link")}
        </Button>
      </div>
      {links.map((lnk, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: links have no stable id; index is the identity
        <div key={i} className="flex gap-2 items-center">
          <Input
            value={lnk.label}
            onChange={(e) => update(i, { label: e.target.value })}
            placeholder={t("admin.teams.link_label_placeholder")}
            className="w-32 shrink-0"
          />
          <Input
            value={lnk.url}
            onChange={(e) => update(i, { url: e.target.value })}
            placeholder="https://..."
            type="url"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 text-destructive hover:text-destructive"
            onClick={() => remove(i)}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      ))}
    </div>
  );
}
