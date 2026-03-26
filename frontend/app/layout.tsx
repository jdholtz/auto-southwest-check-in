import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "SW Check-In",
  description: "Southwest Airlines Auto Check-In Monitor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <div className="flex min-h-screen bg-gray-50">
          <Sidebar />
          <main className="ml-64 flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
