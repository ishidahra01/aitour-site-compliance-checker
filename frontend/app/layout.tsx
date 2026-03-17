import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "基地局設置チェッカー",
  description:
    "基地局設置適合性チェッカー — Powered by GitHub Copilot SDK, Work IQ MCP, M365 Copilot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className="antialiased font-sans bg-gray-50">{children}</body>
    </html>
  );
}
