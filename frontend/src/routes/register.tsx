import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Navigate, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCaptcha } from "@/hooks/use-captcha";
import { ApiError, register as apiRegister, getPublicInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";

export const Route = createFileRoute("/register")({
  component: RegisterPage,
});

function RegisterPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { name } = useBranding();

  const { data: publicInfo } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });

  const allowRegistration = publicInfo?.competition?.allow_registration ?? true;

  const {
    captchaEnabled,
    captchaWidgetEndpoint,
    captchaToken,
    capWidgetRef,
    resetCaptcha,
    captchaSolved,
  } = useCaptcha(publicInfo);

  if (user) return <Navigate to="/" />;
  if (publicInfo && !allowRegistration) return <Navigate to="/login" />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiRegister({
        username,
        password,
        email: email || undefined,
        captchaToken: captchaEnabled ? (captchaToken ?? undefined) : undefined,
      });
      toast.success(t("register.success"));
      navigate({ to: "/login" });
    } catch (err) {
      resetCaptcha();
      if (err instanceof ApiError) {
        setError(err.description ?? err.message);
      } else {
        setError(t("register.error_unexpected"));
      }
    } finally {
      setLoading(false);
    }
  }

  const submitDisabled = loading || !captchaSolved;

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold">{name}</CardTitle>
          <CardDescription>{t("register.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

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
              <Label htmlFor="email">{t("register.email")}</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

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
              {loading ? t("register.submitting") : t("register.submit")}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            {t("register.have_account")}{" "}
            <Link to="/login" className="underline underline-offset-4 hover:text-foreground">
              {t("register.sign_in")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
