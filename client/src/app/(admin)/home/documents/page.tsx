"use client";

import {
  AlertTriangle,
  CheckCircle,
  FileText,
  Loader2,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import Image from "next/image";
// UI Components from local library
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";

// Interface definitions
interface CompletedDoc {
  doc_id: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  tenant?: string;
  wasabi_file_key?: string;
}

interface ActiveIngestion {
  job_id: string;
  file_name: string;
  file_size: number;
  current_step: number;
  step_message: string;
  status: "processing" | "completed" | "failed";
  startTime?: number;
  elapsedTime?: number;
  history?: string[];
}

// Backend URL environment variable with fallback
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const fetchDocuments = async (): Promise<CompletedDoc[]> => {
  const response = await fetch("/api/documents", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load documents");
  }
  const data = await response.json();
  if (data.success && data.documents) {
    return data.documents;
  }
  return [];
};

export default function DocumentsPage() {
  const queryClient = useQueryClient();

  // TanStack Query for fetching completed documents
  const { data: completedDocs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: fetchDocuments,
  });

  const [activeIngestions, setActiveIngestions] = useState<
    Record<string, ActiveIngestion>
  >({});
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  // Track open SSE connections to prevent leaks
  const sseConnections = useRef<Record<string, EventSource>>({});

  // Recover active ingestions from SessionStorage on mount
  useEffect(() => {
    const recoveredActive = sessionStorage.getItem("punjabi_active_ingestions");
    if (recoveredActive) {
      try {
        const parsed = JSON.parse(recoveredActive) as Record<
          string,
          ActiveIngestion
        >;
        setActiveIngestions(parsed);
        // Re-establish SSE for each active ingestion
        Object.keys(parsed).forEach((jobId) => {
          connectSSE(jobId);
        });
      } catch (err) {
        console.error("Failed to recover active ingestions", err);
      }
    }

    // Cleanup SSE connections on unmount
    return () => {
      Object.values(sseConnections.current).forEach((conn) => conn.close());
    };
  }, []);

  // Real-time timer and local timeout effect for active ingestions
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveIngestions((prev) => {
        let changed = false;
        const updated = { ...prev };

        Object.keys(updated).forEach((jobId) => {
          const job = updated[jobId];
          if (job.status === "processing") {
            const start = job.startTime || Date.now();
            const elapsed = Math.floor((Date.now() - start) / 1000);

            if (elapsed >= 180) {
              // 3 minutes local timeout
              updated[jobId] = {
                ...job,
                status: "failed",
                step_message: "Process timed out after 3 minutes.",
                elapsedTime: elapsed,
                history: job.history?.includes(
                  "Process timed out after 3 minutes.",
                )
                  ? job.history || []
                  : [
                      ...(job.history || []),
                      "Process timed out after 3 minutes.",
                    ],
              };
              // Close SSE connection
              if (sseConnections.current[jobId]) {
                sseConnections.current[jobId].close();
                delete sseConnections.current[jobId];
              }
            } else {
              updated[jobId] = {
                ...job,
                startTime: start,
                elapsedTime: elapsed,
              };
            }
            changed = true;
          }
        });

        if (changed) {
          sessionStorage.setItem(
            "punjabi_active_ingestions",
            JSON.stringify(updated),
          );
          return updated;
        }
        return prev;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Formats date cleanly: e.g. "Jul 19, 2026"
  const formatDate = (dateString: string) => {
    if (!dateString) return "-";
    try {
      const d = new Date(dateString);
      if (isNaN(d.getTime())) return dateString;
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateString;
    }
  };

  // Map file types to public SVG icons
  const getFileIcon = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return "/pdf.svg";
    if (["doc", "docx"].includes(ext || "")) return "/doc.svg";
    if (["xls", "xlsx", "csv"].includes(ext || "")) return "/xls.svg";
    if (["ppt", "pptx"].includes(ext || "")) return "/ppt.svg";
    return "/file.svg";
  };

  // Formats file sizes
  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / k ** i).toFixed(2)) + " " + sizes[i];
  };

  // Truncates long filenames
  const truncateFileName = (name: string, maxLen: number = 28) => {
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

  // File selection validation (Max 25MB)
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const maxSizeBytes = 25 * 1024 * 1024; // 25 MB

    if (file.size > maxSizeBytes) {
      toast.error("File limit exceeded", {
        description: `Selected file is ${formatFileSize(file.size)}. Max size allowed is 25MB.`,
      });
      e.target.value = ""; // reset
      return;
    }

    setSelectedFile(file);
    toast.success("File added", {
      description: `${file.name} is ready for upload.`,
    });
  };

  // Connect to SSE status stream on Python server
  const connectSSE = (jobId: string) => {
    if (sseConnections.current[jobId]) {
      sseConnections.current[jobId].close();
    }

    const eventSource = new EventSource(
      `${BACKEND_URL}/api/v1/ingest/status/${jobId}/stream`,
    );
    sseConnections.current[jobId] = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { status, current_step, step_message, file_name } = data;

        setActiveIngestions((prev) => {
          const updated = { ...prev };
          const newMsg = step_message || "Ingesting...";

          if (updated[jobId]) {
            const currentHistory = updated[jobId].history || [];
            const updatedHistory = currentHistory.includes(newMsg)
              ? currentHistory
              : [...currentHistory, newMsg];

            updated[jobId] = {
              ...updated[jobId],
              current_step: current_step || 0,
              step_message: newMsg,
              status: status || "processing",
              history: updatedHistory,
            };
          } else {
            updated[jobId] = {
              job_id: jobId,
              file_name: file_name || "Document",
              file_size: 0,
              current_step: current_step || 0,
              step_message: newMsg,
              status: status || "processing",
              startTime: Date.now(),
              elapsedTime: 0,
              history: [newMsg],
            };
          }

          sessionStorage.setItem(
            "punjabi_active_ingestions",
            JSON.stringify(updated),
          );
          return updated;
        });

        if (status === "completed") {
          toast.success("Ingestion successful!", {
            description: `${file_name || "Document"} has been parsed, embedded, and stored in Pinecone.`,
          });

          eventSource.close();
          delete sseConnections.current[jobId];

          queryClient.invalidateQueries({ queryKey: ["documents"] });

          setActiveIngestions((prev) => {
            const updated = { ...prev };
            delete updated[jobId];
            sessionStorage.setItem(
              "punjabi_active_ingestions",
              JSON.stringify(updated),
            );
            return updated;
          });
        }

        if (status === "failed") {
          toast.error("Ingestion failed", {
            description: `${file_name || "Document"} processing failed: ${step_message}`,
          });
          eventSource.close();
          delete sseConnections.current[jobId];

          setActiveIngestions((prev) => {
            const updated = { ...prev };
            if (updated[jobId]) {
              updated[jobId].status = "failed";
              updated[jobId].step_message = `Failed: ${step_message}`;
            }
            sessionStorage.setItem(
              "punjabi_active_ingestions",
              JSON.stringify(updated),
            );
            return updated;
          });
        }
      } catch (err) {
        console.error("Failed to parse SSE payload", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE connection error", err);
      eventSource.close();
      delete sseConnections.current[jobId];

      setActiveIngestions((prev) => {
        const updated = { ...prev };
        if (updated[jobId] && updated[jobId].status === "processing") {
          updated[jobId].status = "failed";
          updated[jobId].step_message =
            "Disconnected from Server SSE connection.";
        }
        return updated;
      });
    };
  };

  // Upload to Wasabi and invoke Python Ingestion API
  const handleConfirmUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const uploadSim = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(uploadSim);
            return 90;
          }
          return prev + 15;
        });
      }, 150);

      const uploadResponse = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      clearInterval(uploadSim);

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => ({}));
        const errorMsg =
          errorData.error || `HTTP error ${uploadResponse.status}`;
        throw new Error(errorMsg);
      }

      const uploadResult = await uploadResponse.json();
      setUploadProgress(100);

      const actualFileUrl = uploadResult.data.url;
      const actualFileKey = uploadResult.data.key;
      const actualFileId = uploadResult.data.id;
      const actualFileName = uploadResult.data.name;
      const actualFileSize = uploadResult.data.size;

      setIsDialogOpen(false);
      setSelectedFile(null);
      setIsUploading(false);
      setUploadProgress(0);

      // Refetch documents from database so all docs remain visible
      queryClient.invalidateQueries({ queryKey: ["documents"] });

      // Trigger ingestion API endpoint
      const response = await fetch(`${BACKEND_URL}/api/v1/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          file_url: actualFileUrl,
          file_key: actualFileKey,
          userId: "admin-client-user",
          tenant: "default",
          permissions: ["read:demo"],
          version: "1.0.0",
          job_id: actualFileId,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson?.detail || "Ingestion trigger failed.");
      }

      const resData = await response.json();
      const jobId = resData.data.job_id;

      const now = Date.now();
      setActiveIngestions((prev) => {
        const updated = {
          ...prev,
          [jobId]: {
            job_id: jobId,
            file_name: actualFileName,
            file_size: actualFileSize,
            current_step: 0,
            step_message: "Job submitted to Temporal queue...",
            status: "processing",
            startTime: now,
            elapsedTime: 0,
            history: ["Job submitted to Temporal queue..."],
          },
        };
        sessionStorage.setItem(
          "punjabi_active_ingestions",
          JSON.stringify(updated),
        );
        return updated;
      });

      connectSSE(jobId);
    } catch (err: any) {
      toast.error("Upload failed", {
        description: err.message || "Failed to trigger document ingestion.",
      });
      setIsUploading(false);
    }
  };

  // TanStack Query Mutation for deleting documents
  const deleteMutation = useMutation({
    mutationFn: async ({
      docId,
      fileName,
    }: {
      docId: string;
      fileName: string;
    }) => {
      const doc = completedDocs.find((d) => d.doc_id === docId);
      const fileKey = doc?.wasabi_file_key;

      // 1. Delete from PostgreSQL Database
      const dbResponse = await fetch("/api/documents", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId }),
      });
      if (!dbResponse.ok) {
        throw new Error("Failed to delete document metadata from database.");
      }

      // 2. Delete from Wasabi S3
      if (fileKey) {
        await fetch("/api/delete", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: fileKey }),
        });
      }

      // 3. Delete from Pinecone
      const response = await fetch(
        `${BACKEND_URL}/api/v1/ingest/${docId}?tenant=default`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to delete document vectors from Pinecone.");
      }
    },
    onSuccess: (_, { docId, fileName }) => {
      queryClient.setQueryData<CompletedDoc[]>(["documents"], (old = []) =>
        old.filter((d) => d.doc_id !== docId),
      );
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document deleted", {
        description: `${fileName} removed from database, Wasabi, and Pinecone.`,
      });
    },
    onError: (err: any) => {
      toast.error("Delete failed", {
        description: err.message || "Could not complete document deletion.",
      });
    },
  });

  const removeFailedIngestion = (jobId: string) => {
    setActiveIngestions((prev) => {
      const updated = { ...prev };
      delete updated[jobId];
      sessionStorage.setItem(
        "punjabi_active_ingestions",
        JSON.stringify(updated),
      );
      return updated;
    });
  };

  return (
    <div className="space-y-6 bg-white">
      {/* Top Banner / Ingestion Portal Header */}
      <div className="w-[95%] mx-auto p-4 rounded-xl shadow-sm border bg-linear-to-br from-amber-800 to-yellow-50 relative h-[185px] mt-3">
        <div className="flex items-center justify-between h-full">
          <div className="text-content flex flex-col justify-center h-full w-[55%] text-left text-white">
            <h1 className="text-2xl font-semibold">Ingestion Portal</h1>
            <p className="text-sm tracking-tight mt-2.5 text-white">
              Upload and process layout-aware documents/ Files / products
              catalog for Agent to serve customers.
            </p>
            <div className="mt-auto">
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="rounded-md text-xs text-black bg-white hover:bg-white/90 border-none shadow-xs flex items-center gap-2">
                    <UploadCloud className="h-4 w-4" /> Upload new doc
                  </Button>
                </DialogTrigger>

                <DialogContent className="max-w-md bg-white border border-border rounded-lg p-6 shadow-xl">
                  <DialogHeader>
                    <DialogTitle className="text-lg font-bold text-foreground">
                      Upload Ingestion Document
                    </DialogTitle>
                  </DialogHeader>

                  <div className="space-y-4 py-4">
                    <div className="border-2 border-dashed border-muted-foreground/30 hover:border-[#5F7560] rounded-lg p-8 text-center cursor-pointer transition relative">
                      <input
                        type="file"
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        onChange={handleFileChange}
                        disabled={isUploading}
                      />
                      <UploadCloud className="h-10 w-10 text-[#5F7560] mx-auto mb-2" />
                      <p className="text-sm font-semibold text-foreground">
                        Click or drag file here to upload
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Supported: PDF, Docx, TXT, Excel, PPTX (Max 25MB)
                      </p>
                    </div>

                    {selectedFile && (
                      <div className="bg-muted/10 border border-border rounded-lg p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <img
                            src={getFileIcon(selectedFile.name)}
                            alt="Icon"
                            className="h-8 w-8 object-contain"
                          />
                          <div className="text-left">
                            <p className="text-sm font-bold text-foreground truncate max-w-[200px]">
                              {selectedFile.name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatFileSize(selectedFile.size)}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedFile(null)}
                          disabled={isUploading}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    )}

                    {isUploading && (
                      <div className="space-y-2">
                        <Progress
                          value={uploadProgress}
                          className="h-1.5 bg-muted"
                        />
                        <p className="text-xs text-center text-muted-foreground">
                          Uploading to storage: {uploadProgress}%
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end gap-3 mt-4 border-t pt-4">
                    <DialogClose asChild>
                      <Button variant="outline" disabled={isUploading}>
                        Cancel
                      </Button>
                    </DialogClose>
                    <Button
                      onClick={handleConfirmUpload}
                      disabled={!selectedFile || isUploading}
                      className="bg-[#5F7560] hover:bg-[#4E614F] text-white"
                    >
                      {isUploading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />{" "}
                          Uploading...
                        </>
                      ) : (
                        "Confirm Upload"
                      )}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <div className="3d-image">
            <Image
              alt="Ingestion Portal Hero"
              className="absolute bottom-0 right-8"
              height={210}
              src="/5.svg"
              width={210}
            />
          </div>
        </div>
      </div>

      {/* Grid of active processes and completed docs */}
      <div className="grid grid-cols-1 gap-6">
        {/* Real-time Processing Jobs Section */}
        {Object.keys(activeIngestions).length > 0 && (
          <div className="bg-[#5F7560]/5 border border-[#5F7560]/20 rounded-xl p-6 space-y-4">
            <h2 className="text-md font-bold text-[#2E3A2F] flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-[#5F7560]" />{" "}
              Processing Documents ({Object.keys(activeIngestions).length})
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.values(activeIngestions).map((job) => (
                <div
                  key={job.job_id}
                  className="bg-white border border-border rounded-lg p-4 shadow-sm flex flex-col justify-between space-y-3 relative overflow-hidden"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex items-center gap-3">
                      <img
                        src={getFileIcon(job.file_name)}
                        alt="icon"
                        className="h-8 w-8 object-contain"
                      />
                      <div className="text-left">
                        <p className="text-sm font-bold text-foreground truncate max-w-[220px]">
                          {truncateFileName(job.file_name)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Size: {formatFileSize(job.file_size)}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1.5">
                      {job.status === "failed" ? (
                        <Badge
                          variant="destructive"
                          className="flex items-center gap-1"
                        >
                          <AlertTriangle className="h-3 w-3" /> Failed
                        </Badge>
                      ) : (
                        <Badge className="bg-[#5F7560]/10 text-[#2E3A2F] border-none flex items-center gap-1 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          <span> {job.elapsedTime || 0}s</span>
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2 bg-muted/5 p-3 rounded-lg border text-xs">
                    <div className="flex justify-between text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                      <span>Progress</span>
                      <span>Step {job.current_step}/6</span>
                    </div>
                    <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${job.status === "failed" ? "bg-destructive" : "bg-[#5F7560]"}`}
                        style={{ width: `${(job.current_step / 6) * 100}%` }}
                      />
                    </div>

                    <div className="mt-2 space-y-1 max-h-[85px] overflow-y-auto pt-1.5 border-t border-dashed border-border scrollbar-thin">
                      {(job.history || [job.step_message]).map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex items-start gap-1.5 leading-relaxed ${idx === (job.history?.length || 1) - 1 ? "text-foreground font-medium" : "text-muted-foreground/60"}`}
                        >
                          <span className="text-[9px] text-muted-foreground/40 mt-0.5">
                            [{idx + 1}]
                          </span>
                          <span className="break-all">{msg}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {job.status === "failed" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeFailedIngestion(job.job_id)}
                      className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completed Uploaded Docs Section */}
        <div className="space-y-4">
          <h2 className="text-md font-bold text-foreground flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-[#5F7560]" /> Uploaded
            Documents ({completedDocs.length})
          </h2>

          {isLoading ? (
            <div className="overflow-hidden border border-border rounded-lg">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-muted/50 border-b border-border text-xs font-bold text-muted-foreground">
                    <th className="p-4 w-8">Format</th>
                    <th className="p-4">Name</th>
                    <th className="p-4">Size</th>
                    <th className="p-4">Ingestion</th>
                    <th className="p-4">Uploaded At</th>
                    <th className="p-4 w-12 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {[1, 2, 3, 4, 5].map((i) => (
                    <tr key={i} className="border-b border-border">
                      <td className="p-4">
                        <Skeleton className="h-6 w-6 rounded-md" />
                      </td>
                      <td className="p-4">
                        <Skeleton className="h-4 w-48" />
                      </td>
                      <td className="p-4">
                        <Skeleton className="h-4 w-16" />
                      </td>
                      <td className="p-4">
                        <Skeleton className="h-6 w-20 rounded-full" />
                      </td>
                      <td className="p-4">
                        <Skeleton className="h-4 w-24" />
                      </td>
                      <td className="p-4 text-center">
                        <Skeleton className="h-8 w-8 rounded-md mx-auto" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : completedDocs.length === 0 ? (
            <div className="border border-dashed rounded-lg p-12 text-center text-muted-foreground">
              <FileText className="h-12 w-12 text-muted-foreground/45 mx-auto mb-2" />
              <p className="text-sm font-semibold">No documents uploaded yet</p>
              <p className="text-xs">
                Select and process new documents using the top-right button.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden border border-border rounded-lg">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-muted/50 border-b border-border text-xs font-bold text-muted-foreground">
                    <th className="p-4 w-8">Format</th>
                    <th className="p-4">Name</th>
                    <th className="p-4">Size</th>
                    <th className="p-4">Ingestion</th>
                    <th className="p-4">Uploaded At</th>
                    <th className="p-4 w-12 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {completedDocs.map((doc) => (
                    <tr
                      key={doc.doc_id}
                      className="border-b border-border hover:bg-muted/10 text-sm transition-colors"
                    >
                      <td className="p-4">
                        <img
                          src={getFileIcon(doc.file_name)}
                          alt="ext-icon"
                          className="h-8 w-8 object-contain"
                        />
                      </td>
                      <td className="p-4 font-semibold text-foreground">
                        {truncateFileName(doc.file_name, 35)}
                      </td>
                      <td className="p-4 text-muted-foreground">
                        {doc.file_size
                          ? formatFileSize(doc.file_size)
                          : "2.4 MB (approx)"}
                      </td>
                      <td className="p-4">
                        <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200/60 font-medium shadow-none hover:bg-emerald-50 flex items-center gap-1.5 w-fit">
                          <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
                          Success
                        </Badge>
                      </td>
                      <td className="p-4 text-xs text-muted-foreground font-medium">
                        {formatDate(doc.uploaded_at)}
                      </td>
                      <td className="p-4 text-center">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            deleteMutation.mutate({
                              docId: doc.doc_id,
                              fileName: doc.file_name,
                            })
                          }
                          disabled={deleteMutation.isPending}
                          className="text-destructive hover:bg-destructive/10"
                        >
                          {deleteMutation.isPending &&
                          deleteMutation.variables?.docId === doc.doc_id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
