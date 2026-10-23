import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import type { TFunction } from "i18next";
import {
  ArrowRight,
  Flag,
  type LucideIcon,
  Mail,
  Palette,
  ScrollText,
  UserPlus,
  Users,
} from "lucide-react";
import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConfigField } from "@/components/config-field";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  apiErrorMessage,
  createFirstAdmin,
  getConfig,
  getSetupStatus,
  updateConfig,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, PASSWORD_LIMITS, USERNAME_MAX_LENGTH } from "@/lib/utils";

const STEPS = ["account", "event", "next"] as const;
type Step = (typeof STEPS)[number];

const EVENT_KEYS = [
  "ctf.name",
  "ctf.description",
  "ctf.start_time",
  "ctf.end_time",
  "appearance.logo_url",
  "appearance.accent_color",
];

type NextLink = { icon: LucideIcon; title: string; description: string } & (
  | { to: "/admin/challenges" | "/admin/pages" | "/admin/users" }
  | { to: "/admin/settings"; search: { category: string } }
);

function nextLinks(t: TFunction): NextLink[] {
  return [
    {
      icon: Flag,
      to: "/admin/challenges",
      title: t("setup.next.challenges_title"),
      description: t("setup.next.challenges_desc"),
    },
    {
      icon: ScrollText,
      to: "/admin/pages",
      title: t("setup.next.pages_title"),
      description: t("setup.next.pages_desc"),
    },
    {
      icon: Users,
      to: "/admin/settings",
      search: { category: "competition" },
      title: t("setup.next.registration_title"),
      description: t("setup.next.registration_desc"),
    },
    {
      icon: Mail,
      to: "/admin/settings",
      search: { category: "email" },
      title: t("setup.next.email_title"),
      description: t("setup.next.email_desc"),
    },
    {
      icon: Palette,
      to: "/admin/settings",
      search: { category: "appearance" },
      title: t("setup.next.appearance_title"),
      description: t("setup.next.appearance_desc"),
    },
    {
      icon: UserPlus,
      to: "/admin/users",
      title: t("setup.next.admins_title"),
      description: t("setup.next.admins_desc"),
    },
  ];
}

const SETUP_QUERY = { queryKey: ["setup"], queryFn: getSetupStatus, staleTime: Infinity };

export const Route = createFileRoute("/setup")({
  validateSearch: (search: Record<string, unknown>): { token?: string; step?: Step } => ({
    token: typeof search.token === "string" ? search.token : undefined,
    step: STEPS.find((s) => s === search.step),
  }),
  component: SetupPage,
});

function SetupPage() {
  const { step } = Route.useSearch();
  const { user, isLoading } = useAuth();
  const { data: status } = useQuery(SETUP_QUERY);

  if (!status || isLoading) return null;
  if (status.admin_required) {
    return (
      <SetupShell step="account">
        <AccountStep />
      </SetupShell>
    );
  }
  const isAdmin = user?.role === "admin";
  if (!isAdmin || (step !== "event" && step !== "next")) {
    return <Navigate to={isAdmin ? "/admin" : "/"} replace />;
  }
  return <SetupShell step={step}>{step === "event" ? <EventStep /> : <NextStep />}</SetupShell>;
}

function SetupShell({ step, children }: { step: Step; children: ReactNode }) {
  const { t } = useTranslation();
  const index = STEPS.indexOf(step);
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="fixed top-4 right-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-lg space-y-4">
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <span
              key={s}
              className={cn("h-1.5 w-8 rounded-full", i <= index ? "bg-primary" : "bg-muted")}
            />
          ))}
        </div>
        <p className="text-center text-sm text-muted-foreground">
          {t("setup.progress", { current: index + 1, total: STEPS.length })}
        </p>
        {children}
      </div>
    </div>
  );
}

function AccountStep() {
  const { t } = useTranslation();
  const { token: linkToken } = Route.useSearch();
  const navigate = Route.useNavigate();
  const qc = useQueryClient();
  const { refresh } = useAuth();
  const [token, setToken] = useState(linkToken ?? "");
  const [askToken, setAskToken] = useState(!linkToken);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("setup.account.mismatch"));
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await createFirstAdmin({ token, username, password, email: email || undefined });
      await refresh();
      qc.setQueryData(SETUP_QUERY.queryKey, { admin_required: false });
      await navigate({ search: { step: "event" }, replace: true });
    } catch (err) {
      const code = err instanceof ApiError ? err.errCode : null;
      if (code === "SETUP-403-TOKEN") {
        setAskToken(true);
        setError(t("setup.account.token_invalid"));
      } else if (code === "SETUP-409-DONE") {
        await qc.invalidateQueries({ queryKey: SETUP_QUERY.queryKey });
      } else {
        setError(apiErrorMessage(err, t("setup.account.error_unexpected")));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl font-bold">{t("setup.account.title")}</CardTitle>
        <CardDescription>{t("setup.account.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
          )}
          {askToken && (
            <div className="space-y-2">
              <Label htmlFor="token">{t("setup.account.token")}</Label>
              <Input
                id="token"
                required
                autoComplete="off"
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
              <CardDescription>{t("setup.account.token_hint")}</CardDescription>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="username">{t("setup.account.username")}</Label>
            <Input
              id="username"
              required
              autoComplete="username"
              maxLength={USERNAME_MAX_LENGTH}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">{t("setup.account.email")}</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t("setup.account.password")}</Label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              {...PASSWORD_LIMITS}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">{t("setup.account.confirm_password")}</Label>
            <Input
              id="confirm"
              type="password"
              required
              autoComplete="new-password"
              {...PASSWORD_LIMITS}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t("common.saving") : t("setup.account.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function EventStep() {
  const { t } = useTranslation();
  const navigate = Route.useNavigate();
  const qc = useQueryClient();
  const { data: items = [] } = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const [values, setValues] = useState<Record<string, string>>({});

  const byKey = useMemo(() => new Map(items.map((item) => [item.key, item])), [items]);
  const fields = EVENT_KEYS.flatMap((key) => byKey.get(key) ?? []);
  const savedValue = (key: string) => String(byKey.get(key)?.value ?? "");
  const currentValue = (key: string) => values[key] ?? savedValue(key);
  const changed = Object.fromEntries(
    Object.entries(values).filter(([key, value]) => value !== savedValue(key)),
  );
  const timezone = savedValue("ctf.timezone");

  const goNext = () => navigate({ search: { step: "next" } });
  const mutation = useMutation({
    mutationFn: () => updateConfig(changed),
    onSuccess: async (updated) => {
      qc.setQueryData(["config"], updated);
      await qc.invalidateQueries({ queryKey: ["info", "public"] });
      await goNext();
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (Object.keys(changed).length === 0) {
      void goNext();
      return;
    }
    mutation.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl font-bold">{t("setup.event.title")}</CardTitle>
        <CardDescription>{t("setup.event.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {mutation.isError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {apiErrorMessage(mutation.error, t("setup.event.error"))}
            </div>
          )}
          {fields.map((item) => (
            <ConfigField
              key={item.key}
              item={item}
              value={currentValue(item.key)}
              onChange={(v) => setValues((prev) => ({ ...prev, [item.key]: v }))}
              timezone={timezone}
            />
          ))}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => void goNext()}>
              {t("setup.event.skip")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("setup.event.submit")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function NextStep() {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl font-bold">{t("setup.next.title")}</CardTitle>
        <CardDescription>{t("setup.next.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="divide-y rounded-md border">
          {nextLinks(t).map(({ icon: Icon, title, description, ...link }) => (
            <li key={title}>
              <Link
                {...link}
                className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/60"
              >
                <Icon className="size-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-sm text-muted-foreground">{description}</p>
                </div>
                <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
        <Link to="/admin" className={cn(buttonVariants(), "w-full")}>
          {t("setup.next.dashboard")}
        </Link>
      </CardContent>
    </Card>
  );
}
