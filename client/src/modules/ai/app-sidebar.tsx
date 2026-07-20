"use client";

import type * as React from "react";
import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useSession } from "@/lib/auth-client";
import { toast } from "sonner";
import { Plus, MessageSquare, Trash2, Loader2, Leaf } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface Thread {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

function AppSidebarInner({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { data: session } = useSession();
  const userId = session?.user?.id || "guest_user";
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeThreadId = searchParams.get("threadId");

  const [threads, setThreads] = useState<Thread[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchThreads = useCallback(async () => {
    try {
      setIsLoading(true);
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(
        `${backendUrl}/api/v1/agent/threads?user_id=${userId}`,
      );
      if (!res.ok) throw new Error("Failed to fetch threads");
      const data = await res.json();
      if (data.success) {
        setThreads(data.threads);
      }
    } catch (err) {
      console.error("Error fetching threads:", err);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchThreads();

    // Listen to custom event to automatically refresh threads list
    const handleUpdate = () => {
      fetchThreads();
    };

    window.addEventListener("threads-updated", handleUpdate);
    return () => {
      window.removeEventListener("threads-updated", handleUpdate);
    };
  }, [fetchThreads]);

  const handleNewChat = () => {
    const newId = `thread-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    router.push(`/ai?threadId=${newId}`);
  };

  const handleDeleteThread = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    e.preventDefault();
    if (deletingId) return;

    try {
      setDeletingId(threadId);
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(
        `${backendUrl}/api/v1/agent/threads/${threadId}`,
        {
          method: "DELETE",
        },
      );
      if (!res.ok) throw new Error("Failed to delete thread");

      toast.success("Conversation deleted successfully");

      // Update local state
      setThreads((prev) => prev.filter((t) => t.id !== threadId));

      // If deleted active thread, route to a new one
      if (activeThreadId === threadId) {
        const newId = `thread-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
        router.push(`/ai?threadId=${newId}`);
      }
    } catch (err) {
      console.error("Error deleting thread:", err);
      toast.error("Failed to delete conversation");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Sidebar {...props}>
      <SidebarHeader className="px-4 py-3 border-b border-zinc-100 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-[#2E3A2F]">
          <Leaf className="w-5 h-5 fill-emerald-600 text-emerald-600" />
          <span className="font-bold text-sm tracking-wide">
            VRSA AGROTECH AI
          </span>
        </div>
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-full border border-zinc-200/80 bg-zinc-50 hover:bg-zinc-100 text-[#2E3A2F] text-xs font-semibold shadow-xs transition-all active:scale-98 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </SidebarHeader>

      <SidebarContent className="px-2 py-2">
        <SidebarGroup>
          <SidebarGroupLabel className="text-zinc-400 text-[10px] font-semibold tracking-wider uppercase mb-1">
            Recent Chats
          </SidebarGroupLabel>
          <SidebarGroupContent>
            {isLoading && threads.length === 0 ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
              </div>
            ) : threads.length === 0 ? (
              <div className="text-center py-6 text-zinc-400 text-xs px-2">
                No recent conversations
              </div>
            ) : (
              <SidebarMenu>
                {threads.map((thread) => {
                  const isActive = activeThreadId === thread.id;
                  return (
                    <SidebarMenuItem
                      key={thread.id}
                      className="relative group/item mb-0.5"
                    >
                      <SidebarMenuButton
                        onClick={() => router.push(`/ai?threadId=${thread.id}`)}
                        className={cn(
                          "w-full flex items-center gap-2 px-3 py-2 rounded-xl text-left text-xs transition-colors hover:bg-zinc-100/60 cursor-pointer",
                          isActive
                            ? "bg-[#2E3A2F]/8 text-[#2E3A2F] font-semibold border-l-3 border-[#2E3A2F] rounded-l-none"
                            : "text-zinc-600",
                        )}
                      >
                        <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-80" />
                        <span className="truncate pr-4">{thread.title}</span>
                      </SidebarMenuButton>
                      <button
                        onClick={(e) => handleDeleteThread(e, thread.id)}
                        disabled={deletingId === thread.id}
                        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 text-zinc-400 hover:text-red-600 transition-opacity p-1 rounded-md hover:bg-red-50 cursor-pointer"
                      >
                        {deletingId === thread.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="">
        {/* BOXX */}
        <div className="flex flex-col border rounded-sm p-5 bg-linear-to-br from-white to-green-700/20">
          <div className="text-xs text-muted-foreground font-medium uppercase tracking-wider leading-relaxed">
            fueling punjab , nourishing livestock.
          </div>
          <div className="font-gurmukhi text-sm text-[#2E3A2F] font-semibold leading-relaxed">
            ਪੰਜਾਬ ਨੂੰ ਊਰਜਾ, ਪਸ਼ੂਧਨ ਨੂੰ ਪੋਸ਼ਣ।
          </div>
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

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Suspense fallback={<Sidebar {...props} />}>
      <AppSidebarInner {...props} />
    </Suspense>
  );
}
