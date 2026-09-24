import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  Box,
  Boxes,
  ChartColumn,
  Cloud,
  Container,
  Cpu,
  Database,
  Flag,
  Gauge,
  HardDrive,
  KeyRound,
  Layers,
  List,
  type LucideIcon,
  Network,
  Puzzle,
  Server,
  Settings,
  Shield,
  Terminal,
  Users,
  Wrench,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { type PluginPageEntry, type PluginScope, pluginManifest } from "@/lib/plugins";

/** The lucide icons a plugin page may name; any other name falls back to `puzzle`. */
const PLUGIN_ICONS: Record<string, LucideIcon> = {
  activity: Activity,
  box: Box,
  boxes: Boxes,
  "chart-column": ChartColumn,
  cloud: Cloud,
  container: Container,
  cpu: Cpu,
  database: Database,
  flag: Flag,
  gauge: Gauge,
  "hard-drive": HardDrive,
  "key-round": KeyRound,
  layers: Layers,
  list: List,
  network: Network,
  puzzle: Puzzle,
  server: Server,
  settings: Settings,
  shield: Shield,
  terminal: Terminal,
  users: Users,
  wrench: Wrench,
};

export interface PluginNavPage extends PluginPageEntry {
  key: string;
  scope: PluginScope;
}

/** Resolve a manifest label for `language`, falling back to English, then any locale. */
export function pluginLabel(label: PluginPageEntry["label"], language: string): string {
  if (typeof label === "string") return label;
  return (
    label[language] ?? label[language.split("-")[0]] ?? label.en ?? Object.values(label)[0] ?? ""
  );
}

/** The nav-listed pages of every plugin bundle loaded for `scope`. */
export function usePluginPages(scope: PluginScope): PluginNavPage[] {
  const { data = [] } = useQuery({
    queryKey: ["plugins", "manifest", scope],
    queryFn: () => pluginManifest(scope),
    staleTime: Number.POSITIVE_INFINITY,
  });
  return data.flatMap((entry) => entry.pages.map((page) => ({ ...page, key: entry.key, scope })));
}

interface PluginNavLinksProps {
  pages: PluginNavPage[];
  className?: string;
  activeClassName?: string;
  inactiveClassName?: string;
  showIcon?: boolean;
}

export function PluginNavLinks({
  pages,
  className,
  activeClassName,
  inactiveClassName,
  showIcon = true,
}: PluginNavLinksProps) {
  const { i18n } = useTranslation();
  return pages.map((page) => {
    const to = page.scope === "admin" ? "/admin/plugins/$key/$" : "/plugins/$key/$";
    const Icon = PLUGIN_ICONS[page.icon ?? ""] ?? Puzzle;
    return (
      <Link
        key={`${page.key}/${page.path}`}
        to={to}
        params={{ key: page.key, _splat: page.path }}
        activeOptions={{ exact: page.path === "" }}
        className={className}
        activeProps={activeClassName ? { className: activeClassName } : undefined}
        inactiveProps={inactiveClassName ? { className: inactiveClassName } : undefined}
      >
        {showIcon && <Icon className="h-4 w-4 shrink-0" />}
        {pluginLabel(page.label, i18n.resolvedLanguage ?? i18n.language)}
      </Link>
    );
  });
}
