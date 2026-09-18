"use client";

import { AuthProvider } from "@/lib/auth";
import { Header } from "@/components/Header";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-[#f6f8fa] text-[#24292f]">
        <AuthProvider>
          <Header />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
