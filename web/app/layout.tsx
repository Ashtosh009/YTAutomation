import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Shorts Studio • No Brain Stickman",
  description: "Automated YouTube Shorts Review Queue & Control Panel",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-channel-darkest text-slate-100 antialiased flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="border-t border-channel-border py-6 text-center text-xs text-slate-500 bg-channel-dark/50">
          <div className="flex justify-center gap-6 mb-2">
            <a href="/about" className="hover:text-slate-400 transition-colors">
              About Channel
            </a>
            <a href="/privacy" className="hover:text-slate-400 transition-colors">
              Privacy Policy
            </a>
          </div>
          <p>© {new Date().getFullYear()} No Brain Stickman • Automated Studio Pipeline</p>
        </footer>
      </body>
    </html>
  );
}
