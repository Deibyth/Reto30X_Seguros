import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { fetchCredits } from "@/lib/analytics";
import { Loader2, AlertCircle, DollarSign, CreditCard, Calendar, BarChart3 } from "lucide-react";

const COLORS = ["#0067B1", "#FFD000", "#4ECDC4", "#FF6B6B", "#95E1D3", "#C7C7C7"];

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

export function CreditPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "credits"],
    queryFn: fetchCredits,
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
        <p className="text-sm">Error al cargar datos de créditos</p>
      </div>
    );
  }

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n);

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={CreditCard} label="Total Créditos" value={data.total_credits.toLocaleString()} />
        <StatCard icon={DollarSign} label="Volumen Total" value={formatCurrency(data.total_volume)} />
        <StatCard icon={BarChart3} label="Monto Promedio" value={formatCurrency(data.avg_amount)} />
        <StatCard icon={Calendar} label="Plazo Promedio" value={`${data.avg_term_months.toFixed(0)} meses`} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Amount by destination */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Cantidad de Créditos por Destino</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.destino_distribution} layout="vertical" margin={{ left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis
                type="category"
                dataKey="destino"
                tick={{ fontSize: 11 }}
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

        {/* Destination distribution */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Distribución de Destinos</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.destino_distribution}
                dataKey="count"
                nameKey="destino"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ payload }) =>
                  `${payload?.destino} ${payload ? `(${((payload.count / data.destino_distribution.reduce((a, b) => a + b.count, 0)) * 100).toFixed(0)}%)` : ""}`
                }
                labelLine
              >
                {data.destino_distribution.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: "hsl(var(--popover-foreground))",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
