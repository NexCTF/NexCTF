import { notifyManager, type QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext } from "react";
import { login as apiLogin, logout as apiLogout, getMe, type User } from "@/lib/api";
import { closeSSE } from "@/lib/sse";

export interface AuthContext {
  user: User | null;
  isLoading: boolean;
  login: (
    username: string,
    password: string,
    totpCode?: string,
    captchaToken?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  /** Reload the user after a sign-in that did not go through `login`. */
  refresh: () => Promise<void>;
}

/** Queries kept when the signed-in account changes. */
function keptAcrossAccounts(queryKey: readonly unknown[]): boolean {
  const [root, sub] = queryKey;
  return (root === "auth" && sub === "me") || (root === "info" && sub === "public");
}

async function setIdentity(qc: QueryClient, user: User | null): Promise<void> {
  closeSSE();
  qc.removeQueries({ predicate: (query) => !keptAcrossAccounts(query.queryKey) });
  qc.setQueryData(["auth", "me"], user);
  await new Promise<void>((resolve) => notifyManager.schedule(resolve));
}

/** Exported so tests can provide a value without mounting the real provider. */
export const AuthCtx = createContext<AuthContext | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();

  const { data: user = null, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const refresh = useCallback(async () => {
    await setIdentity(qc, await getMe());
  }, [qc]);

  const login = useCallback(
    async (username: string, password: string, totpCode?: string, captchaToken?: string) => {
      await apiLogin(username, password, totpCode, captchaToken);
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    await setIdentity(qc, null);
  }, [qc]);

  return (
    <AuthCtx.Provider value={{ user, isLoading, login, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): AuthContext {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
