import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Site Approval Bot",
  description: "Site Approval Bot powered by GitHub Copilot SDK and Work IQ — automates approval workflows for site installation requests",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
