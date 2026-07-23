"use client";

import React, { useState } from "react";
import {
  Clock,
  CheckCircle2,
  Search,
  ArrowLeft,
  ChevronDown,
  Check,
  MessageSquareText,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Image from "next/image";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

interface QueryItem {
  id: string;
  title: string;
  description: string;
  status: string;
  createdAt: string;
  customerName: string | null;
  customerEmail: string | null;
  customerImage?: string | null;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
}

function MetricCard({ title, value, icon }: MetricCardProps) {
  return (
    <div className="bg-neutral-50 border border-border p-5 rounded-lg shadow-xs flex items-center justify-between hover:shadow-sm hover:border-[#5F7560]/30 transition-all text-left">
      <div className="space-y-1">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {title}
        </p>
        <p className="text-2xl font-bold text-[#2E3A2F] tracking-tight">
          {value}
        </p>
      </div>
      <div className="p-2 rounded-sm border bg-white flex items-center justify-center -mb-3">
        <span>{icon}</span>
      </div>
    </div>
  );
}

const QUERY_STATUSES = [
  { id: "pending", label: "Pending", styles: "bg-amber-50 text-amber-700 border-amber-200/60" },
  { id: "in-review", label: "In-Review", styles: "bg-blue-50 text-blue-700 border-blue-200/60" },
  { id: "completed", label: "Completed", styles: "bg-emerald-50 text-emerald-700 border-emerald-200/60" },
];

const fetchQuiries = async (): Promise<QueryItem[]> => {
  const response = await fetch("/api/quiries");
  if (!response.ok) {
    throw new Error("Failed to load quiries");
  }
  const data = await response.json();
  if (data.success && data.quiries) {
    return data.quiries;
  }
  return [];
};

export default function QuiriesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const queryClient = useQueryClient();

  const { data: quiries = [], isLoading } = useQuery({
    queryKey: ["quiries"],
    queryFn: fetchQuiries,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Mutation to update query status in DB
  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      const res = await fetch("/api/quiries", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, status }),
      });
      if (!res.ok) throw new Error("Failed to update status");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiries"] });
    },
  });

  const handleStatusChange = (queryId: string, newStatus: string, statusLabel: string) => {
    toast.promise(
      updateStatusMutation.mutateAsync({ id: queryId, status: newStatus }),
      {
        loading: `Updating inquiry status to "${statusLabel}"...`,
        success: `Inquiry status changed to "${statusLabel}"`,
        error: "Failed to update inquiry status",
      }
    );
  };

  const formatDate = (dateString: string) => {
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateString;
    }
  };

  const getStatusObj = (status: string) => {
    const s = status.toLowerCase();
    return (
      QUERY_STATUSES.find((item) => item.id === s) || {
        id: s,
        label: status.charAt(0).toUpperCase() + status.slice(1),
        styles: "bg-amber-50 text-amber-700 border-amber-200/60",
      }
    );
  };

  // Metrics
  const totalQuiries = quiries.length;
  const pendingCount = quiries.filter((q) => q.status.toLowerCase() === "pending").length;
  const inReviewCount = quiries.filter((q) => q.status.toLowerCase() === "in-review").length;
  const completedCount = quiries.filter((q) => q.status.toLowerCase() === "completed").length;

  // Filtering
  const filteredQuiries = quiries.filter((q) => {
    const matchesSearch =
      (q.customerName?.toLowerCase() || "").includes(searchQuery.toLowerCase()) ||
      (q.customerEmail?.toLowerCase() || "").includes(searchQuery.toLowerCase()) ||
      q.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      q.description.toLowerCase().includes(searchQuery.toLowerCase());

    if (selectedStatus === "all") return matchesSearch;
    return matchesSearch && q.status.toLowerCase() === selectedStatus.toLowerCase();
  });

  return (
    <div className="space-y-6 bg-white select-none">
      {/* Top Hero Banner */}
      <div className="w-[95%] mx-auto p-4 mt-4 rounded-xl shadow-sm border bg-linear-to-br from-[#0A4729]/70 to-emerald-50 relative h-[170px]">
        <div className="flex items-center justify-between h-full">
          <div className="text-content flex flex-col justify-center h-full w-[55%] text-left text-white">
            <h1 className="text-2xl font-semibold">Customer Quiries</h1>
            <p className="text-sm tracking-tight mt-2.5">
              Review farmer questions, address AI escalations, and resolve customer
              inquiries across VRSA AGROTECH services.
            </p>
            <div className="mt-auto">
              <Link href="/home" passHref legacyBehavior>
                <Button
                  className="rounded-md text-xs text-black bg-white hover:bg-white/90 border-none shadow-xs flex items-center gap-1.5"
                  variant="outline"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Back to Dashboard
                </Button>
              </Link>
            </div>
          </div>

          <div className="3d-image">
            <Image
              alt="Hero"
              className="absolute bottom-0 right-8"
              height={230}
              src="/4.svg"
              width={230}
            />
          </div>
        </div>
      </div>

      {/* 4 Summary Metric Cards */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 mt-6">
        <MetricCard
          title="Total Quiries"
          value={totalQuiries}
          icon={<MessageSquareText className="h-5 w-5 text-blue-600" />}
        />
        <MetricCard
          title="Pending Response"
          value={pendingCount}
          icon={<Clock className="h-5 w-5 text-amber-600" />}
        />
        <MetricCard
          title="In-Review"
          value={inReviewCount}
          icon={<Eye className="h-5 w-5 text-purple-600" />}
        />
        <MetricCard
          title="Completed / Solved"
          value={completedCount}
          icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
        />
      </div>

      {/* Quiries Table Section */}
      <div className="mt-8 text-left space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2">
          <div>
            <h2 className="text-lg font-bold text-[#2E3A2F]">All Customer Quiries</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Click any status button below to update inquiry resolution in real time
            </p>
          </div>

          {/* Search & Status Filter Tabs */}
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-56">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search title, customer..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-border bg-neutral-50/50 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-[#5F7560] transition-all"
              />
            </div>

            <div className="flex items-center gap-1 bg-neutral-100 p-1 rounded-lg border border-border">
              <button
                type="button"
                onClick={() => setSelectedStatus("all")}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all cursor-pointer ${
                  selectedStatus === "all"
                    ? "bg-white text-[#2E3A2F] shadow-xs"
                    : "text-muted-foreground hover:text-[#2E3A2F]"
                }`}
              >
                All
              </button>
              {QUERY_STATUSES.map((st) => (
                <button
                  key={st.id}
                  type="button"
                  onClick={() => setSelectedStatus(st.id)}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all cursor-pointer capitalize ${
                    selectedStatus === st.id
                      ? "bg-white text-[#2E3A2F] shadow-xs"
                      : "text-muted-foreground hover:text-[#2E3A2F]"
                  }`}
                >
                  {st.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table Content */}
        {isLoading ? (
          <div className="border border-border rounded-xl p-4 bg-white space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <Skeleton className="h-4 w-32 rounded-full bg-neutral-200" />
              <Skeleton className="h-4 w-24 rounded-full bg-neutral-200" />
              <Skeleton className="h-4 w-16 rounded-full bg-neutral-200" />
              <Skeleton className="h-4 w-20 rounded-full bg-neutral-200" />
            </div>
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-border/40 last:border-0"
              >
                <div className="flex items-center gap-3 w-1/3">
                  <Skeleton className="h-8 w-8 rounded-full shrink-0 bg-neutral-200" />
                  <div className="space-y-1 flex-1">
                    <Skeleton className="h-3.5 w-28 rounded-full bg-neutral-200" />
                    <Skeleton className="h-2.5 w-36 rounded-full bg-neutral-200" />
                  </div>
                </div>
                <Skeleton className="h-3.5 w-40 rounded-full bg-neutral-200" />
                <Skeleton className="h-6 w-24 rounded-full bg-neutral-200" />
                <Skeleton className="h-3.5 w-20 rounded-full bg-neutral-200" />
              </div>
            ))}
          </div>
        ) : filteredQuiries.length === 0 ? (
          <div className="py-12 border border-dashed border-muted-foreground/20 rounded-xl text-center flex flex-col items-center justify-center bg-neutral-50/30">
            <MessageSquareText className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm font-semibold text-[#2E3A2F]">
              No customer quiries found
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Try adjusting your search criteria or filter selection.
            </p>
          </div>
        ) : (
          <div className="border border-border rounded-xl overflow-hidden shadow-xs bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-neutral-50/70 border-b border-border">
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-4">
                      Customer Name
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Inquiry Title & Description
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Status Action
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider pr-4">
                      Date Created
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {filteredQuiries.map((q) => {
                    const statusObj = getStatusObj(q.status);
                    return (
                      <tr
                        key={q.id}
                        className="hover:bg-neutral-50/40 transition-colors"
                      >
                        <td className="p-3 pl-4">
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8 shrink-0 border border-border">
                              {q.customerImage && (
                                <AvatarImage
                                  src={q.customerImage}
                                  alt={q.customerName || "Customer"}
                                />
                              )}
                              <AvatarFallback className="bg-[#5F7560]/10 text-[#2E3A2F] font-semibold text-xs border border-[#5F7560]/20">
                                {q.customerName
                                  ? q.customerName.charAt(0).toUpperCase()
                                  : "?"}
                              </AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-[#2E3A2F] truncate">
                                {q.customerName || "Guest User"}
                              </p>
                              {q.customerEmail && (
                                <p className="text-xs text-muted-foreground truncate">
                                  {q.customerEmail}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        <td className="p-3 max-w-xs">
                          <p className="text-sm font-semibold text-[#2E3A2F] truncate">
                            {q.title}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {q.description}
                          </p>
                        </td>

                        {/* Interactive Status Dropdown Button with Toast Promise */}
                        <td className="p-3">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border cursor-pointer hover:opacity-90 transition-all outline-none ${statusObj.styles}`}
                              >
                                <span>{statusObj.label}</span>
                                <ChevronDown className="h-3 w-3 opacity-70" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" className="w-36 p-1.5 bg-white rounded-xl shadow-lg border border-border">
                              {QUERY_STATUSES.map((st) => (
                                <DropdownMenuItem
                                  key={st.id}
                                  onClick={() => handleStatusChange(q.id, st.id, st.label)}
                                  className="flex items-center justify-between text-xs py-1.5 px-2 rounded-lg cursor-pointer hover:bg-neutral-100 font-medium"
                                >
                                  <span className={`px-2 py-0.5 rounded-full text-[11px] border ${st.styles}`}>
                                    {st.label}
                                  </span>
                                  {q.status.toLowerCase() === st.id && (
                                    <Check className="h-3.5 w-3.5 text-[#2E3A2F]" />
                                  )}
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>

                        <td className="p-3 text-sm text-muted-foreground pr-4">
                          {formatDate(q.createdAt)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
