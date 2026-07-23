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
import { fetchCustomers } from "@/lib/analytics";
import { Loader2, AlertCircle, Users, Award, Clock } from "lucide-react";

const COLORS = ["#0067B1", "#FFD000", "#4ECDC4", "#FF6B6B", "#95E1D3"];

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

export function CustomerPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "customers"],
    queryFn: fetchCustomers,
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
        <p className="text-sm">Error al cargar perfil de clientes</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard icon={Users} label="Total Clientes" value={data.total_customers.toLocaleString()} />
        <StatCard icon={Award} label="Score Crediticio Prom." value={data.avg_credit_score.toFixed(0)} />
        <StatCard icon={Clock} label="Antigüedad Prom." value={`${data.avg_tenure_months.toFixed(0)} meses`} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Salary distribution */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Distribución Salarial</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.salary_distribution} margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 11 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: "hsl(var(--popover-foreground))",
                }}
              />
              <Bar dataKey="count" fill="#0067B1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Contract types */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Tipos de Contrato</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.contract_types}
                dataKey="count"
                nameKey="type"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ payload }) =>
                  `${payload?.type} ${payload ? `(${((payload.count / data.contract_types.reduce((a, b) => a + b.count, 0)) * 100).toFixed(0)}%)` : ""}`
                }
                labelLine
              >
                {data.contract_types.map((_, i) => (
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
