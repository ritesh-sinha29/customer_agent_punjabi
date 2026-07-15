import React from "react";
import { MessageSquare } from "lucide-react";

export default function QuiriesPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white border border-border rounded-xl p-8 shadow-sm">
        <div className="flex items-center gap-4 mb-6">
          <div className="p-3 bg-[#5F7560]/10 text-[#2E3A2F] rounded-lg">
            <MessageSquare className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Quiries</h1>
            <p className="text-sm text-muted-foreground">Respond to customer inquiries and AI agent queries.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
