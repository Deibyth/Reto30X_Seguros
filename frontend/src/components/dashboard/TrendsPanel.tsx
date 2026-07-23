import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { fetchTrends } from "@/lib/analytics";
import type {} from "@/lib/analytics";
import { Loader2, AlertCircle } from "lucide-react";

const RANGE_OPTIONS = [
  { label: "7 días", value: 7 },
  { label: "30 días", value: 30 },
  { label: "90 días", value: 90 },
] as const;

export function TrendsPanel() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics", "trends", days],
    queryFn: () => fetchTrends(days),
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
        <p className="text-sm">Error al cargar tendencias</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Range selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Mostrar:</span>
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setDays(opt.value)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              days === opt.value
                ? "bg-colsubsidio-blue text-white"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">
          Aplicaciones y Completaciones por Día
        </h3>
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              stroke="hsl(var(--muted-foreground))"
              angle={-45}
              textAnchor="end"
              height={60}
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
            <Legend />
            <Line
              type="monotone"
              dataKey="applications"
              stroke="#0067B1"
              strokeWidth={2}
              dot={false}
              name="Aplicaciones"
            />
            <Line
              type="monotone"
              dataKey="completions"
              stroke="#FFD000"
              strokeWidth={2}
              dot={false}
              name="Completaciones"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
