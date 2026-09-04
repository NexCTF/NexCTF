import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus, ScrollText } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DeleteButton } from "@/components/confirm-dialog";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { ActionsCell, EmptyCell, idColumn, StatusCell } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  type CustomPage,
  createAdminPage,
  deleteAdminPage,
  getAdminPages,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/pages")({
  component: PagesPage,
});

function CreatePageDialog({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");

  const mutation = useMutation({
    mutationFn: () => createAdminPage({ title, slug }),
    onSuccess: (page) => {
      toast.success(t("admin.pages.created", { defaultValue: "Page created" }));
      setOpen(false);
      setTitle("");
      setSlug("");
      onCreated(page.id);
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.pages.create_error", { defaultValue: "Failed to create page" }),
        ),
      ),
  });

  function handleTitleChange(v: string) {
    setTitle(v);
    if (!slug || slug === slugify(title)) {
      setSlug(slugify(v));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.pages.create", { defaultValue: "New page" })}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.pages.create", { defaultValue: "New page" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.pages.field_title", { defaultValue: "Title" })}</Label>
            <Input
              value={title}
              onChange={(e) => handleTitleChange(e.target.value)}
              placeholder={t("admin.pages.title_placeholder", { defaultValue: "About us" })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.pages.field_slug", { defaultValue: "Slug" })}</Label>
            <Input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="about-us"
              pattern="[a-z0-9-]+"
              required
            />
            <p className="text-xs text-muted-foreground">
              {t("admin.pages.slug_hint", {
                defaultValue:
                  "URL-friendly identifier. Accessible at /p/{slug}. Use 'home' to customize the index page.",
              })}
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending || !title || !slug}>
              {mutation.isPending ? t("common.creating") : t("common.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeletePageButton({ page, onDeleted }: { page: CustomPage; onDeleted: () => void }) {
  const { t } = useTranslation();

  const mutation = useMutation({
    mutationFn: () => deleteAdminPage(page.id),
    onSuccess: () => {
      toast.success(t("admin.pages.deleted", { defaultValue: "Page deleted" }));
      onDeleted();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.pages.delete_error", { defaultValue: "Delete failed" })),
      ),
  });

  return (
    <DeleteButton
      description={t("admin.pages.delete_confirm", {
        title: page.title,
        defaultValue: 'Delete page "{{title}}"?',
      })}
      disabled={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    />
  );
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-");
}

const NAV_PLACEMENT_LABELS: Record<string, string> = {
  footer: "Footer",
  nav: "Top nav",
};

function PagesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "pages", table.queryString],
    queryFn: () => getAdminPages(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "pages"] });
  }

  const columns: Column<CustomPage>[] = [
    idColumn<CustomPage>(t),
    {
      key: "title",
      header: t("table.col_title", { defaultValue: "Title" }),
      cell: (p) => (
        <button
          type="button"
          className="font-medium text-left hover:underline"
          onClick={() => navigate({ to: "/admin/pages/$pageId", params: { pageId: p.id } })}
        >
          {p.title}
        </button>
      ),
    },
    {
      key: "slug",
      header: t("admin.pages.col_slug", { defaultValue: "Slug" }),
      cell: (p) => <span className="text-muted-foreground font-mono text-xs">/p/{p.slug}</span>,
    },
    {
      key: "nav_placement",
      header: t("admin.pages.col_nav", { defaultValue: "Navigation" }),
      cell: (p) =>
        p.nav_placement ? (
          <span className="text-xs">
            {NAV_PLACEMENT_LABELS[p.nav_placement] ?? p.nav_placement}
          </span>
        ) : (
          <EmptyCell />
        ),
    },
    {
      key: "is_published",
      header: t("table.col_status", { defaultValue: "Status" }),
      cell: (p) => (
        <StatusCell
          active={p.is_published}
          label={
            p.is_published
              ? t("admin.pages.published", { defaultValue: "Published" })
              : t("admin.pages.draft", { defaultValue: "Draft" })
          }
        />
      ),
    },
    {
      key: "actions" as keyof CustomPage,
      header: "",
      sortable: false,
      cell: (p) => (
        <ActionsCell>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate({ to: "/admin/pages/$pageId", params: { pageId: p.id } })}
          >
            {t("common.edit", { defaultValue: "Edit" })}
          </Button>
          <DeletePageButton page={p} onDeleted={invalidate} />
        </ActionsCell>
      ),
      className: "w-40 text-right",
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={ScrollText}
        title={t("admin.nav.pages", { defaultValue: "Pages" })}
        actions={
          <CreatePageDialog
            onCreated={(id) => navigate({ to: "/admin/pages/$pageId", params: { pageId: id } })}
          />
        }
      />

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(p) => p.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
