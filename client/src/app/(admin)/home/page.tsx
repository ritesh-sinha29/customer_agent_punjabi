"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  HelpCircle,
  Users,
  ShoppingBag,
  Clock,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import Link from "next/link";

interface DocumentItem {
  doc_id: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  url: string;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
}

function MetricCard({
  title,
  value,
  icon,
  iconBg,
  iconColor,
}: MetricCardProps) {
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
      <div
        className={`p-2 rounded-sm border bg-white flex items-center justify-center -mb-3`}
      >
        <span className="">{icon}</span>
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTopDocuments = async () => {
      try {
        const response = await fetch("/api/documents");
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.documents) {
            // Display only top 4 documents
            setDocuments(data.documents.slice(0, 4));
          }
        }
      } catch (err) {
        console.error("Failed to load documents", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTopDocuments();
  }, []);

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
    return parseFloat((bytes / k ** i).toFixed(2)) + " " + sizes[i];
  };

  const truncateFileName = (name: string, maxLen = 30) => {
    if (name.length <= maxLen) return name;
    const parts = name.split(".");
    const ext = parts.pop();
    const rest = parts.join(".");
    return (
      rest.slice(0, maxLen - (ext?.length || 0) - 4) +
      "..." +
      (ext ? `.${ext}` : "")
    );
  };

  return (
    <div className="space-y-6 bg-white select-none">
      {/* Top Banner */}
      <div className="w-[95%] mx-auto p-4 mt-4 rounded-xl shadow-sm border bg-linear-to-br from-[#0A4729]/70 to-emerald-50 relative h-[185px]">
        <div className="flex items-center justify-between h-full">
          <div className="text-content flex flex-col justify-center h-full w-[55%] text-left text-white">
            <h1 className="text-2xl font-semibold">Welcome user</h1>
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
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
        />
        <MetricCard
          title="Total Customers"
          value="1,248"
          icon={<Users className="h-5 w-5" />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
        />
        <MetricCard
          title="Orders Today"
          value={86}
          icon={<ShoppingBag className="h-5 w-5" />}
          iconBg="bg-blue-50"
          iconColor="text-blue-600"
        />
        <MetricCard
          title="Orders Last 1hr"
          value={7}
          icon={<Clock className="h-5 w-5" />}
          iconBg="bg-indigo-50"
          iconColor="text-indigo-600"
        />
      </div>

      {/* Uploaded Files Section */}
      <div className=" mt-6 text-left">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-lg font-bold text-[#2E3A2F]">Uploaded Files</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Upload company Policies / Products for Agents
            </p>
          </div>
          <Link href="/home/documents" passHref legacyBehavior>
            <Button variant="default" size="sm" className="text-xs rounded-md">
              View All <ArrowRight className="h-3 w-3" />
            </Button>
          </Link>
        </div>

        {loading ? (
          <div className="py-4 text-center text-sm text-muted-foreground animate-pulse">
            Loading recent uploads...
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.doc_id}
                className="flex items-center gap-4 p-4 border border-border rounded-xl hover:border-[#5F7560]/40 hover:bg-[#5F7560]/5 transition-all cursor-pointer"
              >
                <img
                  src={getFileIcon(doc.file_name)}
                  alt="file-type-icon"
                  className="h-10 w-10 object-contain flex-shrink-0"
                />
                <div className="flex-1 min-w-0 text-left">
                  <p
                    className="text-sm font-bold text-[#2E3A2F] truncate"
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
          </div>
        )}
      </div>
    </div>
  );
}
