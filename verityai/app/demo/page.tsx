import type { Metadata } from "next";
import { Suspense } from "react";
import Analyzer from "@/components/analyzer";

export const metadata: Metadata = {
  title: "Demo · VerityAI",
  description: "Upload a video and VerityAI will check it for signs of AI generation.",
};

export default function DemoPage() {
  return (
    <main className="flex flex-col items-center gap-12 px-4 pb-24 pt-12">
      <div className="max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-success">Demo</p>
        <h1 className="mt-3 text-5xl font-bold">Analyze a video</h1>
        <p className="mt-4 text-lg opacity-70">
          VerityAI checks depth, motion, color, faces and text frame by frame, then weighs the evidence to
          judge whether the clip was generated.
        </p>
      </div>

      {/* The analyzer reads ?id= from the URL, which has to be inside a Suspense boundary */}
      <Suspense fallback={<span className="loading loading-ring loading-lg text-success" />}>
        <Analyzer />
      </Suspense>
    </main>
  );
}
