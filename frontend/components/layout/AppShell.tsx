import * as React from "react";
import { Sidebar } from "./Sidebar";
import { Navbar } from "./Navbar";
import { AuthGate } from "./AuthGate";
import { ChatSessionProvider } from "@/hooks/useChatSession";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <ChatSessionProvider>
        <div className="flex h-screen w-full bg-[var(--color-background)] overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col overflow-hidden">
            <Navbar />
            <main className="flex-1 overflow-auto">
              {children}
            </main>
          </div>
        </div>
      </ChatSessionProvider>
    </AuthGate>
  );
}
