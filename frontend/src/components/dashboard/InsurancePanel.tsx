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
import { fetchInsurance } from "@/lib/analytics";
import type {} from "@/lib/analytics";
import {
  Loader2,
  AlertCircle,
  ShieldCheck,
  DollarSign,
  AlertTriangle,
} from "lucide-react";

const COLORS = ["#0067B1", "#FFD000", "#4ECDC4", "#FF6B6B", "#95E1D3", "#C7C7C7", "#F9A825"];

const STATUS_COLORS: Record<string, string> = {
  activo: "#22C55E",
  cancelado: "#EF4444",
  vencido: "#F59E0B",
};

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
}) {
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

export function InsurancePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "insurance"],
    queryFn: fetchInsurance,
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
        <p className="text-sm">Error al cargar datos de seguros</p>
      </div>
    );
  }

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("es-CO", {
      style: "currency",
      currency: "COP",
      maximumFractionDigits: 0,
    }).format(n);

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={ShieldCheck}
          label="Total Pólizas"
          value={data.total_policies.toLocaleString()}
        />
        <StatCard
          icon={ShieldCheck}
          label="Pólizas Activas"
          value={data.active_policies.toLocaleString()}
        />
        <StatCard
          icon={DollarSign}
          label="Primas Totales"
          value={formatCurrency(data.total_premiums)}
        />
        <StatCard
          icon={AlertTriangle}
          label="Reclamaciones"
          value={data.claims_stats.total.toLocaleString()}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Polizas por estado */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            Pólizas por Estado
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.by_status} layout="vertical" margin={{ left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                type="number"
                tick={{ fontSize: 12 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <YAxis
                type="category"
                dataKey="estado"
                tick={{ fontSize: 12 }}
                stroke="hsl(var(--muted-foreground))"
                width={80}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: "hsl(var(--popover-foreground))",
                }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.by_status.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={STATUS_COLORS[entry.estado] || COLORS[i % COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Polizas por tipo */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            Distribución por Tipo de Seguro
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.by_type}
                dataKey="count"
                nameKey="tipo"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ payload }) =>
                  `${payload?.tipo} ${payload ? `(${((payload.count / data.by_type.reduce((a, b) => a + b.count, 0)) * 100).toFixed(0)}%)` : ""}`
                }
                labelLine
              >
                {data.by_type.map((_, i) => (
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

        {/* Claims summary */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            Reclamaciones
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-muted p-4">
              <p className="text-xs text-muted-foreground">Totales</p>
              <p className="text-2xl font-bold text-foreground">
                {data.claims_stats.total}
              </p>
            </div>
            <div className="rounded-lg bg-muted p-4">
              <p className="text-xs text-muted-foreground">Aprobadas</p>
              <p className="text-2xl font-bold text-green-600">
                {data.claims_stats.approved}
              </p>
            </div>
            <div className="col-span-2 rounded-lg bg-muted p-4">
              <p className="text-xs text-muted-foreground">Monto Total Reclamado</p>
              <p className="text-2xl font-bold text-foreground">
                {formatCurrency(data.claims_stats.total_amount)}
              </p>
            </div>
          </div>
        </div>

        {/* Premiums by type */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            Primas por Tipo de Seguro
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.by_type} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                type="number"
                tick={{ fontSize: 12 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <YAxis
                type="category"
                dataKey="tipo"
                tick={{ fontSize: 10 }}
                stroke="hsl(var(--muted-foreground))"
                width={100}
              />
              <Tooltip
                formatter={(value) =>
                  typeof value === "number" ? formatCurrency(value) : value
                }
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: "hsl(var(--popover-foreground))",
                }}
              />
              <Bar dataKey="premiums" fill="#0067B1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
