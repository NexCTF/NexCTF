import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Navigate, useNavigate } from "@tanstack/react-router";
import { ShieldBan } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OtpFieldInput, OtpFieldRoot } from "@/components/ui/otp-field";
import { Separator } from "@/components/ui/separator";
import { useCaptcha } from "@/hooks/use-captcha";
import { ApiError, logout as apiLogout, getPublicInfo, oauthAuthorizeUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { next?: string } => ({
    next: typeof search.next === "string" ? search.next : undefined,
  }),
  component: LoginPage,
});

function LoginPage() {
  const { t } = useTranslation();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const { next } = Route.useSearch();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [totpRequired, setTotpRequired] = useState(false);
  const [accountDisabled, setAccountDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { name } = useBranding();

  const { data: publicInfo } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });
  const providers = publicInfo?.oauth_providers ?? [];
  const allowRegistration = publicInfo?.competition?.allow_registration ?? false;

  const {
    captchaEnabled,
    captchaWidgetEndpoint,
    captchaToken,
    capWidgetRef,
    resetCaptcha,
    captchaSolved,
  } = useCaptcha(publicInfo);

  if (user) return <Navigate to="/" />;

  if (accountDisabled) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-sm">
          <CardHeader className="text-center">
            <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-full bg-destructive/10">
              <ShieldBan className="size-7 text-destructive" />
            </div>
            <CardTitle>{t("login.disabled_title")}</CardTitle>
            <CardDescription>{t("login.disabled_message")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full"
              variant="outline"
              onClick={async () => {
                await apiLogout().catch(() => {});
                setAccountDisabled(false);
              }}
            >
              {t("common.sign_out")}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(
        username,
        password,
        totpRequired ? totpCode : undefined,
        captchaEnabled ? (captchaToken ?? undefined) : undefined,
      );
      if (next) {
        window.location.href = next;
      } else {
        navigate({ to: "/" });
      }
    } catch (err) {
      resetCaptcha();
      if (err instanceof ApiError) {
        if (err.errCode === "AUTH-TOTP-REQUIRED") {
          setTotpRequired(true);
          setTotpCode("");
        } else if (err.errCode === "AUTH-403-DISABLED") {
          setAccountDisabled(true);
        } else {
          setError(err.description ?? err.message);
        }
      } else {
        setError(t("login.error_unexpected"));
      }
    } finally {
      setLoading(false);
    }
  }

  const submitDisabled = loading || (totpRequired && totpCode.length < 6) || !captchaSolved;

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold">{name}</CardTitle>
          <CardDescription>
            {totpRequired ? t("login.totp_subtitle") : t("login.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {totpRequired ? (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground text-center">{t("login.totp_hint")}</p>
                <div className="flex justify-center">
                  <OtpFieldRoot
                    length={6}
                    value={totpCode}
                    onValueChange={setTotpCode}
                    onValueComplete={() => {}}
                    autoSubmit
                    validationType="numeric"
                  >
                    {Array.from({ length: 6 }).map((_, i) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: fixed-count OTP slots, never reorder
                      <OtpFieldInput key={i} />
                    ))}
                  </OtpFieldRoot>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full text-xs"
                  onClick={() => {
                    setTotpRequired(false);
                    setError(null);
                  }}
                >
                  {t("login.totp_back")}
                </Button>
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="username">{t("login.username")}</Label>
                  <Input
                    id="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">{t("login.password")}</Label>
                  <Input
                    id="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </>
            )}

            {captchaEnabled && captchaWidgetEndpoint && (
              <cap-widget
                ref={(el: HTMLElement | null) => {
                  capWidgetRef.current = el;
                }}
                data-cap-api-endpoint={captchaWidgetEndpoint}
                style={{ display: "none" }}
              />
            )}

            <Button type="submit" className="w-full" disabled={submitDisabled}>
              {loading ? t("login.submitting") : t("login.submit")}
            </Button>
          </form>

          {!totpRequired && providers.length > 0 && (
            <>
              <div className="relative my-6">
                <Separator />
                <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                  {t("login.or_continue_with")}
                </span>
              </div>

              <div className="space-y-2">
                {providers.map((provider) => (
                  <a
                    key={provider.slug}
                    href={oauthAuthorizeUrl(provider.slug, window.location.origin)}
                    className={buttonVariants({
                      variant: "outline",
                      className: "w-full",
                    })}
                  >
                    {provider.icon_url && (
                      <img src={provider.icon_url} alt="" className="h-5 w-5" />
                    )}
                    {provider.name}
                  </a>
                ))}
              </div>
            </>
          )}

          {!totpRequired && allowRegistration && (
            <p className="mt-4 text-center text-sm text-muted-foreground">
              {t("login.no_account")}{" "}
              <Link to="/register" className="underline underline-offset-4 hover:text-foreground">
                {t("login.sign_up")}
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
