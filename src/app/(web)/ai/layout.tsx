"use client";

import * as React from "react";
import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AppSidebar } from "@/modules/ai/app-sidebar";

export default function AiLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-zinc-50 text-[#2E3A2F]">
        {/* AppSidebar component from modules/ai */}
        <AppSidebar className="border-r border-zinc-200 bg-white" />

        {/* SidebarInset on the right side */}
        <SidebarInset className="flex flex-col flex-1 min-h-screen bg-zinc-50">
          {/* Top header bar with SidebarTrigger */}
          <header className="flex h-16 shrink-0 items-center gap-2 border-b border-zinc-100 px-4 bg-white">
            <SidebarTrigger className="-ml-1" />
          </header>

          {/* Page content */}
          <main className="flex-1 flex flex-col">
            {children}
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
