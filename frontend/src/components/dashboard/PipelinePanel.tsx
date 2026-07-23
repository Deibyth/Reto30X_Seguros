import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fetchPipeline } from "@/lib/analytics";
import type { PipelineSummary } from "@/lib/analytics";
import { Loader2, AlertCircle, Activity, Users, CheckCircle, FileText, TrendingUp } from "lucide-react";

function StatCard({ icon: Icon, label, value, sub }: { icon: React.ElementType; label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-5">
      <div className="flex size-12 items-center justify-center rounded-lg bg-colsubsidio-blue/10">
        <Icon className="size-6 text-colsubsidio-blue" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold text-foreground">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

function StatusChart({ data }: { data: PipelineSummary }) {
  const chartData = Object.entries(data.applications_by_status).map(([status, count]) => ({
    status,
    count,
  }));

  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Aplicaciones por Estado</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis type="number" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
          <YAxis
            type="category"
            dataKey="status"
            tick={{ fontSize: 12 }}
            stroke="hsl(var(--muted-foreground))"
            width={90}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              color: "hsl(var(--popover-foreground))",
            }}
          />
          <Bar dataKey="count" fill="#0067B1" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function AbandonTable({ data }: { data: PipelineSummary }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Abandono por Sección</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="pb-2 font-medium">Sección</th>
              <th className="pb-2 text-right font-medium">Abandonos</th>
            </tr>
          </thead>
          <tbody>
            {data.abandon_at_section.map((row) => (
              <tr key={row.section} className="border-b border-border/50">
                <td className="py-2 capitalize">{row.section.replace(/_/g, " ")}</td>
                <td className="py-2 text-right font-medium">{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PipelinePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "pipeline"],
    queryFn: fetchPipeline,
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
        <p className="text-sm">Error al cargar datos del pipeline</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <StatCard icon={Users} label="Sesiones Totales" value={data.total_sessions} />
        <StatCard icon={Activity} label="Sesiones Activas" value={data.active_sessions} />
        <StatCard icon={CheckCircle} label="Completadas" value={data.completed_sessions} />
        <StatCard icon={FileText} label="Aplicaciones" value={data.total_applications} />
        <StatCard
          icon={TrendingUp}
          label="Tasa de Conversión"
          value={`${data.conversion_rate.toFixed(1)}%`}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <StatusChart data={data} />
        <AbandonTable data={data} />
      </div>
    </div>
  );
}
