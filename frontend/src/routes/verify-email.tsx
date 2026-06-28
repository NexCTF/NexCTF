import { createFileRoute, Link } from "@tanstack/react-router";
import { MailCheck, MailX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ResendVerificationForm } from "@/components/resend-verification-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { verifyEmail } from "@/lib/api";

export const Route = createFileRoute("/verify-email")({
  validateSearch: (search: Record<string, unknown>): { token?: string } => ({
    token: typeof search.token === "string" ? search.token : undefined,
  }),
  component: VerifyEmailPage,
});

type Status = "loading" | "success" | "invalid";

function VerifyEmailPage() {
  const { t } = useTranslation();
  const { token } = Route.useSearch();
  const [status, setStatus] = useState<Status>(token ? "loading" : "invalid");
  // The token is single-use: guard against the effect firing twice (React
  // StrictMode) which would consume the token, then report it already spent.
  const startedRef = useRef(false);

  useEffect(() => {
    if (!token || startedRef.current) return;
    startedRef.current = true;
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch(() => setStatus("invalid"));
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        {status === "loading" && (
          <CardHeader className="text-center">
            <CardTitle>{t("verify_email.checking")}</CardTitle>
          </CardHeader>
        )}

        {status === "success" && (
          <>
            <CardHeader className="text-center">
              <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-full bg-primary/10">
                <MailCheck className="size-7 text-primary" />
              </div>
              <CardTitle>{t("verify_email.success_title")}</CardTitle>
              <CardDescription>{t("verify_email.success_desc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link to="/login">
                <Button className="w-full">{t("reset_password.back_to_login")}</Button>
              </Link>
            </CardContent>
          </>
        )}

        {status === "invalid" && (
          <>
            <CardHeader className="text-center">
              <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-full bg-destructive/10">
                <MailX className="size-7 text-destructive" />
              </div>
              <CardTitle>{t("verify_email.invalid_title")}</CardTitle>
              <CardDescription>{t("verify_email.invalid_desc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <ResendVerificationForm />
            </CardContent>
          </>
        )}
      </Card>
    </div>
  );
}
