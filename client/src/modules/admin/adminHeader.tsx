"use client";

import React from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useSession, signOut } from "@/lib/auth-client";
import { usePathname, useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { LogOut, ChevronDown, User, ChevronRight } from "lucide-react";

export function AdminHeader() {
  const { data: session, isPending } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  const handleSignOut = async () => {
    try {
      await signOut({
        fetchOptions: {
          onSuccess: () => {
            router.push("/");
            router.refresh();
          },
        },
      });
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  const getBreadcrumbTitle = (path: string) => {
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 0 || (segments.length === 1 && segments[0] === "home")) {
      return "Home";
    }
    const lastSegment = segments[segments.length - 1];
    return lastSegment.charAt(0).toUpperCase() + lastSegment.slice(1);
  };

  const currentPageTitle = getBreadcrumbTitle(pathname);

  const userInitial = session?.user?.name
    ? session.user.name.charAt(0).toUpperCase()
    : "A";

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-background px-6 select-none">
      {/* Left side: Sidebar trigger & Dynamic Breadcrumbs */}
      <div className="flex items-center gap-4">
        <SidebarTrigger className="-ml-1" />
        <div className="h-4 w-px bg-border" />
        <nav className="flex items-center gap-1.5 text-sm font-medium">
          <span className="text-muted-foreground font-medium">Admin Portal</span>
          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/60 shrink-0" />
          <span className="text-[#2E3A2F] font-semibold">
            {currentPageTitle}
          </span>
        </nav>
      </div>

      {/* Right side: User Profile & Dropdown Logout */}
      <div className="flex items-center gap-3">
        {isPending ? (
          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end gap-1">
              <Skeleton className="h-3.5 w-24 rounded-full" />
              <Skeleton className="h-3 w-32 rounded-full" />
            </div>
            <Skeleton className="h-9 w-9 rounded-full" />
          </div>
        ) : session?.user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-3 p-1.5 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors outline-none cursor-pointer group"
              >
                <div className="hidden sm:flex flex-col items-end text-right">
                  <span className="text-xs font-semibold text-[#2E3A2F] dark:text-neutral-100 group-hover:text-[#5F7560] transition-colors">
                    {session.user.name || "Admin User"}
                  </span>
                  <span className="text-[11px] text-muted-foreground truncate max-w-[180px]">
                    {session.user.email}
                  </span>
                </div>
                <Avatar className="h-9 w-9 border border-border shadow-xs">
                  {session.user.image && (
                    <AvatarImage
                      src={session.user.image}
                      alt={session.user.name || "User Avatar"}
                    />
                  )}
                  <AvatarFallback className="bg-[#5F7560] text-white font-bold text-xs">
                    {userInitial}
                  </AvatarFallback>
                </Avatar>
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground group-hover:text-[#2E3A2F] transition-transform group-data-[state=open]:rotate-180" />
              </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              align="end"
              className="w-56 mt-1 p-2 rounded-xl shadow-lg border border-border bg-white dark:bg-neutral-900"
            >
              <DropdownMenuLabel className="font-normal p-2">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-semibold leading-none text-[#2E3A2F] dark:text-neutral-100">
                    {session.user.name}
                  </p>
                  <p className="text-xs leading-none text-muted-foreground truncate">
                    {session.user.email}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="my-1" />
              <DropdownMenuItem
                onClick={handleSignOut}
                className="cursor-pointer text-red-600 focus:text-red-700 focus:bg-red-50 dark:focus:bg-red-950/40 rounded-lg p-2 flex items-center gap-2 font-medium text-xs transition-colors"
              >
                <LogOut className="w-4 h-4 text-red-600" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-muted text-muted-foreground text-xs">
                <User className="w-4 h-4" />
              </AvatarFallback>
            </Avatar>
            <span className="text-xs text-muted-foreground font-medium">
              Guest
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
