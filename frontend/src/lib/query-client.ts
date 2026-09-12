import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";

/**
 * A session killed server-side (revoked by an admin, expired, signed out
 * elsewhere) surfaces only as 401s on whatever the page queries next. The
 * cached identity would otherwise stay valid until its staleTime elapsed,
 * leaving the user on a page that can no longer load anything. Dropping it
 * here lets the route guards send them to login on the next render.
 */
function forgetIdentityOn401(client: QueryClient, error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    client.setQueryData(["auth", "me"], null);
  }
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
    queryCache: new QueryCache({
      onError: (error) => forgetIdentityOn401(client, error),
    }),
    mutationCache: new MutationCache({
      onError: (error) => forgetIdentityOn401(client, error),
    }),
  });
  return client;
}
