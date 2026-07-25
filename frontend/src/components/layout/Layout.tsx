import type { ReactNode } from "react";
import { Header } from "./Header";

interface LayoutProps {
  children: ReactNode;
  onNavigate?: (view: "chat" | "dashboard") => void;
  currentView?: "chat" | "dashboard";
  token?: string | null;
  userName?: string;
  onLogout?: () => void;
}

export function Layout({ children, onNavigate, currentView, token, userName, onLogout }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header
        onNavigate={onNavigate}
        currentView={currentView}
        token={token}
        userName={userName}
        onLogout={onLogout}
      />
      {children}
    </div>
  );
}
