import React from "react";
import { AlertCircle, CheckCircle2, Calendar, Clock } from "lucide-react";

const stats = [
  {
    title: "Unresolved Queries",
    value: "0",
    description: "Requires attention",
    icon: AlertCircle,
    color: "text-amber-600 bg-amber-50 border-amber-200",
  },
  {
    title: "Resolved Queries",
    value: "0",
    description: "Successfully handled",
    icon: CheckCircle2,
    color: "text-emerald-600 bg-emerald-50 border-emerald-200",
  },
  {
    title: "Total Bookings (Today)",
    value: "0",
    description: "Scheduled consultations",
    icon: Calendar,
    color: "text-blue-600 bg-blue-50 border-blue-200",
  },
  {
    title: "Bookings in Last 1 Hour",
    value: "0",
    description: "Recent activity",
    icon: Clock,
    color: "text-[#2E3A2F] bg-[#5F7560]/10 border-[#5F7560]/20",
  },
];

export default function AdminPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-[#2E3A2F]">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Welcome back to the VRSA AGROTECH admin panel. Here is your overview for today.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.title}
            className="relative overflow-hidden rounded-xl border border-border bg-card p-6 shadow-xs transition-all hover:shadow-md"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">{stat.title}</span>
              <div className={`rounded-lg p-2 ${stat.color.split(" ")[1]} ${stat.color.split(" ")[0]} border`}>
                <stat.icon className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4">
              <span className="text-3xl font-bold tracking-tight text-foreground">{stat.value}</span>
              <p className="text-xs text-muted-foreground mt-1">{stat.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

