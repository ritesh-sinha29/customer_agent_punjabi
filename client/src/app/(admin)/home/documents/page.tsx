"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  FileText, 
  UploadCloud, 
  Trash2, 
  Loader2, 
  X, 
  CheckCircle, 
  AlertTriangle 
} from "lucide-react";
import { toast } from "sonner";

// UI Components from local library
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogClose
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

// Interface definitions
interface CompletedDoc {
  doc_id: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  tenant: string;
}

interface ActiveIngestion {
  job_id: string;
  file_name: string;
  file_size: number;
  current_step: number;
  step_message: string;
  status: "processing" | "completed" | "failed";
}

const BACKEND_URL = "http://localhost:8000";

export default function DocumentsPage() {
  const [completedDocs, setCompletedDocs] = useState<CompletedDoc[]>([]);
  const [activeIngestions, setActiveIngestions] = useState<Record<string, ActiveIngestion>>({});
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  // Track open SSE connections to prevent leaks
  const sseConnections = useRef<Record<string, EventSource>>({});

  // 1. Load completed documents from LocalStorage on mount
  useEffect(() => {
    const cached = localStorage.getItem("punjabi_agent_documents");
    if (cached) {
      try {
        setCompletedDocs(JSON.parse(cached));
      } catch (err) {
        console.error("Failed to parse cached documents", err);
      }
    }

    // Recover active ingestions from SessionStorage if user refreshed page
    const recoveredActive = sessionStorage.getItem("punjabi_active_ingestions");
    if (recoveredActive) {
      try {
        const parsed = JSON.parse(recoveredActive) as Record<string, ActiveIngestion>;
        setActiveIngestions(parsed);
        // Re-establish SSE for each active ingestion
        Object.keys(parsed).forEach(jobId => {
          connectSSE(jobId);
        });
      } catch (err) {
        console.error("Failed to recover active ingestions", err);
      }
    }

    // Cleanup SSE connections on unmount
    return () => {
      Object.values(sseConnections.current).forEach(conn => conn.close());
    };
  }, []);

  // Sync state to local storage when completed docs changes
  const saveDocsToCache = (docs: CompletedDoc[]) => {
    localStorage.setItem("punjabi_agent_documents", JSON.stringify(docs));
    setCompletedDocs(docs);
  };

  // Sync active ingestions to session storage
  const saveActiveIngestions = (ingestions: Record<string, ActiveIngestion>) => {
    sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(ingestions));
    setActiveIngestions(ingestions);
  };

  // 2. Map file types to public SVG icons
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
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // Truncates long filenames
  const truncateFileName = (name: string, maxLen: number = 28) => {
    if (name.length <= maxLen) return name;
    const parts = name.split(".");
    const ext = parts.pop();
    const rest = parts.join(".");
    return rest.slice(0, maxLen - (ext?.length || 0) - 4) + "..." + (ext ? `.${ext}` : "");
  };

  // 3. File selection validation (Max 25MB)
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    const file = files[0];
    const maxSizeBytes = 25 * 1024 * 1024; // 25 MB

    if (file.size > maxSizeBytes) {
      toast.error("File limit exceeded", {
        description: `Selected file is ${formatFileSize(file.size)}. Max size allowed is 25MB.`
      });
      e.target.value = ""; // reset
      return;
    }

    setSelectedFile(file);
    toast.success("File added", { description: `${file.name} is ready for upload.` });
  };

  // 4. Connect to SSE status stream on Python server
  const connectSSE = (jobId: string) => {
    // Avoid double listeners
    if (sseConnections.current[jobId]) {
      sseConnections.current[jobId].close();
    }

    const eventSource = new EventSource(`${BACKEND_URL}/api/v1/ingest/status/${jobId}/stream`);
    sseConnections.current[jobId] = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { status, current_step, step_message, file_name } = data;

        // Update active ingestion step progress
        setActiveIngestions(prev => {
          const updated = { ...prev };
          if (updated[jobId]) {
            updated[jobId] = {
              ...updated[jobId],
              current_step: current_step || 0,
              step_message: step_message || "Ingesting...",
              status: status || "processing"
            };
          } else {
            // Fallback initialization if recovered
            updated[jobId] = {
              job_id: jobId,
              file_name: file_name || "Document",
              file_size: 0,
              current_step: current_step || 0,
              step_message: step_message || "Ingesting...",
              status: status || "processing"
            };
          }

          // Persist the state
          sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(updated));
          return updated;
        });

        // If completed, move to completed lists
        if (status === "completed") {
          toast.success("Ingestion successful!", {
            description: `${file_name || "Document"} has been parsed, embedded, and stored in Pinecone.`
          });
          
          eventSource.close();
          delete sseConnections.current[jobId];

          // Append to completed documents list
          setCompletedDocs(prev => {
            const newDoc: CompletedDoc = {
              doc_id: jobId,
              file_name: file_name || "Document",
              file_size: 0, // Could be populated from local state
              uploaded_at: new Date().toLocaleString(),
              tenant: "demo-tenant-punjabi"
            };
            const updatedDocs = [newDoc, ...prev];
            localStorage.setItem("punjabi_agent_documents", JSON.stringify(updatedDocs));
            return updatedDocs;
          });

          // Remove from active list
          setActiveIngestions(prev => {
            const updated = { ...prev };
            delete updated[jobId];
            sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(updated));
            return updated;
          });
        }

        // If failed
        if (status === "failed") {
          toast.error("Ingestion failed", {
            description: `${file_name || "Document"} processing failed: ${step_message}`
          });
          eventSource.close();
          delete sseConnections.current[jobId];

          // Remove from active list after 5s or keep it as error card
          setActiveIngestions(prev => {
            const updated = { ...prev };
            if (updated[jobId]) {
              updated[jobId].status = "failed";
              updated[jobId].step_message = `Failed: ${step_message}`;
            }
            sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(updated));
            return updated;
          });
        }

      } catch (err) {
        console.error("Failed to parse SSE payload", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE connection error", err);
      // Close the connection
      eventSource.close();
      delete sseConnections.current[jobId];

      setActiveIngestions(prev => {
        const updated = { ...prev };
        if (updated[jobId] && updated[jobId].status === "processing") {
          updated[jobId].status = "failed";
          updated[jobId].step_message = "Disconnected from Server SSE connection.";
        }
        return updated;
      });
    };
  };

  // 5. Simulate S3 upload and invoke Python Ingestion API
  const handleConfirmUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(10);

    try {
      // Simulate AWS/Wasabi S3 upload progress
      const uploadSim = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(uploadSim);
            return 90;
          }
          return prev + 20;
        });
      }, 150);

      // We will pretend the file was uploaded to Wasabi and get a download link
      await new Promise(resolve => setTimeout(resolve, 800));
      clearInterval(uploadSim);
      setUploadProgress(100);

      const mockFileUrl = `${BACKEND_URL}/tests/${selectedFile.name}`;
      const mockFileKey = selectedFile.name;

      // Close Dialog
      setIsDialogOpen(false);
      
      // Reset upload states
      setSelectedFile(null);
      setIsUploading(false);
      setUploadProgress(0);

      // Trigger ingestion API endpoint
      const response = await fetch(`${BACKEND_URL}/api/v1/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          file_url: mockFileUrl,
          file_key: mockFileKey,
          userId: "admin-client-user",
          tenant: "demo-tenant-punjabi",
          permissions: ["read:demo"],
          version: "1.0.0"
        })
      });

      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson?.detail || "Ingestion trigger failed.");
      }

      const resData = await response.json();
      const jobId = resData.data.job_id;

      // Add to active ingestions lists
      setActiveIngestions(prev => {
        const updated = {
          ...prev,
          [jobId]: {
            job_id: jobId,
            file_name: mockFileKey,
            file_size: selectedFile.size,
            current_step: 0,
            step_message: "Job submitted to Temporal queue...",
            status: "processing"
          }
        };
        sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(updated));
        return updated;
      });

      // Start SSE listener
      connectSSE(jobId);

    } catch (err: any) {
      toast.error("Upload failed", {
        description: err.message || "Failed to trigger document ingestion."
      });
      setIsUploading(false);
    }
  };

  // 6. Delete completed document from Pinecone and UI lists
  const handleDeleteCompleted = async (docId: string, fileName: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/ingest/${docId}?tenant=demo-tenant-punjabi`, {
        method: "DELETE"
      });

      if (!response.ok) {
        throw new Error("Failed to delete document from Pinecone.");
      }

      // Filter local state
      const updated = completedDocs.filter(d => d.doc_id !== docId);
      saveDocsToCache(updated);

      toast.success("Document deleted", {
        description: `${fileName} vectors removed from Pinecone.`
      });
    } catch (err: any) {
      toast.error("Delete failed", {
        description: err.message || "Could not complete document deletion."
      });
    }
  };

  const removeFailedIngestion = (jobId: string) => {
    setActiveIngestions(prev => {
      const updated = { ...prev };
      delete updated[jobId];
      sessionStorage.setItem("punjabi_active_ingestions", JSON.stringify(updated));
      return updated;
    });
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Title Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 border border-border rounded-xl shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <FileText className="h-6 w-6 text-[#5F7560]" /> Ingestion Portal
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload and process layout-aware documents into the vector store.
          </p>
        </div>
        
        {/* Upload dialog Trigger */}
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#5F7560] hover:bg-[#4E614F] text-white flex items-center gap-2">
              <UploadCloud className="h-4 w-4" /> Upload new doc
            </Button>
          </DialogTrigger>
          
          <DialogContent className="max-w-md bg-white border border-border rounded-lg p-6 shadow-xl">
            <DialogHeader>
              <DialogTitle className="text-lg font-bold text-foreground">Upload Ingestion Document</DialogTitle>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* Drag and drop card */}
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

              {/* Selected File Details */}
              {selectedFile && (
                <div className="bg-muted/10 border border-border rounded-lg p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <img 
                      src={getFileIcon(selectedFile.name)} 
                      alt="Icon" 
                      className="h-8 w-8 object-contain"
                    />
                    <div className="text-left">
                      <p className="text-sm font-bold text-foreground truncate max-w-[200px]">{selectedFile.name}</p>
                      <p className="text-xs text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
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

              {/* Progress Bar */}
              {isUploading && (
                <div className="space-y-2">
                  <Progress value={uploadProgress} className="h-1.5 bg-muted" />
                  <p className="text-xs text-center text-muted-foreground">Uploading to storage: {uploadProgress}%</p>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 mt-4 border-t pt-4">
              <DialogClose asChild>
                <Button variant="outline" disabled={isUploading}>Cancel</Button>
              </DialogClose>
              <Button 
                onClick={handleConfirmUpload} 
                disabled={!selectedFile || isUploading}
                className="bg-[#5F7560] hover:bg-[#4E614F] text-white"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" /> Uploading...
                  </>
                ) : "Confirm Upload"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Grid of active processes and completed docs */}
      <div className="grid grid-cols-1 gap-6">
        
        {/* Real-time Processing Jobs Section */}
        {Object.keys(activeIngestions).length > 0 && (
          <div className="bg-[#5F7560]/5 border border-[#5F7560]/20 rounded-xl p-6 space-y-4">
            <h2 className="text-md font-bold text-[#2E3A2F] flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-[#5F7560]" /> Processing Documents ({Object.keys(activeIngestions).length})
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.values(activeIngestions).map((job) => (
                <div key={job.job_id} className="bg-white border border-border rounded-lg p-4 shadow-sm flex flex-col justify-between space-y-3 relative overflow-hidden">
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
                    
                    {/* Status Badge */}
                    {job.status === "failed" ? (
                      <Badge variant="destructive" className="flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> Failed
                      </Badge>
                    ) : (
                      <Badge className="bg-[#5F7560]/10 text-[#2E3A2F] border-none flex items-center gap-1 animate-pulse">
                        <Loader2 className="h-3 w-3 animate-spin" /> Ingesting
                      </Badge>
                    )}
                  </div>

                  {/* Progressive Step Message */}
                  <div className="space-y-1 bg-muted/5 p-2 rounded border">
                    <div className="flex justify-between text-xs font-bold text-foreground">
                      <span>Step {job.current_step}/6:</span>
                      <span className="text-[#5F7560] font-normal truncate max-w-[200px]">
                        {job.step_message}
                      </span>
                    </div>
                    {/* Linear loader representation */}
                    <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-300 ${job.status === 'failed' ? 'bg-destructive' : 'bg-[#5F7560]'}`}
                        style={{ width: `${(job.current_step / 6) * 100}%` }}
                      />
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
        <div className="bg-white border border-border rounded-xl p-6 space-y-4 shadow-sm">
          <h2 className="text-md font-bold text-foreground flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-[#5F7560]" /> Uploaded Documents ({completedDocs.length})
          </h2>

          {completedDocs.length === 0 ? (
            <div className="border border-dashed rounded-lg p-12 text-center text-muted-foreground">
              <FileText className="h-12 w-12 text-muted-foreground/45 mx-auto mb-2" />
              <p className="text-sm font-semibold">No documents uploaded yet</p>
              <p className="text-xs">Select and process new documents using the top-right button.</p>
            </div>
          ) : (
            <div className="overflow-hidden border border-border rounded-lg">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-muted/50 border-b border-border text-xs font-bold text-muted-foreground">
                    <th className="p-4 w-8">Format</th>
                    <th className="p-4">Name</th>
                    <th className="p-4">Size</th>
                    <th className="p-4">Uploaded At</th>
                    <th className="p-4 w-12 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {completedDocs.map((doc) => (
                    <tr key={doc.doc_id} className="border-b border-border hover:bg-muted/10 text-sm transition-colors">
                      <td className="p-4">
                        <img 
                          src={getFileIcon(doc.file_name)} 
                          alt="ext-icon" 
                          className="h-6 w-6 object-contain"
                        />
                      </td>
                      <td className="p-4 font-semibold text-foreground">
                        {truncateFileName(doc.file_name, 35)}
                      </td>
                      <td className="p-4 text-muted-foreground">
                        {doc.file_size ? formatFileSize(doc.file_size) : "2.4 MB (approx)"}
                      </td>
                      <td className="p-4 text-xs text-muted-foreground">
                        {doc.uploaded_at}
                      </td>
                      <td className="p-4 text-center">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => handleDeleteCompleted(doc.doc_id, doc.file_name)}
                          className="text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
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
