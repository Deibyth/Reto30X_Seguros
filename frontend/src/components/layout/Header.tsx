import { ThemeToggle } from "@/components/theme/ThemeToggle";

interface HeaderProps {
  onNavigate?: (view: "chat" | "dashboard") => void;
  currentView?: "chat" | "dashboard";
}

export function Header({ onNavigate, currentView }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex items-center justify-between px-4 py-3">
        {/* Logo Colsubsidio */}
        <a
          href="https://www.colsubsidio.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3"
        >
          <img
            src="/logo-colsubsidio.svg"
            alt="Logo Colsubsidio"
            className="h-7 w-auto"
          />
        </a>

        {/* Navigation + name + toggle */}
        <div className="flex items-center gap-3">
          {/* View switcher */}
          {onNavigate && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => onNavigate("chat")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  currentView === "chat"
                    ? "bg-colsubsidio-blue text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => onNavigate("dashboard")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  currentView === "dashboard"
                    ? "bg-colsubsidio-blue text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Dashboard
              </button>
            </div>
          )}

          <span className="hidden text-sm text-muted-foreground/60 sm:inline">—</span>
          <span className="text-sm font-medium text-muted-foreground sm:text-base">
            Protección Inteligente 360°
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
