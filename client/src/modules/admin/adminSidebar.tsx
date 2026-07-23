"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  FileText,
  MessageSquare,
  Calendar,
  Activity,
} from "lucide-react";
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
import Image from "next/image";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useSession } from "@/lib/auth-client";

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
  const { data: session } = useSession();
  const userId = session?.user?.id || "guest_user";

  return (
    <Sidebar className="border-r border-border">
      <SidebarHeader className="px-4 py-3 border-b border-zinc-300 flex flex-col gap-2">
        <div className="flex items-center gap-2 ">
          <Image
            src="/vrsa_logo.svg"
            width={40}
            height={40}
            alt="VRSA AGROTECH AI"
          />
          <span className="font-bold text-xl tracking-wide">VRSA AGRO</span>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-3 py-4">
        <SidebarMenu>
          {navigationItems.map((item) => {
            const isActive = pathname === item.url;
            return (
              <SidebarMenuItem key={item.title} className="">
                <SidebarMenuButton
                  asChild
                  isActive={isActive}
                  className={cn(
                    "w-full flex items-center mb-2! gap-3 px-3 py-2 rounded-sm! transition-colors",
                    isActive
                      ? "bg-emerald-900/25!  text-black font-semibold"
                      : "text-neutral-800 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Link
                    href={item.url}
                    className="flex items-center gap-3 capitalize w-full"
                  >
                    <item.icon className="h-4.5 w-4.5" />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter className="">
        {/* BOXX */}
        <div className="flex flex-col border rounded-sm p-4 bg-linear-to-br from-white to-emerald-700/40 relative">
          <div className="text-xs capitalize ">
            fueling punjab , nourishing livestock.
          </div>
          <div className="font-gurmukhi text-sm ">
            ਪੰਜਾਬ ਨੂੰ ਊਰਜਾ, ਪਸ਼ੂਧਨ ਨੂੰ ਪੋਸ਼ਣ।
          </div>
          <Image
            src="/crop.svg"
            width={50}
            height={50}
            alt="VRSA AGROTECH AI"
            className="absolute right-1 bottom-0"
          />
        </div>
        <div className="flex items-center gap-2 pt-3 border-t justify-center w-full">
          <div className="w-6 h-6 rounded-full bg-[#2E3A2F]/10 flex items-center justify-center text-[#2E3A2F] font-bold text-xs ml-5">
            <Avatar>
              <AvatarImage
                src={session?.user?.image!}
                alt={session?.user?.name || "Guest Farmer"}
              />
              <AvatarFallback>
                {session?.user?.name ? session.user.name[0].toUpperCase() : "G"}
              </AvatarFallback>
            </Avatar>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-zinc-700 truncate">
              {session?.user?.name || "Guest Farmer"}
            </p>
            <p className="text-[10px] text-zinc-600 truncate">
              {session?.user?.email || "Offline Companion"}
            </p>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
