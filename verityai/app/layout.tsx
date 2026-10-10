import type { Metadata } from "next";
import { Aleo, Google_Sans } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/navbar";
import Background from "@/components/background";

const googleSans = Google_Sans({
  variable: "--font-google-sans",
  subsets: ["latin"],
  // Next has no size-matched fallback for Google Sans, so use plain system fonts instead
  adjustFontFallback: false,
  fallback: ["system-ui", "sans-serif"],
});

const aleo = Aleo({
  variable: "--font-aleo",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VerityAI",
  description: "Detect AI-generated videos easily.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      data-theme="dark"
      data-scroll-behavior="smooth"
      lang="en"
      className={`${googleSans.variable} ${aleo.variable} h-full antialiased scroll-smooth`}
    >
      <body className="min-h-full flex flex-col font-(family-name:--font-google-sans)">
        <Background />
        <Navbar />
        {children}
      </body>
    </html>
  );
}
