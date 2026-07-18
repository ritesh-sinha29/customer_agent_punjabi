import type { Metadata } from "next";
import { Geist, Geist_Mono, Inter, Noto_Sans_Gurmukhi } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const gurmukhi = Noto_Sans_Gurmukhi({
  weight: ["400", "500", "600", "700"],
  subsets: ["gurmukhi"],
  variable: "--font-gurmukhi",
});

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nourishing Livestock, Empowering Farmers",
  description:
    "Nourishing Livestock, Empowering Farmers - Complete care for every animal.",
};

import { Toaster } from "@/components/ui/sonner";
import QueryProvider from "@/providers/query-provider";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn(
        "h-full",
        "antialiased",
        geistSans.variable,
        geistMono.variable,
        "font-sans",
        inter.variable,
        gurmukhi.variable,
      )}
    >
      <body className="min-h-full flex flex-col">
        <QueryProvider>
          {children}
        </QueryProvider>
        <Toaster position="top-center" />
      </body>
    </html>
  );
}
