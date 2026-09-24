import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { PluginHostBridge } from "@/components/plugin-host-bridge";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth";
import { BrandingProvider } from "@/lib/branding";
import { ThemeProvider } from "@/lib/theme";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <ThemeProvider>
      <BrandingProvider>
        <AuthProvider>
          <PluginHostBridge />
          <div className="min-h-screen bg-background text-foreground">
            <Outlet />
            <Toaster />
          </div>
        </AuthProvider>
      </BrandingProvider>
    </ThemeProvider>
  ),
});
