import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextValue {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "reto30x-theme";

function getStored(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem(STORAGE_KEY) as Theme) ?? "system";
}

function resolve(theme: Theme): "light" | "dark" {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return theme;
}

function apply(resolved: "light" | "dark") {
  document.documentElement.classList.remove("light", "dark");
  document.documentElement.classList.add(resolved);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStored);
  const [resolved, setResolved] = useState<"light" | "dark">(() => resolve(theme));

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
    const r = resolve(t);
    setResolved(r);
    apply(r);
  };

  const toggle = () => {
    setTheme(resolved === "dark" ? "light" : "dark");
  };

  // Listen to system preference changes
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (theme === "system") {
        const r = resolve("system");
        setResolved(r);
        apply(r);
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  // Apply on mount
  useEffect(() => {
    apply(resolved);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
