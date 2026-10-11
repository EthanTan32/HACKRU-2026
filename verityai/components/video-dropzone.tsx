"use client";

import { useRef, useState } from "react";
import { MAX_DURATION_SECONDS, MAX_UPLOAD_MB, videoDuration } from "@/lib/analysis";

// Drop area / file picker for a single video. Checks the backend's size and length limits
// in the browser first, so a bad file is rejected immediately instead of after uploading.
export default function VideoDropzone({ onFile }: { onFile: (file: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickFile = async (files: FileList | null) => {
    const picked = files?.[0];
    if (inputRef.current) inputRef.current.value = "";
    if (!picked) return;
    if (!picked.type.startsWith("video/")) {
      setError("That file isn't a video. Try an MP4, MOV or WebM.");
      return;
    }
    if (picked.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`That video is over ${MAX_UPLOAD_MB} MB. Try a shorter or smaller clip.`);
      return;
    }
    const duration = await videoDuration(picked);
    if (duration !== null && duration > MAX_DURATION_SECONDS + 0.5) {
      setError(`That video is ${Math.round(duration)} seconds long. Clips can be up to ${MAX_DURATION_SECONDS} seconds.`);
      return;
    }
    setError(null);
    onFile(picked);
  };

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => pickFile(e.target.files)}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pickFile(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center justify-center gap-4 rounded-box border-2 border-dashed px-6 py-16 transition-colors cursor-pointer ${
          dragging
            ? "border-success bg-success/10"
            : "border-base-content/20 hover:border-success/60 hover:bg-success/5"
        }`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-12 w-12 text-success"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
        <span className="text-lg font-semibold">Drop a video here or click to upload</span>
        <span className="text-sm opacity-60">
          MP4, MOV or WebM · up to {MAX_UPLOAD_MB} MB and {MAX_DURATION_SECONDS} seconds
        </span>
      </button>
      {error && (
        <p role="alert" className="text-center text-sm text-error">
          {error}
        </p>
      )}
    </div>
  );
}
