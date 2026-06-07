import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Outlet, useNavigate } from "@tanstack/react-router";
import { Settings, Shield } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/language-switcher";
import { NotificationPopover } from "@/components/notification-popover";
import { NotificationToastListener } from "@/components/notification-toast-listener";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { getPublishedPages, type PublicPageSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";

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

function TopNav({ navPages }: { navPages: PublicPageSummary[] }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { name, logoUrl } = useBranding();

  const navLinkCls =
    "px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/60 transition-colors [&.active]:text-foreground [&.active]:font-medium";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-screen-xl items-center gap-6 px-4">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 font-bold text-lg tracking-tight">
          {logoUrl && <img src={logoUrl} alt="" className="h-7 w-7 object-contain" />}
          {name}
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1 text-sm text-muted-foreground">
          <Link to="/challenges" className={navLinkCls}>
            {t("nav.challenges")}
          </Link>
          <Link to="/scoreboard" className={navLinkCls}>
            {t("nav.scoreboard")}
          </Link>
          <Link to="/team" className={navLinkCls}>
            {t("nav.teams")}
          </Link>
          {navPages.map((p) => (
            <Link key={p.slug} to="/p/$slug" params={{ slug: p.slug }} className={navLinkCls}>
              {p.title}
            </Link>
          ))}
        </nav>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />

          {user && <NotificationPopover />}
          {user && <NotificationToastListener />}

          {user?.role === "admin" && (
            <Link to="/admin" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              <Shield className="h-4 w-4 mr-1.5" />
              {t("nav.admin")}
            </Link>
          )}

          {user && (
            <Link to="/settings" className={buttonVariants({ variant: "ghost", size: "icon" })}>
              <Settings className="h-4 w-4" />
            </Link>
          )}

          {user && (
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                await logout();
                navigate({ to: "/login" });
              }}
            >
              {t("common.sign_out")}
            </Button>
          )}
        </div>
      </div>
    </header>
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
