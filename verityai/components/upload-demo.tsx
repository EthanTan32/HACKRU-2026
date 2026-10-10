"use client";

import { useEffect, useRef, useState } from "react";

export default function UploadDemo() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Free the temporary preview URL when it changes or the component unmounts
  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const pickFile = (files: FileList | null) => {
    const picked = files?.[0];
    if (!picked || !picked.type.startsWith("video/")) return;
    setFile(picked);
    // A temporary URL lets the chosen video play in the browser
    setPreviewUrl(URL.createObjectURL(picked));
  };

  const reset = () => {
    setFile(null);
    setPreviewUrl(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="card w-full max-w-2xl bg-base-100/80 border border-base-content/10">
      <div className="card-body gap-6">
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => pickFile(e.target.files)}
        />

        {file && previewUrl ? (
          <>
            <video src={previewUrl} controls className="w-full rounded-box bg-black" />
            <div className="flex items-center justify-between gap-4">
              <p className="truncate text-sm opacity-70">{file.name}</p>
              <div className="flex gap-2">
                <button className="btn btn-ghost" onClick={reset}>
                  Choose another
                </button>
                <button className="btn btn-success">Analyze video</button>
              </div>
            </div>
          </>
        ) : (
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
            <span className="text-sm opacity-60">MP4, MOV or WebM</span>
          </button>
        )}
      </div>
    </div>
  );
}
