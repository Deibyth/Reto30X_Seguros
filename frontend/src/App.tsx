import { useState } from "react";
import { Layout } from "@/components/layout/Layout";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";

type View = "chat" | "dashboard";

function App() {
  const [view, setView] = useState<View>("chat");
  const [token, setToken] = useState<string | null>(null);
  const [userName, setUserName] = useState<string>("");

  const handleLogin = (newToken: string, name: string) => {
    setToken(newToken);
    setUserName(name);
  };

  const handleLogout = () => {
    setToken(null);
    setUserName("");
    setView("chat");
  };

  return (
    <Layout
      onNavigate={setView}
      currentView={view}
      token={token}
      userName={userName}
      onLogout={handleLogout}
    >
      {view === "chat" ? (
        <main className="container mx-auto px-4 py-8">
          <ChatPanel />
        </main>
      ) : (
        <DashboardLayout token={token} onLogin={handleLogin} />
      )}
    </Layout>
  );
}

export default App;
