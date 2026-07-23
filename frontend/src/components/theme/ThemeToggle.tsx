import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { resolved, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg
                 text-muted-foreground transition-colors
                 hover:bg-accent hover:text-accent-foreground
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={resolved === "dark" ? "Activar modo claro" : "Activar modo oscuro"}
      title={resolved === "dark" ? "Modo claro" : "Modo oscuro"}
    >
      {/* Sun — visible in dark mode (switches to light) */}
      <svg
        className={`absolute h-5 w-5 transition-all ${
          resolved === "dark" ? "scale-100 opacity-100" : "scale-0 opacity-0"
        }`}
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2" />
        <path d="M12 20v2" />
        <path d="m4.93 4.93 1.41 1.41" />
        <path d="m17.66 17.66 1.41 1.41" />
        <path d="M2 12h2" />
        <path d="M20 12h2" />
        <path d="m6.34 17.66-1.41 1.41" />
        <path d="m19.07 4.93-1.41 1.41" />
      </svg>

      {/* Moon — visible in light mode (switches to dark) */}
      <svg
        className={`absolute h-5 w-5 transition-all ${
          resolved === "dark" ? "scale-0 opacity-0" : "scale-100 opacity-100"
        }`}
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
      </svg>
    </button>
  );
}
