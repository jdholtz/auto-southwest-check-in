import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SW Check-In",
  description: "Southwest Airlines Auto Check-In Monitor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
