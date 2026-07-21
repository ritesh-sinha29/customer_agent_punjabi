"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, FileText, MessageSquare, Calendar, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const navigationItems = [
  {
    title: "Home",
    url: "/home",
    icon: Home,
  },
  {
    title: "documents",
    url: "/home/documents",
    icon: FileText,
  },
  {
    title: "Quiries",
    url: "/home/quiries",
    icon: MessageSquare,
  },
  {
    title: "Bookings",
    url: "/home/bookings",
    icon: Calendar,
  },
  {
    title: "Evaluation",
    url: "/home/evaluation",
    icon: Activity,
  },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar className="border-r border-border">
      <SidebarHeader className="flex h-16 items-center px-6 border-b border-border">
        <Link href="/home" className="flex items-center gap-2 font-semibold">
          <span className="text-lg tracking-wider font-extrabold text-[#2E3A2F]">
            VRSA AGROTECH
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent className="px-3 py-4">
        <SidebarMenu>
          {navigationItems.map((item) => {
            const isActive = pathname === item.url;
            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive
                      ? "bg-[#5F7560]/10 text-[#2E3A2F] font-semibold"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Link href={item.url} className="flex items-center gap-3 w-full">
                    <item.icon className="h-4.5 w-4.5" />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter className="p-6 border-t border-border flex flex-col gap-2">
        <div className="text-xs text-muted-foreground font-medium uppercase tracking-wider leading-relaxed">
          fueling punjab , nourishing livestock.
        </div>
        <div className="font-gurmukhi text-sm text-[#2E3A2F] font-semibold leading-relaxed">
          ਪੰਜਾਬ ਨੂੰ ਊਰਜਾ, ਪਸ਼ੂਧਨ ਨੂੰ ਪੋਸ਼ਣ।
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
