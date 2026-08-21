import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";
import {
  BookOpen,
  Check,
  Copy,
  KeyRound,
  Link2,
  Link2Off,
  LogOut,
  Monitor,
  Plus,
  ShieldCheck,
  ShieldOff,
  Smartphone,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ConfirmDialog, DeleteButton } from "@/components/confirm-dialog";
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
  ApiError,
  type ApiToken,
  apiErrorMessage,
  changePassword,
  createMyToken,
  deleteAllSessions,
  deleteMyOAuthAccount,
  deleteMySession,
  deleteMyToken,
  getMyOAuthAccounts,
  getMySessions,
  getMyTokens,
  getPublicInfo,
  type OAuthAccount,
  oauthAuthorizeUrl,
  type TotpSetupData,
  totpDisable,
  totpEnable,
  totpSetup,
  type User,
  type UserSession,
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

// ── Row skeleton ──────────────────────────────────────────────────────────────

function RowSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 2 }).map((_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders
        <div key={i} className="h-14 rounded-lg border bg-muted/20 animate-pulse" />
      ))}
    </div>
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
          <Button size="sm">
            <Plus />
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
              <Label htmlFor="token-name">{t("settings.token.field_name")}</Label>
              <Input
                id="token-name"
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
      <DeleteButton
        label={t("settings.token.revoke", { defaultValue: "Revoke token" })}
        description={t("settings.token.revoke_confirm", { name: displayName })}
        disabled={mutation.isPending}
        onConfirm={() => mutation.mutate()}
      />
    </div>
  );
}

// ponytail: substring matching on the UA string, enough for a device label.
// Swap in a real parser only if the labels start being wrong for real users.
// Order is significant — first match wins, so narrower patterns come first.
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/Firefox\//, "Firefox"],
  [/Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const OSES: [RegExp, string][] = [
  [/Windows/, "Windows"],
  [/Android/, "Android"],
  [/iPhone|iPad|iPod/, "iOS"],
  [/Mac OS X/, "macOS"],
  [/Linux/, "Linux"],
];

const matchUa = (ua: string, table: [RegExp, string][]): string | null =>
  table.find(([re]) => re.test(ua))?.[1] ?? null;

function describeDevice(ua: string | null): { browser: string | null; os: string | null } {
  if (!ua) return { browser: null, os: null };
  return { browser: matchUa(ua, BROWSERS), os: matchUa(ua, OSES) };
}

function formatLastSeen(iso: string, locale: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, secs] of units) {
    if (seconds >= secs) return rtf.format(-Math.floor(seconds / secs), unit);
  }
  return rtf.format(-Math.max(seconds, 0), "second");
}

function SessionRow({ session, onRevoked }: { session: UserSession; onRevoked: () => void }) {
  const { t, i18n } = useTranslation();

  const mutation = useMutation({
    mutationFn: () => deleteMySession(session.id),
    onSuccess: () => {
      toast.success(t("settings.session.revoked", { defaultValue: "Session signed out" }));
      onRevoked();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("settings.session.revoke_error", { defaultValue: "Could not sign out that session" }),
        ),
      ),
  });

  const { browser, os } = describeDevice(session.user_agent);
  const label =
    browser && os
      ? t("settings.session.device_on", {
          browser,
          os,
          defaultValue: "{{browser}} on {{os}}",
        })
      : (browser ?? os ?? t("settings.session.device_unknown", { defaultValue: "Unknown device" }));
  const isMobile = os === "Android" || os === "iOS";
  const DeviceIcon = isMobile ? Smartphone : Monitor;

  return (
    <div className="flex items-center gap-4 rounded-lg border px-4 py-3">
      <DeviceIcon className="size-4 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {label}
          {session.current && (
            <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary align-middle">
              {t("settings.session.current", { defaultValue: "This device" })}
            </span>
          )}
        </p>
        <p className="text-xs text-muted-foreground truncate">
          {session.ip
            ? t("settings.session.signed_in_from", {
                ip: session.ip,
                defaultValue: "Signed in from {{ip}}",
              })
            : t("settings.session.signed_in_from_unknown", {
                defaultValue: "Signed in from an unknown IP",
              })}
          {session.last_ip && session.last_ip !== session.ip && (
            <span className="text-amber-600 dark:text-amber-500">
              {` · ${t("settings.session.now_used_from", {
                ip: session.last_ip,
                defaultValue: "now used from {{ip}}",
              })}`}
            </span>
          )}
          {!session.current &&
            ` · ${t("settings.session.last_seen", {
              when: formatLastSeen(session.last_seen_at, i18n.language),
              defaultValue: "Last active {{when}}",
            })}`}
        </p>
      </div>
      {!session.current && (
        <ConfirmDialog
          description={t("settings.session.revoke_confirm", {
            device: label,
            defaultValue: "Sign out {{device}}?",
          })}
          confirmLabel={t("settings.session.revoke", { defaultValue: "Sign out this device" })}
          onConfirm={() => mutation.mutate()}
          trigger={
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={mutation.isPending}
              aria-label={t("settings.session.revoke", { defaultValue: "Sign out this device" })}
            >
              <LogOut className="size-3.5" />
            </Button>
          }
        />
      )}
    </div>
  );
}

function SessionsSection() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { logout } = useAuth();

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["my-sessions"],
    queryFn: getMySessions,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["my-sessions"] });
  }

  const revokeAll = useMutation({
    mutationFn: deleteAllSessions,
    onSuccess: async () => {
      toast.success(
        t("settings.session.all_revoked", { defaultValue: "Signed out on every device" }),
      );
      // The cookie is already dead server-side; reuse logout's teardown so the
      // app drops its cached identity and the route guard sends us to login.
      await logout();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("settings.session.all_revoke_error", {
            defaultValue: "Could not sign out the other devices",
          }),
        ),
      ),
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">
            {t("settings.session.section_title", { defaultValue: "Active sessions" })}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t("settings.session.section_hint", {
              defaultValue: "Devices currently signed in to your account.",
            })}
          </p>
        </div>
        <ConfirmDialog
          description={t("settings.session.revoke_all_confirm", {
            defaultValue: "Sign out on every device? You will be signed out here too.",
          })}
          confirmLabel={t("settings.session.revoke_all", { defaultValue: "Sign out everywhere" })}
          onConfirm={() => revokeAll.mutate()}
          trigger={
            <Button
              variant="outline"
              size="sm"
              disabled={sessions.length === 0 || revokeAll.isPending}
            >
              <LogOut />
              {t("settings.session.revoke_all", { defaultValue: "Sign out everywhere" })}
            </Button>
          }
        />
      </div>

      {isLoading ? (
        <RowSkeleton />
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => (
            <SessionRow key={session.id} session={session} onRevoked={invalidate} />
          ))}
        </div>
      )}
    </section>
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
            <ShieldCheck />
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
            <ShieldOff />
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
    unlink.mutate({ id: account.id, name: account.provider_name });
  }

  if (allProviders.length === 0) return null;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">{t("settings.oauth.section_title")}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">{t("settings.oauth.section_hint")}</p>
      </div>

      {isLoading ? (
        <RowSkeleton />
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
                  <ConfirmDialog
                    description={t("settings.oauth.unlink_confirm", {
                      name: linked.provider_name,
                    })}
                    confirmLabel={t("settings.oauth.unlink")}
                    onConfirm={() => handleUnlink(linked)}
                    trigger={
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive shrink-0 gap-1.5"
                        disabled={unlink.isPending}
                      >
                        <Link2Off className="size-3.5" />
                        {t("settings.oauth.unlink")}
                      </Button>
                    }
                  />
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

// ── Password Section ──────────────────────────────────────────────────────────

function PasswordSection() {
  const { t } = useTranslation();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      toast.success(t("settings.password.changed"));
      setCurrent("");
      setNext("");
      setConfirm("");
    },
    onError: (err) => {
      const wrong = err instanceof ApiError && err.errCode === "AUTH-401";
      toast.error(
        wrong
          ? t("settings.password.wrong_current")
          : apiErrorMessage(err, t("settings.password.error")),
      );
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      toast.error(t("settings.password.mismatch"));
      return;
    }
    mutation.mutate();
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">{t("settings.password.section_title")}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t("settings.password.section_hint")}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border px-4 py-4">
        <div className="space-y-1.5">
          <Label htmlFor="current-password">{t("settings.password.current")}</Label>
          <Input
            id="current-password"
            type="password"
            required
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="new-password">{t("settings.password.new")}</Label>
          <Input
            id="new-password"
            type="password"
            required
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">{t("settings.password.confirm")}</Label>
          <Input
            id="confirm-password"
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <Button type="submit" size="sm" disabled={mutation.isPending}>
          {mutation.isPending ? t("common.saving") : t("settings.password.submit")}
        </Button>
      </form>
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

      {user.has_password && <PasswordSection />}

      {/* Two-Factor Authentication */}
      <TotpSection totpEnabled={user.totp_enabled} onChanged={invalidateUser} />

      {/* Connected OAuth accounts */}
      <OAuthSection />

      {/* Signed-in devices */}
      <SessionsSection />

      {/* API Tokens section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{t("settings.token.section_title")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("settings.token.section_hint")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <BookOpen />
              {t("settings.token.docs")}
            </a>
            <CreateTokenDialog onCreated={invalidate} />
          </div>
        </div>

        {isLoading ? (
          <RowSkeleton />
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
