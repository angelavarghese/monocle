import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Monocle | Smart market watchlists",
  description: "Read the fine print of the market.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
