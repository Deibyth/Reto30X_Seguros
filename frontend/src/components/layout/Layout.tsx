import type { ReactNode } from "react";
import { Header } from "./Header";

interface LayoutProps {
  children: ReactNode;
  onNavigate?: (view: "chat" | "dashboard") => void;
  currentView?: "chat" | "dashboard";
}

export function Layout({ children, onNavigate, currentView }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header onNavigate={onNavigate} currentView={currentView} />
      {children}
    </div>
  );
}
