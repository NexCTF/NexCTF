import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface ThemeContext {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  applyDefaultTheme: (theme: Theme) => void;
}

const Ctx = createContext<ThemeContext | null>(null);

const STORAGE_KEY = "nexctf-theme";

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Narrow an arbitrary string to a known theme name. */
export function parseTheme(value: string | null): Theme | null {
  return value === "light" || value === "dark" || value === "system" ? value : null;
}

/** The stored choice, or null when the visitor has never picked one. */
function readStoredTheme(): Theme | null {
  return parseTheme(localStorage.getItem(STORAGE_KEY));
}

function resolveTheme(theme: Theme): ResolvedTheme {
  return theme === "system" ? getSystemTheme() : theme;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStoredTheme() ?? "system");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveTheme(theme));

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  }, []);

  const applyDefaultTheme = useCallback((t: Theme) => {
    if (readStoredTheme()) return;
    setThemeState(t);
  }, []);

  useEffect(() => {
    const apply = () => {
      const resolved = resolveTheme(theme);
      document.documentElement.classList.toggle("dark", resolved === "dark");
      setResolvedTheme(resolved);
    };

    apply();
    if (theme !== "system") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  return (
    <Ctx.Provider value={{ theme, resolvedTheme, setTheme, applyDefaultTheme }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme(): ThemeContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
