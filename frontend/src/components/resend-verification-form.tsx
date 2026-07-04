import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resendVerification } from "@/lib/api";

/** Email input + button that re-sends the account verification email. */
export function ResendVerificationForm() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [resending, setResending] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setResending(true);
    try {
      await resendVerification(email);
      toast.success(t("verify_email.resent"));
    } catch {
      toast.error(t("verify_email.error_unexpected"));
    } finally {
      setResending(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <div className="space-y-2">
        <Label htmlFor="resend-email">{t("verify_email.email_label")}</Label>
        <Input
          id="resend-email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <Button type="submit" className="w-full" disabled={resending}>
        {resending ? t("verify_email.sending") : t("verify_email.resend")}
      </Button>
    </form>
  );
}
