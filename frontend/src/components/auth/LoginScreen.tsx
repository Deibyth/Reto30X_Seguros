import { useState, type FormEvent } from "react";
import { Loader2, AlertCircle, LogIn } from "lucide-react";

interface LoginScreenProps {
  onLogin: (token: string, name: string) => void;
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Error ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      onLogin(data.token, data.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de conexión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="rounded-xl border bg-card p-8 shadow-lg">
          <div className="mb-6 flex flex-col items-center text-center">
            <img
              src="/logo-colsubsidio.svg"
              alt="Logo Colsubsidio"
              className="mb-4 h-9 w-auto"
            />
            <h1 className="text-xl font-bold text-foreground">
              Panel de Supervisión
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Protección Inteligente 360°
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="username"
                className="mb-1.5 block text-sm font-medium text-foreground"
              >
                Usuario
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Ingrese su usuario"
                required
                autoFocus
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-foreground"
              >
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Ingrese su contraseña"
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-colsubsidio-blue px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-colsubsidio-blue/90 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <LogIn className="size-4" />
              )}
              {loading ? "Ingresando…" : "Ingresar"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
