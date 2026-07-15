import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AdminSidebar } from "@/modules/admin/adminSidebar";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full ">
        <AdminSidebar />
        <SidebarInset className="flex flex-col flex-1">
          {/* Header area with trigger */}
          <header className="flex h-16 items-center gap-4 border-b border-border bg-background px-6">
            <SidebarTrigger className="-ml-1" />
            <div className="h-4 w-px bg-border" />
            <span className="text-sm font-medium text-muted-foreground">
              Admin Portal
            </span>
          </header>

          {/* Main scrollable content area */}
          <main className="flex-1 p-6">{children}</main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
