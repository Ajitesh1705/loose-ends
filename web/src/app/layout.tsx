import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Loose Ends",
  description: "Who promised what, to whom, by when — and is it slipping?",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
