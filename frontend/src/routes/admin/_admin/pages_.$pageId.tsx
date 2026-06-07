import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Image, Link2 } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import {
  apiErrorMessage,
  getAdminFiles,
  getAdminPage,
  markFilePublic,
  type StoredFile,
  updateAdminPage,
} from "@/lib/api";
import { MAGIC_VAR_DOCS } from "@/lib/magic-vars";
import { formatBytes } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/pages_/$pageId")({
  component: PageEditorPage,
});

// ---------------------------------------------------------------------------
// File picker — lets admin insert an image/file URL into the markdown
// ---------------------------------------------------------------------------

function FilePicker({ onInsert }: { onInsert: (markdown: string) => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data: filesResponse } = useQuery({
    queryKey: ["admin", "files", "picker", search],
    queryFn: () => getAdminFiles(search ? `search=${encodeURIComponent(search)}` : ""),
    enabled: open,
  });

  const markPublicMutation = useMutation({
    mutationFn: (fileId: string) => markFilePublic(fileId, true),
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.pages.make_public_error", { defaultValue: "Failed to make file public" }),
        ),
      ),
  });

  async function handlePick(file: StoredFile) {
    if (!file.is_public) {
      try {
        await markPublicMutation.mutateAsync(file.id);
      } catch {
        return;
      }
    }
    const url = `/api/v1/file/${file.id}/view`;
    const isImage = file.mime_type?.startsWith("image/");
    const md = isImage ? `![${file.name}](${url})` : `[${file.name}](${url})`;
    onInsert(md);
    setOpen(false);
    setSearch("");
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button type="button" variant="outline" size="sm">
            <Image className="size-3.5 mr-1.5" />
            {t("admin.pages.insert_file", { defaultValue: "Insert file" })}
          </Button>
        }
      />
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {t("admin.pages.pick_file", { defaultValue: "Pick a file to insert" })}
          </DialogTitle>
        </DialogHeader>
        <Input
          placeholder={t("common.search", { defaultValue: "Search…" })}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mb-2"
        />
        <div className="max-h-80 overflow-y-auto divide-y rounded border">
          {!filesResponse?.data?.length ? (
            <p className="p-4 text-sm text-muted-foreground text-center">
              {t("admin.pages.no_files", {
                defaultValue: "No files found. Upload files first in the Files section.",
              })}
            </p>
          ) : (
            filesResponse.data.map((file) => (
              <button
                key={file.id}
                type="button"
                className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-muted/60 transition-colors"
                onClick={() => handlePick(file)}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">
                    {file.original_filename}
                  </p>
                  {file.mime_type && (
                    <p className="text-xs text-muted-foreground">
                      {file.mime_type}
                      {file.file_size ? ` · ${formatBytes(file.file_size)}` : ""}
                      {!file.is_public && (
                        <span className="ml-2 text-amber-600">
                          {t("admin.pages.will_make_public", {
                            defaultValue: "will be made public",
                          })}
                        </span>
                      )}
                    </p>
                  )}
                </div>
                {file.mime_type?.startsWith("image/") ? (
                  <Image className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                ) : (
                  <Link2 className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                )}
              </button>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Editor with file picker toolbar
// ---------------------------------------------------------------------------

function PageContentEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function insertAtCursor(text: string) {
    const ta = textareaRef.current;
    if (ta) {
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const next = value.slice(0, start) + text + value.slice(end);
      onChange(next);
      setTimeout(() => {
        ta.focus();
        ta.setSelectionRange(start + text.length, start + text.length);
      }, 0);
    } else {
      onChange(value + (value.endsWith("\n") ? "" : "\n") + text);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Content</Label>
        <FilePicker onInsert={insertAtCursor} />
      </div>
      <details className="text-xs border rounded-md">
        <summary className="px-3 py-1.5 cursor-pointer text-muted-foreground hover:text-foreground select-none">
          Available variables
        </summary>
        <div className="px-3 pb-3 pt-1 grid grid-cols-1 gap-1.5">
          {MAGIC_VAR_DOCS.map((v) => (
            <div key={v.key} className="flex items-baseline gap-2">
              <button
                type="button"
                className="font-mono bg-muted px-1 py-0.5 rounded text-xs shrink-0 cursor-pointer hover:bg-muted/70"
                onClick={() => insertAtCursor(`{{${v.key}}}`)}
                title="Click to insert"
              >
                {`{{${v.key}}}`}
              </button>
              <span className="text-muted-foreground">{v.example}</span>
            </div>
          ))}
        </div>
      </details>
      <MarkdownEditor ref={textareaRef} value={value} onChange={onChange} rows={20} />
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
          {mutation.isPending
            ? t("common.saving", { defaultValue: "Saving…" })
            : t("common.save", { defaultValue: "Save" })}
        </Button>
        {effectivePublished && (
          <a
            href={`/p/${effectiveSlug}`}
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
