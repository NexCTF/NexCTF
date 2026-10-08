import { Bot, Globe, KeyRound, Terminal } from "lucide-react";
import { useTranslation } from "react-i18next";
import { StatusBadge } from "@/components/status-badge";
import type { ClientCategory, ClientSource } from "@/lib/api";

const CATEGORY_STYLE = {
  ai: { tone: "red", icon: Bot },
  automation: { tone: "amber", icon: Terminal },
  browser: { tone: "muted", icon: Globe },
} as const;

/** Display names of the client categories and authentication sources. */
export function useClientLabels(): {
  category: Record<ClientCategory, string>;
  source: Record<ClientSource, string>;
} {
  const { t } = useTranslation();
  return {
    category: {
      ai: t("admin.clients.category_ai", { defaultValue: "AI" }),
      automation: t("admin.clients.category_automation", { defaultValue: "Automation" }),
      browser: t("admin.clients.category_browser", { defaultValue: "Browser" }),
    },
    source: {
      cookie: t("admin.clients.source_cookie", { defaultValue: "Browser session" }),
      token: t("admin.clients.source_token", { defaultValue: "API token" }),
    },
  };
}

/** The kind of client a user-agent was classified as. */
export function ClientCategoryBadge({ category }: { category: ClientCategory }) {
  const labels = useClientLabels();
  const { tone, icon } = CATEGORY_STYLE[category];
  return (
    <StatusBadge tone={tone} icon={icon}>
      {labels.category[category]}
    </StatusBadge>
  );
}

/** How the client authenticated, naming the API token when there is one. */
export function ClientSourceBadge({
  source,
  tokenName,
}: {
  source: ClientSource;
  tokenName: string | null;
}) {
  const { t } = useTranslation();
  const labels = useClientLabels();
  if (source === "cookie") {
    return <StatusBadge tone="muted">{labels.source.cookie}</StatusBadge>;
  }
  return (
    <StatusBadge tone="muted" icon={KeyRound}>
      {tokenName
        ? t("admin.clients.source_token_named", {
            name: tokenName,
            defaultValue: "API token: {{name}}",
          })
        : labels.source.token}
    </StatusBadge>
  );
}

/** A raw user-agent string, or a note that the client sent none. */
export function UserAgentText({
  userAgent,
  truncate = false,
}: {
  userAgent: string;
  truncate?: boolean;
}) {
  const { t } = useTranslation();
  if (!userAgent) {
    return (
      <p className="text-xs italic text-muted-foreground">
        {t("admin.clients.no_user_agent", { defaultValue: "No user-agent sent" })}
      </p>
    );
  }
  return (
    <code
      className={`block font-mono text-xs ${truncate ? "max-w-md truncate" : "break-all"}`}
      title={truncate ? userAgent : undefined}
    >
      {userAgent}
    </code>
  );
}
