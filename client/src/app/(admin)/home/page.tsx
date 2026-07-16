import React from "react";
import { AlertCircle, CheckCircle2, Calendar, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import Image from "next/image";

export default function AdminPage() {
  return (
    <div className="space-y-6 bg-white select-none">
      {/* Top Banner */}
      <div className="w-[95%] mx-auto p-4 mt-4 rounded-xl shadow-sm border bg-linear-to-br from-[#0A4729]/70 to-emerald-50 relative h-[185px]">
        <div className="flex items-center justify-between h-full">
          <div className="text-content flex flex-col justify-center h-full w-[55%] text-left text-white">
            <h1 className="text-2xl font-semibold">Welcome user</h1>
            <p className="text-sm tracking-tight mt-2.5">
              Lorem ipsum dolor, sit amet consectetur adipisicing elit. Quidem,
              quo! Lorem ipsum dolor, sit amet consectetur adipisicing elit.
              Vitae, vel.
            </p>
            <div className="mt-auto">
              <Button
                className="rounded-md text-xs text-black"
                variant="outline"
              >
                View Bookings
              </Button>
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
    </div>
  );
}
