import { useState } from "react";
import { PipelinePanel } from "./PipelinePanel";
import { TrendsPanel } from "./TrendsPanel";
import { CustomerPanel } from "./CustomerPanel";
import { EfficiencyPanel } from "./EfficiencyPanel";
import { InsurancePanel } from "./InsurancePanel";

type Tab = "pipeline" | "trends" | "customers" | "insurance" | "ai";

const TABS: { id: Tab; label: string }[] = [
  { id: "pipeline", label: "Pipeline" },
  { id: "trends", label: "Tendencias" },
  { id: "customers", label: "Clientes" },
  { id: "insurance", label: "Seguros" },
  { id: "ai", label: "AI" },
];

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

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
      </div>
    </main>
  );
}
