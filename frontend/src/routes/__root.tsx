import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
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
          <div className="min-h-screen bg-background text-foreground">
            <Outlet />
            <Toaster />
          </div>
        </AuthProvider>
      </BrandingProvider>
    </ThemeProvider>
  ),
});
