import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSupervision, type SupervisionSession, type SupervisionMessage } from "@/lib/analytics";
import { Loader2, AlertCircle, MessageSquare, X } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  perfilando: "bg-blue-500",
  recomendando: "bg-amber-500",
  cotizando: "bg-purple-500",
  inicio: "bg-gray-500",
  completado: "bg-green-500",
};

const STATUS_LABELS: Record<string, string> = {
  perfilando: "Perfilando",
  recomendando: "Recomendando",
  cotizando: "Cotizando",
  inicio: "Inicio",
  completado: "Completado",
};

function ConversationModal({
  session,
  onClose,
}: {
  session: SupervisionSession;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-xl border bg-card shadow-xl animate-fade-in">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Conversación — {session.customer_name || "Anónimo"}
            </h3>
            <p className="text-xs text-muted-foreground">
              {session.product_context || "Sin producto"} · {session.total_messages} mensajes
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {session.conversations.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No hay mensajes en esta sesión.
            </p>
          )}
          {session.conversations.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: SupervisionMessage }) {
  const isUser = message.rol === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
          isUser
            ? "bg-colsubsidio-blue text-white"
            : "bg-muted text-foreground"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{message.mensaje}</p>
        <p
          className={`mt-1 text-[10px] ${
            isUser ? "text-white/60" : "text-muted-foreground"
          }`}
        >
          {new Date(message.created_at).toLocaleString("es-CO", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

function StatusBadge({ estado }: { estado: string }) {
  const color = STATUS_COLORS[estado] || "bg-gray-400";
  const label = STATUS_LABELS[estado] || estado;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${color} text-white`}
    >
      <span className="size-1.5 rounded-full bg-white/70" />
      {label}
    </span>
  );
}

function SupervisionTable({
  sessions,
  onViewConversation,
}: {
  sessions: SupervisionSession[];
  onViewConversation: (s: SupervisionSession) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="whitespace-nowrap pb-3 pr-4 font-medium">Fecha</th>
            <th className="whitespace-nowrap pb-3 pr-4 font-medium">Cliente</th>
            <th className="whitespace-nowrap pb-3 pr-4 font-medium">Estado</th>
            <th className="whitespace-nowrap pb-3 pr-4 font-medium">Producto</th>
            <th className="whitespace-nowrap pb-3 pr-4 font-medium">Intención</th>
            <th className="whitespace-nowrap pb-3 pr-4 text-center font-medium">Msgs</th>
            <th className="whitespace-nowrap pb-3 pr-4 text-center font-medium">Póliza</th>
            <th className="whitespace-nowrap pb-3 font-medium">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr
              key={s.id}
              className="border-b border-border/50 transition-colors hover:bg-muted/30"
            >
              <td className="whitespace-nowrap py-3 pr-4 text-muted-foreground">
                {new Date(s.created_at).toLocaleDateString("es-CO", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                })}
              </td>
              <td className="whitespace-nowrap py-3 pr-4 font-medium text-foreground">
                {s.customer_name || "—"}
              </td>
              <td className="whitespace-nowrap py-3 pr-4">
                <StatusBadge estado={s.estado_actual} />
              </td>
              <td className="whitespace-nowrap py-3 pr-4 text-muted-foreground">
                {s.product_context || "—"}
              </td>
              <td className="whitespace-nowrap py-3 pr-4 text-muted-foreground">
                {s.ultima_intencion || "—"}
              </td>
              <td className="whitespace-nowrap py-3 pr-4 text-center">
                <span className="inline-flex size-7 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
                  {s.total_messages}
                </span>
              </td>
              <td className="whitespace-nowrap py-3 pr-4 text-center">
                {s.has_policy ? (
                  <span className="text-green-600">✅ Sí</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="whitespace-nowrap py-3">
                <button
                  onClick={() => onViewConversation(s)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-colsubsidio-blue/10 px-3 py-1.5 text-xs font-medium text-colsubsidio-blue transition-colors hover:bg-colsubsidio-blue/20"
                >
                  <MessageSquare className="size-3.5" />
                  Ver Conversación
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface SupervisionPanelProps {
  token: string;
}

export function SupervisionPanel({ token }: SupervisionPanelProps) {
  const [selectedSession, setSelectedSession] = useState<SupervisionSession | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "supervision", token],
    queryFn: () => fetchSupervision(token),
    enabled: !!token,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-8 animate-spin text-colsubsidio-blue" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center gap-3 py-20 text-destructive">
        <AlertCircle className="size-6" />
        <p className="text-sm">Error al cargar datos de supervisión</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Supervisión de Sesiones
          </h2>
          <p className="text-sm text-muted-foreground">
            {data.length} sesion{data.length !== 1 ? "es" : ""} encontrada
            {data.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      <div className="rounded-xl border bg-card p-5">
        {data.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No hay sesiones activas para supervisar.
          </p>
        ) : (
          <SupervisionTable
            sessions={data}
            onViewConversation={setSelectedSession}
          />
        )}
      </div>

      {selectedSession && (
        <ConversationModal
          session={selectedSession}
          onClose={() => setSelectedSession(null)}
        />
      )}
    </div>
  );
}
