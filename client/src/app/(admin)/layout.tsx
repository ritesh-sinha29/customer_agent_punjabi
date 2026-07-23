import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AdminSidebar } from "@/modules/admin/adminSidebar";
import { AdminHeader } from "@/modules/admin/adminHeader";

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
          <AdminHeader />

          {/* Main scrollable content area */}
          <main className="flex-1 p-6">{children}</main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
