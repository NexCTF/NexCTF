import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MarkdownEditor, type MarkdownEditorHandle } from "@/components/ui/markdown-editor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { apiErrorMessage, getAdminPage, updateAdminPage } from "@/lib/api";
import { MAGIC_VAR_DOCS } from "@/lib/magic-vars";

export const Route = createFileRoute("/admin/_admin/pages_/$pageId")({
  component: PageEditorPage,
});

// ---------------------------------------------------------------------------
// Editor with magic variable helpers
// ---------------------------------------------------------------------------

function PageContentEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  const editorRef = useRef<MarkdownEditorHandle>(null);

  return (
    <div className="space-y-2">
      <Label>{t("admin.pages.field_content", { defaultValue: "Content" })}</Label>
      <details className="text-xs border rounded-md">
        <summary className="px-3 py-1.5 cursor-pointer text-muted-foreground hover:text-foreground select-none">
          {t("admin.pages.available_variables", { defaultValue: "Available variables" })}
        </summary>
        <div className="px-3 pb-3 pt-1 grid grid-cols-1 gap-1.5">
          {MAGIC_VAR_DOCS.map((v) => (
            <div key={v.key} className="flex items-baseline gap-2">
              <button
                type="button"
                className="font-mono bg-muted px-1 py-0.5 rounded text-xs shrink-0 cursor-pointer hover:bg-muted/70"
                onClick={() => editorRef.current?.insert(`{{${v.key}}}`)}
                title={t("admin.pages.click_to_insert", { defaultValue: "Click to insert" })}
              >
                {`{{${v.key}}}`}
              </button>
              <span className="text-muted-foreground">{v.example}</span>
            </div>
          ))}
        </div>
      </details>
      <MarkdownEditor ref={editorRef} value={value} onChange={onChange} rows={20} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page editor
// ---------------------------------------------------------------------------

const NAV_NONE = "__none__";

const NAV_LABELS: Record<string, string> = {
  [NAV_NONE]: "None",
  footer: "Footer",
  nav: "Top nav",
};

function PageEditorPage() {
  const { t } = useTranslation();
  const { pageId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: page, isLoading } = useQuery({
    queryKey: ["admin", "page", pageId],
    queryFn: () => getAdminPage(pageId),
  });

  const [title, setTitle] = useState<string | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [isPublished, setIsPublished] = useState<boolean | null>(null);
  const [navPlacement, setNavPlacement] = useState<string | null | undefined>(undefined);

  const effectiveTitle = title ?? page?.title ?? "";
  const effectiveSlug = slug ?? page?.slug ?? "";
  const effectiveContent = content ?? page?.content ?? "";
  const effectivePublished = isPublished ?? page?.is_published ?? false;
  const effectiveNav = navPlacement !== undefined ? navPlacement : (page?.nav_placement ?? null);

  const mutation = useMutation({
    mutationFn: () =>
      updateAdminPage(pageId, {
        title: effectiveTitle,
        slug: effectiveSlug,
        content: effectiveContent,
        is_published: effectivePublished,
        nav_placement: (effectiveNav === NAV_NONE ? null : effectiveNav) as "footer" | "nav" | null,
      }),
    onSuccess: () => {
      toast.success(t("admin.pages.saved", { defaultValue: "Page saved" }));
      void queryClient.invalidateQueries({ queryKey: ["admin", "page", pageId] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "pages"] });
      void queryClient.invalidateQueries({ queryKey: ["published-pages"] });
      void queryClient.invalidateQueries({ queryKey: ["page", effectiveSlug] });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.pages.save_error", { defaultValue: "Save failed" })),
      ),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground">{t("common.loading", { defaultValue: "Loading…" })}</p>
      </div>
    );
  }

  if (!page) return null;

  const navValue = effectiveNav === null ? NAV_NONE : (effectiveNav ?? NAV_NONE);

  return (
    <div className="p-8 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate({ to: "/admin/pages" })}>
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="text-2xl font-bold truncate">{effectiveTitle || page.title}</h1>
      </div>

      {/* Meta fields */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="page-title">
            {t("admin.pages.field_title", { defaultValue: "Title" })}
          </Label>
          <Input
            id="page-title"
            value={effectiveTitle}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="page-slug">{t("admin.pages.field_slug", { defaultValue: "Slug" })}</Label>
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none select-none">
              /p/
            </span>
            <Input
              id="page-slug"
              value={effectiveSlug}
              onChange={(e) => setSlug(e.target.value)}
              pattern="[a-z0-9-]+"
              className="pl-10"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {t("admin.pages.home_hint", {
              defaultValue: "Use slug 'home' to customize the index page.",
            })}
          </p>
        </div>
      </div>

      {/* Settings row */}
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-2">
          <Switch
            id="is-published"
            checked={effectivePublished}
            onCheckedChange={(v) => setIsPublished(v)}
          />
          <Label htmlFor="is-published">
            {t("admin.pages.field_published", { defaultValue: "Published" })}
          </Label>
        </div>

        <div className="flex items-center gap-2">
          <Label>{t("admin.pages.field_nav", { defaultValue: "Show in navigation" })}</Label>
          <Select
            value={navValue}
            onValueChange={(v) => setNavPlacement(v === NAV_NONE ? null : v)}
          >
            <SelectTrigger className="w-36">
              <SelectValue>{NAV_LABELS[navValue]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NAV_NONE}>
                {t("admin.pages.nav_none", { defaultValue: "None" })}
              </SelectItem>
              <SelectItem value="footer">
                {t("admin.pages.nav_footer", { defaultValue: "Footer" })}
              </SelectItem>
              <SelectItem value="nav">
                {t("admin.pages.nav_top", { defaultValue: "Top nav" })}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content editor */}
      <PageContentEditor value={effectiveContent} onChange={setContent} />

      {/* Save */}
      <div className="flex items-center gap-3 pt-2">
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? t("common.saving") : t("common.save", { defaultValue: "Save" })}
        </Button>
        {effectivePublished && (
          <a
            href={`/p/${encodeURIComponent(effectiveSlug)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {t("admin.pages.view_live", { defaultValue: "View live →" })}
          </a>
        )}
      </div>
    </div>
  );
}
