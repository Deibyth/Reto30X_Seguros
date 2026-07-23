import { useState } from "react";
import { Layout } from "@/components/layout/Layout";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";

type View = "chat" | "dashboard";

function App() {
  const [view, setView] = useState<View>("chat");

  return (
    <Layout onNavigate={setView} currentView={view}>
      {view === "chat" ? (
        <main className="container mx-auto px-4 py-8">
          <ChatPanel />
        </main>
      ) : (
        <DashboardLayout />
      )}
    </Layout>
  );
}

export default App;
