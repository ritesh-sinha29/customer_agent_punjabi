"use client";

import type * as React from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/modules/ai/app-sidebar";

export default function AiLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-white  select-none">
        {/* AppSidebar component from modules/ai */}
        <AppSidebar className="border-r border-zinc-200 bg-white" />

        {/* Full space container */}
        <div className="flex flex-col flex-1 min-h-screen relative overflow-hidden">
          <div
            className="absolute inset-0 -top-6 opacity-100 z-0 bg-cover bg-top bg-no-repeat pointer-events-none"
            style={{ backgroundImage: "url('/ai-bg-1.png')" }}
          />

          {/* Page content */}
          <main className="flex-1 flex flex-col relative z-10">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
