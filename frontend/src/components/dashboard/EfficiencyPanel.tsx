import { useQuery } from "@tanstack/react-query";
import { fetchEfficiency } from "@/lib/analytics";
import { Loader2, AlertCircle, MessageSquare, Database, Wrench, BarChart3 } from "lucide-react";

function StatCard({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-5">
      <div className="flex size-12 items-center justify-center rounded-lg bg-colsubsidio-blue/10">
        <Icon className="size-6 text-colsubsidio-blue" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold text-foreground">{value}</p>
      </div>
    </div>
  );
}

export function EfficiencyPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "efficiency"],
    queryFn: fetchEfficiency,
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
        <p className="text-sm">Error al cargar datos de eficiencia</p>
      </div>
    );
  }

  const errorRate = data.total_conversations > 0
    ? ((data.sessions_with_tool_errors / data.total_conversations) * 100).toFixed(1)
    : "0";

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={MessageSquare} label="Mensajes Prom./Sesión" value={data.avg_messages_per_completed_session.toFixed(1)} />
        <StatCard icon={Database} label="Campos Recolectados Prom." value={data.avg_fields_collected.toFixed(1)} />
        <StatCard icon={BarChart3} label="Total Conversaciones" value={data.total_conversations} />
        <StatCard icon={Wrench} label="Sesiones con Error" value={data.sessions_with_tool_errors} />
      </div>

      {/* Error rate bar */}
      <div className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Tasa de Errores</h3>
        <div className="flex items-center gap-4">
          <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-colsubsidio-blue transition-all"
              style={{ width: `${Math.min(parseFloat(errorRate), 100)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-muted-foreground">{errorRate}%</span>
        </div>
      </div>

      {/* Top omitted fields table */}
      <div className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Campos Más Omitidos</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="pb-2 font-medium">Campo</th>
                <th className="pb-2 text-right font-medium">Veces Omitido</th>
              </tr>
            </thead>
            <tbody>
              {data.top_omitted_fields.length === 0 ? (
                <tr>
                  <td colSpan={2} className="py-6 text-center text-muted-foreground">
                    No hay campos omitidos registrados
                  </td>
                </tr>
              ) : (
                data.top_omitted_fields.map((row) => (
                  <tr key={row.field} className="border-b border-border/50">
                    <td className="py-2 capitalize">{row.field.replace(/_/g, " ")}</td>
                    <td className="py-2 text-right font-medium">{row.count}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
