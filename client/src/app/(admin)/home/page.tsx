"use client";

import React from "react";
import {
  HelpCircle,
  Users,
  ShoppingBag,
  Clock,
  ArrowRight,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import Image from "next/image";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "@/lib/auth-client";

interface DocumentItem {
  doc_id: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  url: string;
}

interface BookingItem {
  id: string;
  productName: string;
  qty: number;
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

// Fetcher functions for TanStack Query
const fetchDocuments = async (): Promise<DocumentItem[]> => {
  const response = await fetch("/api/documents");
  if (!response.ok) {
    throw new Error("Failed to load documents");
  }
  const data = await response.json();
  if (data.success && data.documents) {
    return data.documents.slice(0, 3);
  }
  return [];
};

const fetchBookings = async (): Promise<BookingItem[]> => {
  const response = await fetch("/api/bookings");
  if (!response.ok) {
    throw new Error("Failed to load bookings");
  }
  const data = await response.json();
  if (data.success && data.bookings) {
    return data.bookings;
  }
  return [];
};

export default function AdminPage() {
  const { data: session } = useSession();

  // TanStack Query caching for documents with 5 minutes staleTime
  const {
    data: documents = [],
    isLoading: docsLoading,
  } = useQuery({
    queryKey: ["documents"],
    queryFn: fetchDocuments,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // TanStack Query caching for bookings with 5 minutes staleTime
  const {
    data: bookings = [],
    isLoading: bookingsLoading,
  } = useQuery({
    queryKey: ["bookings"],
    queryFn: fetchBookings,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Only display top 8 bookings on home page dashboard
  const displayBookings = bookings.slice(0, 8);

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

  const getStatusStyles = (status: string) => {
    const s = status.toLowerCase();
    if (s === "delivered" || s === "completed") {
      return "bg-emerald-50 text-emerald-700 border-emerald-200/50";
    }
    if (s === "out-for-delivery") {
      return "bg-indigo-50 text-indigo-700 border-indigo-200/50";
    }
    if (s === "in-transist" || s === "in-transit") {
      return "bg-purple-50 text-purple-700 border-purple-200/50";
    }
    if (s === "accepted" || s === "approved" || s === "confirmed") {
      return "bg-blue-50 text-blue-700 border-blue-200/50";
    }
    if (s === "cancelled" || s === "rejected") {
      return "bg-red-50 text-red-700 border-red-200/50";
    }
    return "bg-amber-50 text-amber-700 border-amber-200/50";
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return "/pdf.svg";
    if (["doc", "docx"].includes(ext || "")) return "/doc.svg";
    if (["xls", "xlsx", "csv"].includes(ext || "")) return "/xls.svg";
    if (["ppt", "pptx"].includes(ext || "")) return "/ppt.svg";
    return "/file.svg";
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
  };

  const truncateFileName = (name: string, maxLen = 30) => {
    if (name.length <= maxLen) return name;
    const parts = name.split(".");
    const ext = parts.pop();
    const rest = parts.join(".");
    return `${rest.slice(0, maxLen - (ext?.length || 0) - 4)}...${ext ? `.${ext}` : ""}`;
  };

  const userName = session?.user?.name
    ? session.user.name.split(" ")[0]
    : "User";

  return (
    <div className="space-y-6 bg-white select-none">
      {/* Top Banner */}
      <div className="w-[95%] mx-auto p-4 mt-4 rounded-xl shadow-sm border bg-linear-to-br from-[#0A4729]/70 to-emerald-50 relative h-[185px]">
        <div className="flex items-center justify-between h-full">
          <div className="text-content flex flex-col justify-center h-full w-[55%] text-left text-white">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold">Welcome {userName}</h1>
            </div>
            <p className="text-sm tracking-tight mt-2.5">
              Manage VRSA AGROTECH live operations, review ingested resources,
              respond to customer inquiries, and track real-time delivery logs.
            </p>
            <div className="mt-auto">
              <Link href="/home/bookings" passHref legacyBehavior>
                <Button
                  className="rounded-md text-xs text-black bg-white hover:bg-white/90 border-none shadow-xs"
                  variant="outline"
                >
                  View Bookings
                </Button>
              </Link>
            </div>
          </div>

          <div className="3d-image">
            <Image
              alt="Hero"
              className="absolute bottom-0 right-8"
              height={180}
              src="/3.svg"
              width={180}
            />
          </div>
        </div>
      </div>

      {/* 4 Summary Metric Boxes */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 mt-6">
        <MetricCard
          title="Unresolved Quiries"
          value={14}
          icon={<HelpCircle className="h-5 w-5" />}
        />
        <MetricCard
          title="Total Customers"
          value="1,248"
          icon={<Users className="h-5 w-5" />}
        />
        <MetricCard
          title="Orders Today"
          value={86}
          icon={<ShoppingBag className="h-5 w-5" />}
        />
        <MetricCard
          title="Orders Last 1hr"
          value={7}
          icon={<Clock className="h-5 w-5" />}
        />
      </div>

      {/* Uploaded Files Section */}
      <div className="mt-6 text-left">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-lg font-bold text-[#2E3A2F]">Uploaded Files</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Upload company Policies / Products for Agents
            </p>
          </div>
          <Link href="/home/documents" passHref legacyBehavior>
            <Button variant="default" size="sm" className="text-xs rounded-md">
              View All <ArrowRight className="h-3 w-3" />
            </Button>
          </Link>
        </div>

        {docsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-2.5 border border-border rounded-md bg-neutral-50 h-[62px]"
              >
                <Skeleton className="h-10 w-10 rounded-md shrink-0 bg-neutral-200" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-3/4 rounded-full bg-neutral-200" />
                  <Skeleton className="h-3 w-1/2 rounded-full bg-neutral-200" />
                </div>
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="py-4 border-2 border-dashed border-muted/30 rounded-xl text-center flex flex-col items-center justify-center">
            <Image
              src="/file.svg"
              alt="No files"
              width={48}
              height={48}
              className="opacity-70 mb-3"
            />
            <Link href="/home/documents" passHref legacyBehavior>
              <Button
                size="sm"
                className="bg-[#5F7560] hover:bg-[#4E614F] text-white mt-1 rounded-md"
              >
                Go to Documents Portal
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.doc_id}
                className="flex items-center gap-4 p-2.5 border border-border rounded-md bg-neutral-50 cursor-pointer hover:border-[#5F7560]/30 hover:shadow-xs transition-all"
              >
                <img
                  src={getFileIcon(doc.file_name)}
                  alt="file-type-icon"
                  className="h-10 w-10 object-contain shrink-0"
                />
                <div className="flex-1 min-w-0 text-left">
                  <p
                    className="text-xs font-semibold text-[#2E3A2F] truncate"
                    title={doc.file_name}
                  >
                    {truncateFileName(doc.file_name, 35)}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatFileSize(doc.file_size)}
                  </p>
                </div>
              </div>
            ))}

            {/* Upload More Card */}
            <Link href="/home/documents" passHref legacyBehavior>
              <div className="flex items-center gap-3 p-2.5 border border-dashed border-muted-foreground rounded-md cursor-pointer h-[62px] bg-white hover:bg-neutral-100 group">
                <div className="h-9 w-9 rounded-full border border-dashed border-muted-foreground flex items-center justify-center">
                  <Plus className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <p className="text-xs font-semibold">Upload More</p>
                  <p className="text-xs text-muted-foreground">Add new files</p>
                </div>
              </div>
            </Link>
          </div>
        )}
      </div>

      {/* Bookings Section */}
      <div className="mt-8 text-left">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-lg font-bold text-[#2E3A2F]">
              Recent Bookings
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Review and manage the latest farmer service bookings
            </p>
          </div>
          <Link href="/home/bookings" passHref legacyBehavior>
            <Button variant="default" size="sm" className="text-xs rounded-md">
              View All <ArrowRight className="h-3 w-3" />
            </Button>
          </Link>
        </div>

        {bookingsLoading ? (
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
                className="flex items-center justify-between py-2 border-b border-border/40 last:border-0"
              >
                <div className="flex items-center gap-3 w-1/3">
                  <Skeleton className="h-8 w-8 rounded-full shrink-0 bg-neutral-200" />
                  <div className="space-y-1 flex-1">
                    <Skeleton className="h-3.5 w-28 rounded-full bg-neutral-200" />
                    <Skeleton className="h-2.5 w-36 rounded-full bg-neutral-200" />
                  </div>
                </div>
                <Skeleton className="h-3.5 w-24 rounded-full bg-neutral-200" />
                <Skeleton className="h-3.5 w-8 rounded-full bg-neutral-200" />
                <Skeleton className="h-5 w-20 rounded-full bg-neutral-200" />
                <Skeleton className="h-3.5 w-20 rounded-full bg-neutral-200" />
              </div>
            ))}
          </div>
        ) : displayBookings.length === 0 ? (
          <div className="py-8 border border-dashed border-muted-foreground/20 rounded-xl text-center flex flex-col items-center justify-center bg-neutral-50/30">
            <ShoppingBag className="h-8 w-8 text-muted-foreground/50 mb-2" />
            <p className="text-sm font-medium text-muted-foreground">
              No recent bookings found
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
                      Product
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider text-center">
                      Qty
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Status
                    </th>
                    <th className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider pr-4">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {displayBookings.map((booking) => (
                    <tr
                      key={booking.id}
                      className="hover:bg-neutral-50/40 transition-colors"
                    >
                      <td className="p-3 pl-4">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8 shrink-0 border border-border">
                            {booking.customerImage && (
                              <AvatarImage
                                src={booking.customerImage}
                                alt={booking.customerName || "Customer"}
                              />
                            )}
                            <AvatarFallback className="bg-[#5F7560]/10 text-[#2E3A2F] font-semibold text-xs border border-[#5F7560]/20">
                              {booking.customerName
                                ? booking.customerName.charAt(0).toUpperCase()
                                : "?"}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[#2E3A2F] truncate">
                              {booking.customerName || "Guest User"}
                            </p>
                            {booking.customerEmail && (
                              <p className="text-xs text-muted-foreground truncate">
                                {booking.customerEmail}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="p-3 text-sm font-medium text-[#2E3A2F]">
                        {booking.productName}
                      </td>
                      <td className="p-3 text-sm text-center font-semibold text-[#2E3A2F]">
                        {booking.qty}
                      </td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusStyles(
                            booking.status,
                          )}`}
                        >
                          {booking.status.charAt(0).toUpperCase() +
                            booking.status.slice(1)}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-muted-foreground pr-4">
                        {formatDate(booking.createdAt)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
