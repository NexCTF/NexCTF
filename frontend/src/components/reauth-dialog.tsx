import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OtpFieldInput, OtpFieldRoot } from "@/components/ui/otp-field";
import {
  apiErrorMessage,
  getMyOAuthAccounts,
  oauthAuthorizeUrl,
  reauth,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { setReauthPrompt } from "@/lib/reauth";

/** Asks for the password, code or an OAuth sign-in when the API wants a fresh session. */
export function ReauthDialog() {
  const { user } = useAuth();
  const [resolve, setResolve] = useState<((ok: boolean) => void) | null>(null);

  useEffect(() => {
    setReauthPrompt(() => new Promise<boolean>((r) => setResolve(() => r)));
    return () => setReauthPrompt(null);
  }, []);

  const settle = (ok: boolean) => {
    resolve?.(ok);
    setResolve(null);
  };

  if (!user) return null;
  const open = resolve !== null;
  return (
    <Dialog open={open} onOpenChange={(next) => !next && settle(false)}>
      <DialogContent className="max-w-sm">
        {open && (
          <ReauthForm user={user} onDone={() => settle(true)} onCancel={() => settle(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function ReauthForm({
  user,
  onDone,
  onCancel,
}: {
  user: User;
  onDone: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const canSubmit = user.has_password || user.totp_enabled;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await reauth(user.has_password ? password : null, user.totp_enabled ? code : null);
      onDone();
    } catch (err) {
      setError(
        apiErrorMessage(err, t("reauth.failed", { defaultValue: "Could not confirm it's you." })),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{t("reauth.title", { defaultValue: "Confirm it's you" })}</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        {t("reauth.description", {
          defaultValue: "This action needs a recent sign-in. Confirm your identity to continue.",
        })}
      </p>
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}
      {user.has_password && (
        <div className="space-y-2">
          <Label htmlFor="reauth-password">
            {t("reauth.password", { defaultValue: "Password" })}
          </Label>
          <Input
            id="reauth-password"
            type="password"
            required
            autoFocus
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
      )}
      {user.totp_enabled && <TotpInput value={code} onChange={setCode} />}
      <LinkedProviders />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        {canSubmit && (
          <Button type="submit" disabled={submitting || (user.totp_enabled && code.length < 6)}>
            {t("reauth.submit", { defaultValue: "Confirm" })}
          </Button>
        )}
      </DialogFooter>
    </form>
  );
}

function TotpInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <Label>{t("reauth.totp", { defaultValue: "Authentication code" })}</Label>
      <OtpFieldRoot
        length={6}
        value={value}
        onValueChange={onChange}
        onValueComplete={() => {}}
        validationType="numeric"
      >
        {Array.from({ length: 6 }).map((_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-count OTP slots
          <OtpFieldInput key={i} />
        ))}
      </OtpFieldRoot>
    </div>
  );
}

/** Sign in again through a linked provider; the pending action is then retried by hand. */
function LinkedProviders() {
  const { t } = useTranslation();
  const { data: accounts = [] } = useQuery({
    queryKey: ["my-oauth"],
    queryFn: getMyOAuthAccounts,
  });
  if (accounts.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {t("reauth.or_provider", { defaultValue: "Or sign in again with" })}
      </p>
      {accounts.map((account) => (
        <a
          key={account.id}
          href={oauthAuthorizeUrl(account.provider_slug, window.location.href)}
          className={buttonVariants({ variant: "outline", className: "w-full" })}
        >
          {account.provider_icon_url && (
            <img src={account.provider_icon_url} alt="" className="h-5 w-5" />
          )}
          {account.provider_name}
        </a>
      ))}
    </div>
  );
}
