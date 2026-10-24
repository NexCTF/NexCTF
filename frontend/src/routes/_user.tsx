import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Outlet, useNavigate } from "@tanstack/react-router";
import { ExternalLink, LogIn, LogOut, Settings, Shield } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/language-switcher";
import { NavSheet } from "@/components/nav-sheet";
import { NotificationPopover } from "@/components/notification-popover";
import { NotificationToastListener } from "@/components/notification-toast-listener";
import { PluginNavLinks, usePluginPages } from "@/components/plugin-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";
import { getPublicInfo, getPublishedPages, type PublicPageSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_user")({
  component: UserLayout,
});

function UserLayout() {
  const { data: pages = [] } = useQuery({
    queryKey: ["published-pages"],
    queryFn: getPublishedPages,
    staleTime: 5 * 60 * 1000,
  });

  const footerPages = pages.filter((p) => p.nav_placement === "footer");

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav navPages={pages.filter((p) => p.nav_placement === "nav")} />
      <main className="flex-1">
        <Outlet />
      </main>
      {footerPages.length > 0 && <SiteFooter pages={footerPages} />}
    </div>
  );
}

const NAV_LINK_CLS =
  "px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/60 transition-colors [&.active]:text-foreground [&.active]:font-medium";
const MENU_ROW_CLS = `${NAV_LINK_CLS} flex items-center gap-2 text-sm`;

function TopNav({ navPages }: { navPages: PublicPageSummary[] }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { name, logoUrl } = useBranding();

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-screen-xl items-center gap-6 px-4">
        <Link to="/" className="flex min-w-0 items-center gap-2 font-bold text-lg tracking-tight">
          {logoUrl ? (
            <img src={logoUrl} alt={name} className="h-7 max-w-40 object-contain" />
          ) : (
            <span className="truncate">{name}</span>
          )}
        </Link>

        <nav className="hidden items-center gap-1 text-sm text-muted-foreground lg:flex">
          <NavLinks navPages={navPages} className={NAV_LINK_CLS} />
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <div className="hidden lg:contents">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
          {user && <NotificationPopover />}
          <div className="hidden lg:contents">
            {user && (
              <Link
                to="/settings"
                aria-label={t("nav.settings", { defaultValue: "Settings" })}
                className={buttonVariants({ variant: "ghost", size: "icon" })}
              >
                <Settings />
              </Link>
            )}
            <AccountActions className={buttonVariants({ variant: "ghost", size: "sm" })} />
          </div>
          <div className="lg:hidden">
            <MobileMenu navPages={navPages} />
          </div>
        </div>

        {user && <NotificationToastListener />}
      </div>
    </header>
  );
}

/** Challenges, scoreboard, teams, then custom, plugin and external links. */
function NavLinks({ navPages, className }: { navPages: PublicPageSummary[]; className: string }) {
  const { t } = useTranslation();
  const pluginPages = usePluginPages("user");
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  return (
    <>
      <Link to="/challenges" className={className}>
        {t("nav.challenges")}
      </Link>
      <Link to="/scoreboard" className={className}>
        {t("nav.scoreboard")}
      </Link>
      <Link to="/team" className={className}>
        {t("nav.teams")}
      </Link>
      {navPages.map((p) => (
        <Link key={p.slug} to="/p/$slug" params={{ slug: p.slug }} className={className}>
          {p.title}
        </Link>
      ))}
      <PluginNavLinks pages={pluginPages} className={className} showIcon={false} />
      {(info?.links ?? []).map((l, i) => (
        <a
          // biome-ignore lint/suspicious/noArrayIndexKey: links have no stable id; index is the identity
          key={i}
          href={l.url}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(className, "inline-flex items-center gap-1")}
        >
          {l.name}
          <ExternalLink className="size-3" />
        </a>
      ))}
    </>
  );
}

/** Admin and sign out, or sign in when anonymous. */
function AccountActions({ className }: { className: string }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return (
      <Link to="/login" className={className}>
        <LogIn />
        {t("nav.login")}
      </Link>
    );
  }

  return (
    <>
      {user.role === "admin" && (
        <Link to="/admin" className={className}>
          <Shield />
          {t("nav.admin")}
        </Link>
      )}

      <button
        type="button"
        className={className}
        onClick={async () => {
          await logout();
          navigate({ to: "/login" });
        }}
      >
        <LogOut />
        {t("common.sign_out")}
      </button>
    </>
  );
}

/** Drawer holding the whole top nav below the `lg` breakpoint. */
function MobileMenu({ navPages }: { navPages: PublicPageSummary[] }) {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <NavSheet side="right" className="gap-4 p-4" titleClassName="px-3 text-base">
      <nav className="flex flex-col gap-0.5 text-sm text-muted-foreground">
        <NavLinks navPages={navPages} className={MENU_ROW_CLS} />
      </nav>
      <div className="flex flex-col gap-0.5 border-t pt-4 text-muted-foreground [&_svg]:size-4">
        {user && (
          <Link to="/settings" className={MENU_ROW_CLS}>
            <Settings />
            {t("nav.settings", { defaultValue: "Settings" })}
          </Link>
        )}
        <AccountActions className={MENU_ROW_CLS} />
      </div>
      <div className="mt-auto flex items-center gap-1 border-t pt-4">
        <LanguageSwitcher />
        <ThemeToggle />
      </div>
    </NavSheet>
  );
}

function SiteFooter({ pages }: { pages: PublicPageSummary[] }) {
  const { name } = useBranding();
  return (
    <footer className="border-t bg-muted/40 py-6 mt-auto">
      <div className="mx-auto max-w-screen-xl px-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>{name}</span>
        <nav className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {pages.map((p) => (
            <Link
              key={p.slug}
              to="/p/$slug"
              params={{ slug: p.slug }}
              className="hover:text-foreground transition-colors"
            >
              {p.title}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
