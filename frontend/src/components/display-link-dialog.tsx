import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Check, Copy, ExternalLink, EyeOff, KeyRound } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Banner } from "@/components/banner";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiErrorMessage, createMyToken, getConfig } from "@/lib/api";
import {
  type DisplayOptions,
  displayPath,
  ROTATE_RANGE,
  resolveDisplayOptions,
} from "@/lib/display";
import { useEventPhase } from "@/lib/use-event-phase";
import { copyToClipboard } from "@/lib/utils";

const ALL_TEAMS = "__all__";
const ROTATE = "__rotate__";
const DEFAULT_ROTATE = 20;

interface LinkForm {
  /** ALL_TEAMS, ROTATE or a bracket name. */
  view: string;
  rotate: string;
  scale: string;
}

const INITIAL_FORM: LinkForm = { view: ALL_TEAMS, rotate: String(DEFAULT_ROTATE), scale: "1" };

/** Scopes of a screen token: the scoreboard and the broadcasts, read-only. */
export const SCREEN_TOKEN_SCOPES = ["read:scoreboard", "read:notification"];
const DAY_MS = 24 * 60 * 60 * 1000;

/** A screen token lives until a day after the event ends, or a week without an end time. */
export function screenTokenExpiry(end: Date | null, now: number): Date {
  return end ? new Date(Math.max(end.getTime(), now) + DAY_MS) : new Date(now + 7 * DAY_MS);
}

interface ScreenToken {
  token: string;
  expiresAt: string | null;
}

/** The display settings *form* resolves to, with the page's own bounds applied. */
function formOptions(form: LinkForm): DisplayOptions {
  const fixed = form.view !== ALL_TEAMS && form.view !== ROTATE;
  return resolveDisplayOptions({
    bracket: fixed ? form.view : undefined,
    rotate: form.view === ROTATE ? Number(form.rotate) || DEFAULT_ROTATE : 0,
    scale: Number(form.scale),
  });
}

/**
 * Warning when the scoreboard is not public, so the screen needs an account (unless
 * the link carries a token) or shows nothing.
 */
function VisibilityNotice({ hasToken }: { hasToken: boolean }) {
  const { t } = useTranslation();
  const { data: items } = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const visibility = items?.find((i) => i.key === "visibility.scoreboard")?.value;
  if (visibility === undefined || visibility === "public") return null;
  if (visibility === "authenticated" && hasToken) return null;

  const message =
    visibility === "hidden"
      ? t("admin.display.visibility_hidden", {
          defaultValue: "The scoreboard is hidden: the screen will only show a notice.",
        })
      : t("admin.display.visibility_authenticated", {
          defaultValue:
            "The scoreboard is only visible to signed-in accounts: sign in on the screen before opening the link.",
        });

  return (
    <Banner tone="amber" icon={EyeOff}>
      {message}{" "}
      <Link to="/admin/settings" className="underline underline-offset-4">
        {t("admin.display.change_visibility", { defaultValue: "Change the visibility" })}
      </Link>
    </Banner>
  );
}

function SelectField({
  id,
  label,
  value,
  items,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  items: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={(v) => v && onChange(v)}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue className="capitalize">
            {items.find((i) => i.value === value)?.label}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {items.map((i) => (
            <SelectItem key={i.value} value={i.value} className="capitalize">
              {i.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Adds a read-only API token to the link, so the screen needs no sign-in. */
function ScreenTokenField({
  token,
  onCreated,
}: {
  token: ScreenToken | null;
  onCreated: (token: ScreenToken) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { end } = useEventPhase();
  const mutation = useMutation({
    mutationFn: () =>
      createMyToken(
        `Big screen ${new Date().toLocaleString()}`,
        SCREEN_TOKEN_SCOPES,
        screenTokenExpiry(end, Date.now()).toISOString(),
      ),
    onSuccess: (created) => {
      if (created.token) onCreated({ token: created.token, expiresAt: created.expires_at });
      void queryClient.invalidateQueries({ queryKey: ["my-tokens"] });
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.display.token_error", { defaultValue: "Could not create the token" }),
        ),
      ),
  });

  if (token) {
    const date = token.expiresAt ? new Date(token.expiresAt).toLocaleString() : "—";
    return (
      <Banner tone="green" icon={KeyRound}>
        {t("admin.display.token_added_until", {
          date,
          defaultValue:
            "The link carries a read-only token until {{date}}: the screen shows the scoreboard and broadcasts without signing in. Anyone with the link can see them too. Revoke the “Big screen” token in your account settings to disable it sooner.",
        })}
      </Banner>
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
      <p className="text-sm text-muted-foreground">
        {t("admin.display.token_hint", {
          defaultValue: "No sign-in on the screen: add a read-only token to the link.",
        })}
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        <KeyRound />
        {t("admin.display.token_add", { defaultValue: "Add a screen token" })}
      </Button>
    </div>
  );
}

/** Generated link with a copy action. */
function LinkOutput({ url }: { url: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  function copy() {
    copyToClipboard(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
    toast.success(t("admin.display.link_copied", { defaultValue: "Link copied" }));
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor="display-link">
        {t("admin.display.field_link", { defaultValue: "Link" })}
      </Label>
      <div className="flex flex-wrap gap-2">
        <Input
          id="display-link"
          readOnly
          value={url}
          className="min-w-0 flex-1 font-mono"
          onFocus={(e) => e.target.select()}
        />
        <Button variant="outline" onClick={copy}>
          {copied ? <Check className="text-green-600" /> : <Copy />}
          {t("common.copy", { defaultValue: "Copy" })}
        </Button>
      </div>
    </div>
  );
}

/** Settings of a `/display` screen and the link that opens it. */
export function DisplayLinkDialog({
  brackets,
  onClose,
}: {
  brackets: string[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState<LinkForm>(INITIAL_FORM);
  const [token, setToken] = useState<ScreenToken | null>(null);
  const patch = (p: Partial<LinkForm>) => setForm((f) => ({ ...f, ...p }));
  const fragment = token ? `#token=${encodeURIComponent(token.token)}` : "";
  const url = `${window.location.origin}${displayPath(formOptions(form))}${fragment}`;

  const views = [
    { value: ALL_TEAMS, label: t("admin.display.view_all", { defaultValue: "All teams" }) },
    ...(brackets.length > 0
      ? [
          {
            value: ROTATE,
            label: t("admin.display.view_rotate", {
              defaultValue: "All teams, then each bracket in turn",
            }),
          },
        ]
      : []),
    ...brackets.map((b) => ({ value: b, label: b })),
  ];
  const resolutions = [
    { value: "1", label: "1080p" },
    { value: "2", label: "4K" },
  ];

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {t("admin.scoreboard.big_screen", { defaultValue: "Big screen" })}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <VisibilityNotice hasToken={token !== null} />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              id="display-view"
              label={t("admin.display.field_view", { defaultValue: "Show" })}
              value={form.view}
              items={views}
              onChange={(view) => patch({ view })}
            />
            <SelectField
              id="display-resolution"
              label={t("admin.display.field_resolution", { defaultValue: "Screen resolution" })}
              value={form.scale}
              items={resolutions}
              onChange={(scale) => patch({ scale })}
            />
            {form.view === ROTATE && (
              <div className="space-y-1.5">
                <Label htmlFor="display-rotate">
                  {t("admin.display.field_rotate", { defaultValue: "Seconds per view" })}
                </Label>
                <Input
                  id="display-rotate"
                  type="number"
                  min={ROTATE_RANGE[0]}
                  max={ROTATE_RANGE[1]}
                  value={form.rotate}
                  onChange={(e) => patch({ rotate: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  {t("admin.display.hint_range", {
                    min: ROTATE_RANGE[0],
                    max: ROTATE_RANGE[1],
                    defaultValue: "Between {{min}} and {{max}}",
                  })}
                </p>
              </div>
            )}
          </div>
          <ScreenTokenField token={token} onCreated={setToken} />
          <LinkOutput url={url} />
        </div>
        <DialogFooter>
          <a href={url} target="_blank" rel="noreferrer" className={buttonVariants()}>
            <ExternalLink />
            {t("admin.display.open", { defaultValue: "Open" })}
          </a>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
