import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  type AnyRoute,
  createMemoryHistory,
  createRootRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import { type AuthContext, AuthCtx } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";

interface RenderRouteOptions {
  /** URL to start at, search string included. */
  path?: string;
  /** Route pattern, when it differs from `path` — e.g. "/p/$slug". */
  routePath?: string;
  /** Auth state the page sees; defaults to a signed-out visitor. */
  auth?: Partial<AuthContext>;
}

/**
 * Render a single file route through a memory router.
 *
 * Only the route under test is attached, and the app's real root is reduced to
 * the providers a page can't render without. Branding falls back to its default
 * context, and auth is supplied directly rather than fetched.
 */
export function renderRoute(
  route: AnyRoute,
  { path = "/", routePath, auth }: RenderRouteOptions = {},
) {
  const authValue: AuthContext = {
    user: null,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...auth,
  };
  const rootRoute = createRootRoute({
    component: () => (
      <ThemeProvider>
        <AuthCtx.Provider value={authValue}>
          <Outlet />
        </AuthCtx.Provider>
      </ThemeProvider>
    ),
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  // File routes carry no id/path until the generated tree calls `update` on them.
  const pattern = routePath ?? path.split("?")[0];
  const child = route.update({
    id: pattern,
    path: pattern,
    getParentRoute: () => rootRoute,
    // biome-ignore lint/suspicious/noExplicitAny: mirrors routeTree.gen.ts
  } as any);

  const router = createRouter({
    routeTree: rootRoute.addChildren([child]),
    history: createMemoryHistory({ initialEntries: [path] }),
    // Routes other than the one under test are absent; redirects land here.
    defaultNotFoundComponent: () => null,
    context: { queryClient },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      {/* biome-ignore lint/suspicious/noExplicitAny: test router isn't the registered app router */}
      <RouterProvider router={router as any} />
    </QueryClientProvider>,
  );
  return { ...result, router, auth: authValue };
}
