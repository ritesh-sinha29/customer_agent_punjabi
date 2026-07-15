"use client";

import type * as React from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar {...props}>
      <SidebarHeader>
        {/* Sidebar header - empty structure for now */}
      </SidebarHeader>

      <SidebarContent>
        {/* Sidebar content - empty structure for now */}
      </SidebarContent>

      <SidebarFooter>
        {/* Sidebar footer - empty structure for now */}
      </SidebarFooter>
    </Sidebar>
  );
}
