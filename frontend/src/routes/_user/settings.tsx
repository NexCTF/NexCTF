import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";
import {
  Check,
  Copy,
  KeyRound,
  Link2,
  Link2Off,
  Plus,
  ShieldCheck,
  ShieldOff,
  Trash2,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
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
import { OtpFieldInput, OtpFieldRoot } from "@/components/ui/otp-field";
import {
  type ApiToken,
  apiErrorMessage,
  createMyToken,
  deleteMyOAuthAccount,
  deleteMyToken,
  getMyOAuthAccounts,
  getMyTokens,
  getPublicInfo,
  type OAuthAccount,
  oauthAuthorizeUrl,
  type TotpSetupData,
  totpDisable,
  totpEnable,
  totpSetup,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { copyToClipboard } from "@/lib/utils";

export const Route = createFileRoute("/_user/settings")({
  component: SettingsPage,
});

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={copy}>
      {copied ? <Check className="size-3.5 text-green-500" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

// ── Create token dialog ───────────────────────────────────────────────────────

function CreateTokenDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [createdToken, setCreatedToken] = useState<ApiToken | null>(null);

  const mutation = useMutation({
    mutationFn: () => createMyToken(name),
    onSuccess: (token) => {
      setCreatedToken(token);
      setName("");
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("settings.token.create_error"))),
  });

  function handleClose() {
    setOpen(false);
    setCreatedToken(null);
    setName("");
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("settings.token.new")}
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>
            {createdToken ? t("settings.token.created_title") : t("settings.token.new_title")}
          </DialogTitle>
        </DialogHeader>

        {createdToken ? (
          <div className="space-y-3 mt-2">
            <p className="text-sm text-muted-foreground">{t("settings.token.copy_hint")}</p>
            <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
              <code className="flex-1 text-xs font-mono break-all">{createdToken.token}</code>
              {/* biome-ignore lint/style/noNonNullAssertion: token is always present on a freshly-created token */}
              <CopyButton value={createdToken.token!} />
            </div>
            <DialogFooter>
              <Button onClick={handleClose}>{t("settings.token.done")}</Button>
            </DialogFooter>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate();
            }}
            className="space-y-4 mt-2"
          >
            <div className="space-y-1.5">
              <Label>{t("settings.token.field_name")}</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("settings.token.name_placeholder")}
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? t("common.saving") : t("common.save")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Token row ─────────────────────────────────────────────────────────────────

function TokenRow({ token, onDeleted }: { token: ApiToken; onDeleted: () => void }) {
  const { t, i18n } = useTranslation();

  const mutation = useMutation({
    mutationFn: () => deleteMyToken(token.id),
    onSuccess: () => {
      toast.success(t("settings.token.revoked"));
      onDeleted();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("settings.token.revoke_error"))),
  });

  const displayName = token.name ?? t("settings.token.unnamed");

  const createdAt = new Date(token.created_at).toLocaleDateString(i18n.language, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="flex items-center gap-4 rounded-lg border px-4 py-3">
      <KeyRound className="size-4 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{displayName}</p>
        <p className="text-xs text-muted-foreground">
          {t("settings.token.created_at", { date: createdAt })}
        </p>
      </div>
      {token.expires_at && (
        <span className="text-xs text-muted-foreground shrink-0">
          {t("settings.token.expires_at", {
            date: new Date(token.expires_at).toLocaleDateString(i18n.language),
          })}
        </span>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="size-7 text-destructive hover:text-destructive shrink-0"
        disabled={mutation.isPending}
        onClick={() => {
          if (confirm(t("settings.token.revoke_confirm", { name: displayName }))) {
            mutation.mutate();
          }
        }}
      >
        <Trash2 className="size-3.5" />
      </Button>
    </div>
  );
}

// ── TOTP Setup Dialog ─────────────────────────────────────────────────────────

type SetupStep = "qr" | "verify";

function TotpSetupDialog({ onEnabled }: { onEnabled: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<SetupStep>("qr");
  const [setupData, setSetupData] = useState<TotpSetupData | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const setupMutation = useMutation({
    mutationFn: totpSetup,
    onSuccess: (data) => {
      setSetupData(data);
      setStep("qr");
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("settings.totp.setup_error"))),
  });

  const enableMutation = useMutation({
    mutationFn: () => totpEnable(code),
    onSuccess: () => {
      qc.setQueryData<User | null>(["auth", "me"], (u) => (u ? { ...u, totp_enabled: true } : u));
      toast.success(t("settings.totp.enabled"));
      onEnabled();
      handleClose();
    },
    onError: () => {
      setError(t("settings.totp.invalid_code"));
      setCode("");
    },
  });

  function handleOpen() {
    setOpen(true);
    setStep("qr");
    setSetupData(null);
    setCode("");
    setError(null);
    setupMutation.mutate();
  }

  function handleClose() {
    setOpen(false);
    setSetupData(null);
    setCode("");
    setError(null);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? handleOpen() : handleClose())}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <ShieldCheck className="size-4" />
            {t("settings.totp.enable_btn")}
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("settings.totp.setup_title")}</DialogTitle>
        </DialogHeader>

        {setupMutation.isPending ? (
          <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
            {t("common.loading")}
          </div>
        ) : (
          setupData && (
            <div className="space-y-4 mt-2">
              {step === "qr" ? (
                <>
                  <p className="text-sm text-muted-foreground">{t("settings.totp.scan_hint")}</p>
                  <div className="flex justify-center rounded-xl border bg-white p-4">
                    <QRCodeSVG value={setupData.provisioning_uri} size={180} />
                  </div>
                  {(() => {
                    const secret = new URLSearchParams(
                      new URL(setupData.provisioning_uri).search,
                    ).get("secret");
                    return secret ? (
                      <div className="space-y-1.5">
                        <p className="text-xs text-muted-foreground">
                          {t("settings.totp.manual_entry")}
                        </p>
                        <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
                          <code className="flex-1 text-xs font-mono break-all">{secret}</code>
                          <CopyButton value={secret} />
                        </div>
                      </div>
                    ) : null;
                  })()}
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={handleClose}>
                      {t("common.cancel")}
                    </Button>
                    <Button onClick={() => setStep("verify")}>{t("settings.totp.next_btn")}</Button>
                  </DialogFooter>
                </>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">{t("settings.totp.verify_hint")}</p>
                  {error && <p className="text-sm text-destructive">{error}</p>}
                  <div className="flex justify-center">
                    <OtpFieldRoot
                      length={6}
                      value={code}
                      onValueChange={(v) => {
                        setCode(v);
                        setError(null);
                      }}
                      onValueComplete={() => {}}
                      autoSubmit
                      validationType="numeric"
                    >
                      {Array.from({ length: 6 }).map((_, i) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-count OTP slots
                        <OtpFieldInput key={i} />
                      ))}
                    </OtpFieldRoot>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => setStep("qr")}>
                      {t("common.back")}
                    </Button>
                    <Button
                      onClick={() => enableMutation.mutate()}
                      disabled={enableMutation.isPending || code.length < 6}
                    >
                      {enableMutation.isPending
                        ? t("common.saving")
                        : t("settings.totp.confirm_btn")}
                    </Button>
                  </DialogFooter>
                </>
              )}
            </div>
          )
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── TOTP Disable Dialog ───────────────────────────────────────────────────────

function TotpDisableDialog({ onDisabled }: { onDisabled: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => totpDisable(code),
    onSuccess: () => {
      qc.setQueryData<User | null>(["auth", "me"], (u) => (u ? { ...u, totp_enabled: false } : u));
      toast.success(t("settings.totp.disabled"));
      onDisabled();
      handleClose();
    },
    onError: () => {
      setError(t("settings.totp.invalid_code"));
      setCode("");
    },
  });

  function handleClose() {
    setOpen(false);
    setCode("");
    setError(null);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
      <DialogTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
          >
            <ShieldOff className="size-4" />
            {t("settings.totp.disable_btn")}
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("settings.totp.disable_title")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <p className="text-sm text-muted-foreground">{t("settings.totp.disable_hint")}</p>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-center">
            <OtpFieldRoot
              length={6}
              value={code}
              onValueChange={(v) => {
                setCode(v);
                setError(null);
              }}
              onValueComplete={() => {}}
              autoSubmit
              validationType="numeric"
            >
              {Array.from({ length: 6 }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: fixed-count OTP slots
                <OtpFieldInput key={i} />
              ))}
            </OtpFieldRoot>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || code.length < 6}
            >
              {mutation.isPending ? t("common.saving") : t("settings.totp.disable_confirm_btn")}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── OAuth Section ─────────────────────────────────────────────────────────────

function OAuthSection() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: accounts = [], isLoading: accountsLoading } = useQuery({
    queryKey: ["my-oauth"],
    queryFn: getMyOAuthAccounts,
  });

  const { data: publicInfo, isLoading: infoLoading } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });

  const isLoading = accountsLoading || infoLoading;
  const allProviders = publicInfo?.oauth_providers ?? [];

  const unlink = useMutation({
    mutationFn: ({ id }: { id: string; name: string }) => deleteMyOAuthAccount(id),
    onSuccess: (_, { id, name }) => {
      queryClient.setQueryData<OAuthAccount[]>(
        ["my-oauth"],
        (prev) => prev?.filter((a) => a.id !== id) ?? [],
      );
      toast.success(t("settings.oauth.unlinked", { name }));
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("settings.oauth.unlink_error"))),
  });

  function handleUnlink(account: OAuthAccount) {
    if (confirm(t("settings.oauth.unlink_confirm", { name: account.provider_name }))) {
      unlink.mutate({ id: account.id, name: account.provider_name });
    }
  }

  if (allProviders.length === 0) return null;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">{t("settings.oauth.section_title")}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">{t("settings.oauth.section_hint")}</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton
            <div key={i} className="h-14 rounded-lg border bg-muted/20 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {allProviders.map((provider) => {
            const linked = accounts.find((a) => a.provider_slug === provider.slug);
            return (
              <div
                key={provider.slug}
                className="flex items-center gap-4 rounded-lg border px-4 py-3"
              >
                {provider.icon_url ? (
                  <img src={provider.icon_url} alt="" className="size-4 shrink-0" />
                ) : (
                  <Link2 className="size-4 text-muted-foreground shrink-0" />
                )}
                <p className="flex-1 text-sm font-medium">{provider.name}</p>
                {linked ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive shrink-0 gap-1.5"
                    disabled={unlink.isPending}
                    onClick={() => handleUnlink(linked)}
                  >
                    <Link2Off className="size-3.5" />
                    {t("settings.oauth.unlink")}
                  </Button>
                ) : (
                  <a
                    href={oauthAuthorizeUrl(provider.slug, window.location.href)}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    <Link2 className="size-3.5" />
                    {t("settings.oauth.connect")}
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ── TOTP Section ──────────────────────────────────────────────────────────────

function TotpSection({ totpEnabled, onChanged }: { totpEnabled: boolean; onChanged: () => void }) {
  const { t } = useTranslation();

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">{t("settings.totp.section_title")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("settings.totp.section_hint")}</p>
        </div>
        {totpEnabled ? (
          <TotpDisableDialog onDisabled={onChanged} />
        ) : (
          <TotpSetupDialog onEnabled={onChanged} />
        )}
      </div>

      <div className="rounded-lg border px-4 py-3 flex items-center gap-3">
        {totpEnabled ? (
          <ShieldCheck className="size-4 text-green-500 shrink-0" />
        ) : (
          <ShieldOff className="size-4 text-muted-foreground shrink-0" />
        )}
        <div>
          <p className="text-sm font-medium">
            {totpEnabled ? t("settings.totp.status_enabled") : t("settings.totp.status_disabled")}
          </p>
          <p className="text-xs text-muted-foreground">
            {totpEnabled
              ? t("settings.totp.status_enabled_hint")
              : t("settings.totp.status_disabled_hint")}
          </p>
        </div>
      </div>
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SettingsPage() {
  const { t } = useTranslation();
  const { user, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const { data: tokensResp, isLoading } = useQuery({
    queryKey: ["my-tokens"],
    queryFn: getMyTokens,
    enabled: !!user,
  });

  const tokens = tokensResp?.data ?? [];

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["my-tokens"] });
  }

  function invalidateUser() {
    void queryClient.refetchQueries({ queryKey: ["auth", "me"] });
  }

  if (authLoading) return null;
  if (!user) return <Navigate to="/login" />;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">{t("settings.title")}</h1>
        <p className="text-muted-foreground text-sm mt-1">{t("settings.subtitle")}</p>
      </div>

      {/* Two-Factor Authentication */}
      <TotpSection totpEnabled={user.totp_enabled} onChanged={invalidateUser} />

      {/* Connected OAuth accounts */}
      <OAuthSection />

      {/* API Tokens section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{t("settings.token.section_title")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("settings.token.section_hint")}
            </p>
          </div>
          <CreateTokenDialog onCreated={invalidate} />
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders
              <div key={i} className="h-14 rounded-lg border bg-muted/20 animate-pulse" />
            ))}
          </div>
        ) : tokens.length === 0 ? (
          <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
            {t("settings.token.empty")}
          </div>
        ) : (
          <div className="space-y-2">
            {tokens.map((token) => (
              <TokenRow key={token.id} token={token} onDeleted={invalidate} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
