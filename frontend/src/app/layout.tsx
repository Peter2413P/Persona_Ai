import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

import { PersonaProvider } from "@/components/PersonaProvider";

export const metadata: Metadata = {
  title: "PersonaForge AI",
  description: "Intelligent document + internet RAG chatbot.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex bg-zinc-950 text-zinc-50 overflow-hidden">
        <PersonaProvider>
          <Sidebar />
          <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden bg-zinc-900/30">
            {children}
          </main>
        </PersonaProvider>
      </body>
    </html>
  );
}
