import { useState } from "react";
import { LoginScreen } from "@/components/auth/LoginScreen";
import { PipelinePanel } from "./PipelinePanel";
import { TrendsPanel } from "./TrendsPanel";
import { CustomerPanel } from "./CustomerPanel";
import { EfficiencyPanel } from "./EfficiencyPanel";
import { InsurancePanel } from "./InsurancePanel";
import { SupervisionPanel } from "./SupervisionPanel";

type Tab = "pipeline" | "trends" | "customers" | "insurance" | "ai" | "supervision";

const TABS: { id: Tab; label: string }[] = [
  { id: "pipeline", label: "Pipeline" },
  { id: "trends", label: "Tendencias" },
  { id: "customers", label: "Clientes" },
  { id: "insurance", label: "Seguros" },
  { id: "ai", label: "AI" },
  { id: "supervision", label: "Supervisión" },
];

interface DashboardLayoutProps {
  token: string | null;
  onLogin: (token: string, name: string) => void;
}

export function DashboardLayout({ token, onLogin }: DashboardLayoutProps) {
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

  // If not authenticated, show login
  if (!token) {
    return (
      <main className="container mx-auto px-4 py-8">
        <LoginScreen onLogin={onLogin} />
      </main>
    );
  }

  return (
    <main className="container mx-auto px-4 py-8">
      {/* Tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-colsubsidio-blue text-white shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active panel */}
      <div className="animate-fade-in">
        {activeTab === "pipeline" && <PipelinePanel />}
        {activeTab === "trends" && <TrendsPanel />}
        {activeTab === "customers" && <CustomerPanel />}
        {activeTab === "insurance" && <InsurancePanel />}
        {activeTab === "ai" && <EfficiencyPanel />}
        {activeTab === "supervision" && <SupervisionPanel token={token} />}
      </div>
    </main>
  );
}
