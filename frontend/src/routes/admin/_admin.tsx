import { createFileRoute, Link, Outlet, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  Bell,
  BookOpen,
  CalendarDays,
  ClipboardList,
  Clock,
  Files,
  Flag,
  FolderOpen,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Puzzle,
  ScrollText,
  Settings,
  SlidersHorizontal,
  Tag,
  Trophy,
  Users,
  UsersRound,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/language-switcher";
import { NotificationToastListener } from "@/components/notification-toast-listener";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";

export const Route = createFileRoute("/admin/_admin")({
  component: AdminLayout,
});

type NavItem = {
  to: string;
  label: string;
  icon: React.ElementType;
  exact?: boolean;
};
type NavSection = { heading: string; items: NavItem[] };

const NAV_SECTIONS: NavSection[] = [
  {
    heading: "admin.nav.section.overview",
    items: [
      {
        to: "/admin",
        label: "admin.nav.dashboard",
        icon: LayoutDashboard,
        exact: true,
      },
      { to: "/admin/events", label: "admin.nav.events", icon: CalendarDays },
      { to: "/admin/scoreboard", label: "admin.nav.scoreboard", icon: Trophy },
      {
        to: "/admin/score-adjustments",
        label: "admin.nav.score_adjustments",
        icon: SlidersHorizontal,
      },
      {
        to: "/admin/submissions",
        label: "admin.nav.submissions",
        icon: ClipboardList,
      },
    ],
  },
  {
    heading: "admin.nav.section.manage",
    items: [
      { to: "/admin/challenges", label: "admin.nav.challenges", icon: Flag },
      {
        to: "/admin/categories",
        label: "admin.nav.categories",
        icon: FolderOpen,
      },
      { to: "/admin/tags", label: "admin.nav.tags", icon: Tag },
      { to: "/admin/users", label: "admin.nav.users", icon: Users },
      { to: "/admin/teams", label: "admin.nav.teams", icon: UsersRound },
      {
        to: "/admin/custom-fields",
        label: "admin.nav.custom_fields",
        icon: ListChecks,
      },
      { to: "/admin/files", label: "admin.nav.files", icon: Files },
      { to: "/admin/pages", label: "admin.nav.pages", icon: ScrollText },
    ],
  },
  {
    heading: "admin.nav.section.system",
    items: [
      { to: "/admin/plugins", label: "admin.nav.plugins", icon: Puzzle },
      {
        to: "/admin/oauth-providers",
        label: "admin.nav.oauth_providers",
        icon: KeyRound,
      },
      {
        to: "/admin/oauth-clients",
        label: "admin.nav.oauth_clients",
        icon: KeyRound,
      },
      { to: "/admin/scheduler", label: "admin.nav.scheduler", icon: Clock },
      {
        to: "/admin/notifications",
        label: "admin.nav.notifications",
        icon: Bell,
      },
      { to: "/admin/settings", label: "admin.nav.settings", icon: Settings },
    ],
  },
];

const ACTIVE_CLS = "bg-background font-medium shadow-sm text-foreground";
const INACTIVE_CLS = "text-muted-foreground hover:bg-background/60 hover:text-foreground";
const BASE_CLS = "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors";

function AdminLayout() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { name, logoUrl } = useBranding();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/40 sticky top-0 h-screen overflow-hidden">
        {/* Brand */}
        <div className="flex h-14 items-center border-b px-4 gap-2">
          {logoUrl && <img src={logoUrl} alt="" className="h-6 w-6 object-contain shrink-0" />}
          <span className="font-bold tracking-tight truncate">{name}</span>
          <span className="ml-auto rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary uppercase tracking-wider shrink-0">
            Admin
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
          {NAV_SECTIONS.map(({ heading, items }) => (
            <div key={heading}>
              <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {t(heading)}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, label, icon: Icon, exact }) => (
                  <Link
                    key={to}
                    to={to}
                    activeOptions={{ exact }}
                    activeProps={{ className: `${BASE_CLS} ${ACTIVE_CLS}` }}
                    inactiveProps={{ className: `${BASE_CLS} ${INACTIVE_CLS}` }}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {t(label)}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom */}
        <div className="border-t px-3 py-3 space-y-1">
          <Link to="/" className={`${BASE_CLS} ${INACTIVE_CLS}`}>
            <ArrowLeft className="h-4 w-4" />
            {t("admin.nav.back_to_site")}
          </Link>

          <a
            href="/api/v1/docs"
            target="_blank"
            rel="noopener noreferrer"
            className={`${BASE_CLS} ${INACTIVE_CLS}`}
          >
            <BookOpen className="h-4 w-4" />
            API Docs
          </a>

          <button
            type="button"
            onClick={async () => {
              await logout();
              navigate({ to: "/login" });
            }}
            className={`w-full ${BASE_CLS} ${INACTIVE_CLS}`}
          >
            <LogOut className="h-4 w-4" />
            {t("common.sign_out")}
          </button>

          <div className="flex items-center gap-1 pt-1">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Page content */}
      <div className="flex flex-1 flex-col">
        <Outlet />
      </div>

      <NotificationToastListener />
    </div>
  );
}
