import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Markdown } from "@/components/markdown";
import { useMagicVars } from "@/hooks/use-magic-vars";
import { getPublicInfo, getPublishedPage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { applyMagicVars } from "@/lib/magic-vars";

export const Route = createFileRoute("/_user/")({
  component: Home,
});

function Home() {
  const { t } = useTranslation();
  const { user, isLoading } = useAuth();
  const { name, logoUrl } = useBranding();
  const magicVars = useMagicVars();

  const { data: homePage, isLoading: homeLoading } = useQuery({
    queryKey: ["page", "home"],
    queryFn: () => getPublishedPage("home"),
    retry: false,
    throwOnError: false,
  });

  const { data: publicInfo } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });
  const description = publicInfo?.competition?.description;

  if (isLoading || homeLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  if (homePage) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <Markdown>{applyMagicVars(homePage.content, magicVars)}</Markdown>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" />;

  return (
    <div className="flex flex-col items-center justify-center py-32 gap-4">
      {logoUrl && <img src={logoUrl} alt={name} className="h-16 w-16 object-contain" />}
      <h1 className="text-4xl font-bold">{name}</h1>
      {description && <p className="text-muted-foreground text-center max-w-md">{description}</p>}
      <p className="text-muted-foreground">{t("home.welcome", { username: user.username })}</p>
    </div>
  );
}
