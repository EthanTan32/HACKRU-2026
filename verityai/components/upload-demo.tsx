"use client";

import { useRouter } from "next/navigation";
import VideoDropzone from "@/components/video-dropzone";
import { setPendingFile } from "@/lib/analysis";

// Home page upload box: picking a video goes straight to the demo page, which starts analyzing it
export default function UploadDemo() {
  const router = useRouter();

  return (
    <div className="card w-full max-w-2xl bg-base-100/80 border border-base-content/10">
      <div className="card-body">
        <VideoDropzone
          onFile={(file) => {
            setPendingFile(file);
            router.push("/demo");
          }}
        />
      </div>
    </div>
  );
}
