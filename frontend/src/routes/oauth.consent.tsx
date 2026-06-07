import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ShieldCheck, ShieldX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { approveOAuthConsent, getOAuthConsentInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/oauth/consent")({
  validateSearch: (search: Record<string, unknown>) => ({
    client_id: typeof search.client_id === "string" ? search.client_id : "",
    redirect_uri: typeof search.redirect_uri === "string" ? search.redirect_uri : "",
    scope: typeof search.scope === "string" ? search.scope : "openid profile",
    state: typeof search.state === "string" ? search.state : undefined,
  }),
  component: ConsentPage,
});

const SCOPE_ICONS: Record<string, string> = {
  openid: "🔑",
  profile: "👤",
  email: "✉️",
  roles: "🛡️",
};

function ConsentPage() {
  const { t } = useTranslation();
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const { client_id, redirect_uri, scope, state } = Route.useSearch();

  const { data: info, isLoading } = useQuery({
    queryKey: ["oauth-consent", client_id, scope],
    queryFn: () => getOAuthConsentInfo(client_id, scope),
    enabled: !!user && !!client_id,
    retry: false,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveOAuthConsent({ client_id, redirect_uri, scope, state }),
    onSuccess: ({ redirect_to }) => {
      window.location.href = redirect_to;
    },
  });

  function handleDeny() {
    let url = `${redirect_uri}?error=access_denied`;
    if (state) url += `&state=${encodeURIComponent(state)}`;
    window.location.href = url;
  }

  // Redirect to login if not authenticated
  if (!authLoading && !user) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    navigate({ to: "/login", search: { next } });
    return null;
  }

  if (authLoading || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-muted-foreground text-sm">{t("common.loading")}</div>
      </div>
    );
  }

  if (!client_id || !redirect_uri) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-destructive">{t("oauth_consent.invalid_request")}</CardTitle>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">{t("oauth_consent.title")}</CardTitle>
          <CardDescription>
            {t("oauth_consent.app_requesting", {
              app: info?.client_name ?? client_id,
            })}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {info?.client_description && (
            <p className="text-sm text-muted-foreground text-center">{info.client_description}</p>
          )}

          <div className="rounded-lg border p-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {t("oauth_consent.permissions")}
            </p>
            {(info?.requested_scopes ?? scope.split(" ")).map((s) => (
              <div key={s} className="flex items-center gap-2 text-sm">
                <span>{SCOPE_ICONS[s] ?? "•"}</span>
                <span>{t(`oauth_consent.scope.${s}`, { defaultValue: s })}</span>
              </div>
            ))}
          </div>

          <p className="text-xs text-center text-muted-foreground">
            {t("oauth_consent.logged_in_as", { username: user?.username })}
          </p>
        </CardContent>

        <CardFooter className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleDeny}
            disabled={approveMutation.isPending}
          >
            <ShieldX className="size-4" />
            {t("oauth_consent.deny")}
          </Button>
          <Button
            className="flex-1"
            onClick={() => approveMutation.mutate()}
            disabled={approveMutation.isPending}
          >
            <ShieldCheck className="size-4" />
            {approveMutation.isPending ? t("oauth_consent.authorizing") : t("oauth_consent.allow")}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
