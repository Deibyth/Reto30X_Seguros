export interface PipelineSummary {
  total_sessions: number;
  active_sessions: number;
  completed_sessions: number;
  total_applications: number;
  applications_by_status: Record<string, number>;
  conversion_rate: number;
  abandon_at_section: Array<{ section: string; count: number }>;
}

export interface DailyTrend {
  date: string;
  applications: number;
  completions: number;
}

export interface CustomerProfile {
  salary_distribution: Array<{ range: string; count: number }>;
  contract_types: Array<{ type: string; count: number }>;
  avg_tenure_months: number;
  avg_credit_score: number;
  total_customers: number;
}

export interface CreditStats {
  avg_amount: number;
  avg_term_months: number;
  destino_distribution: Array<{ destino: string; count: number }>;
  amount_ranges: Array<{ range: string; count: number }>;
  total_credits: number;
  total_volume: number;
}

export interface AIEfficiency {
  avg_messages_per_completed_session: number;
  total_conversations: number;
  avg_fields_collected: number;
  top_omitted_fields: Array<{ field: string; count: number }>;
  sessions_with_tool_errors: number;
}

export interface DashboardSummary {
  pipeline: PipelineSummary;
  trends: DailyTrend[];
  customers: CustomerProfile;
  credits: CreditStats;
  efficiency: AIEfficiency;
}

export async function fetchSummary(): Promise<DashboardSummary> {
  const res = await fetch("/api/analytics/summary");
  if (!res.ok) throw new Error("Failed to fetch analytics summary");
  return res.json();
}

export async function fetchPipeline(): Promise<PipelineSummary> {
  const res = await fetch("/api/analytics/pipeline");
  if (!res.ok) throw new Error("Failed to fetch pipeline");
  return res.json();
}

export async function fetchTrends(days: number = 30): Promise<DailyTrend[]> {
  const res = await fetch(`/api/analytics/trends?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch trends");
  return res.json();
}

export async function fetchCustomers(): Promise<CustomerProfile> {
  const res = await fetch("/api/analytics/customers");
  if (!res.ok) throw new Error("Failed to fetch customers");
  return res.json();
}

export async function fetchCredits(): Promise<CreditStats> {
  const res = await fetch("/api/analytics/credits");
  if (!res.ok) throw new Error("Failed to fetch credits");
  return res.json();
}

export interface InsuranceStats {
  total_policies: number;
  active_policies: number;
  by_type: Array<{ tipo: string; count: number; premiums: number }>;
  by_status: Array<{ estado: string; count: number }>;
  total_premiums: number;
  claims_stats: {
    total: number;
    approved: number;
    total_amount: number;
  };
}

export async function fetchInsurance(): Promise<InsuranceStats> {
  const res = await fetch("/api/analytics/insurance");
  if (!res.ok) throw new Error("Failed to fetch insurance stats");
  return res.json();
}

export async function fetchEfficiency(): Promise<AIEfficiency> {
  const res = await fetch("/api/analytics/efficiency");
  if (!res.ok) throw new Error("Failed to fetch efficiency");
  return res.json();
}

export interface SupervisionMessage {
  rol: "user" | "assistant";
  mensaje: string;
  created_at: string;
}

export interface SupervisionSession {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  estado_actual: string;
  product_context: string | null;
  ultima_intencion: string;
  created_at: string;
  updated_at: string;
  conversations: SupervisionMessage[];
  total_messages: number;
  has_policy: boolean;
}

export async function fetchSupervision(token: string): Promise<SupervisionSession[]> {
  const res = await fetch("/api/analytics/supervision", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch supervision data");
  return res.json();
}
