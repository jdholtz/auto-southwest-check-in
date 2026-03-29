import { Sidebar } from "@/components/layout/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 pt-14 px-4 pb-4 md:ml-64 md:pt-0 md:p-8">{children}</main>
    </div>
  );
}
