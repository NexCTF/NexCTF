import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Markdown } from "@/components/markdown";
import { useMagicVars } from "@/hooks/use-magic-vars";
import { getPublishedPage } from "@/lib/api";
import { applyMagicVars } from "@/lib/magic-vars";

export const Route = createFileRoute("/_user/p/$slug")({
  component: PublicPage,
});

function PublicPage() {
  const { t } = useTranslation();
  const { slug } = Route.useParams();
  const magicVars = useMagicVars();

  const {
    data: page,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["page", slug],
    queryFn: () => getPublishedPage(slug),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground">{t("common.loading", { defaultValue: "Loading…" })}</p>
      </div>
    );
  }

  if (isError || !page) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-2">
        <p className="text-lg font-semibold">
          {t("errors.not_found", { defaultValue: "Page not found" })}
        </p>
        <p className="text-muted-foreground text-sm">
          {t("errors.not_found_desc", {
            defaultValue: "This page doesn't exist or is not published.",
          })}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-bold mb-8">{page.title}</h1>
      <div className="prose-container">
        <Markdown>{applyMagicVars(page.content, magicVars)}</Markdown>
      </div>
    </div>
  );
}
