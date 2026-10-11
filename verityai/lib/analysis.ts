// Client for the FrameTrace analysis backend (FrameTrace/backend, FastAPI on port 8000 by default)

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Limits enforced by the backend, checked here first so people get a clear message right away
export const MAX_UPLOAD_MB = 100;
export const MAX_DURATION_SECONDS = 30;

export type DetectorStatus = "ok" | "insufficient_data" | "not_enabled" | "not_available" | "error";

export type EvidenceEvent = {
  timestamp: number;
  type: string;
  severity: number;
  detail: string;
  detector?: string;
};

export type DetectorResult = {
  name: string;
  status: DetectorStatus;
  anomaly_index: number | null;
  events: EvidenceEvent[];
  metrics: Record<string, string | number | null>;
  note: string;
};

export type Classification =
  | "likely_ai"
  | "likely_real"
  | "uncertain"
  | "insufficient_evidence"
  | "model_unavailable"
  | "not_trained";

export type AnalysisResult = {
  video_id: string;
  classification: Classification;
  ai_probability: number | null;
  message: string;
  artifacts: string[];
  video: { duration_seconds: number; fps: number; sampled_frames: number };
  detectors: Record<string, DetectorResult>;
  timeline: EvidenceEvent[];
};

// Which stage a running analysis has reached: step counts from 0 and stage names the detector
// (or "classifier" for the final verdict) that is running now. stage_elapsed is how long it has
// been running and durations how long each finished stage took, in seconds.
export type JobProgress = {
  step: number;
  total: number;
  stage: string;
  stage_elapsed: number;
  durations: number[];
};

export type JobStatus = {
  video_id: string;
  status: "queued" | "running" | "failed" | "completed";
  error?: string | null;
  progress?: JobProgress | null;
};

// Uses XMLHttpRequest rather than fetch so the page can show upload progress
export function uploadVideo(file: File, onProgress: (fraction: number) => void) {
  return new Promise<{ video_id: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/videos`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: { video_id?: string; detail?: string } = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300 && body.video_id) resolve({ video_id: body.video_id });
      else reject(new Error(body.detail ?? `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error(unreachable()));
    const form = new FormData();
    form.append("video", file);
    xhr.send(form);
  });
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  } catch {
    throw new Error(unreachable());
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const getJobStatus = (id: string) => getJson<JobStatus>(`/api/videos/${id}/status`);
export const getResults = (id: string) => getJson<AnalysisResult>(`/api/videos/${id}/results`);
export const mediaUrl = (id: string) => `${API_URL}/api/videos/${id}/media`;
export const artifactUrl = (id: string, name: string) => `${API_URL}/api/videos/${id}/artifacts/${name}`;

function unreachable() {
  return `Couldn't reach the analysis server at ${API_URL}. Make sure the backend is running.`;
}

// Hands a video picked on the home page to the demo page. It only lives in memory, which is
// enough for a client-side navigation; after a refresh the demo page uses the ?id= in the URL.
let pendingFile: File | null = null;
export const setPendingFile = (file: File) => {
  pendingFile = file;
};
export const peekPendingFile = () => pendingFile;
export const clearPendingFile = () => {
  pendingFile = null;
};

// Reads a video's length in the browser so over-long clips are caught before uploading
export function videoDuration(file: File) {
  return new Promise<number | null>((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(Number.isFinite(video.duration) ? video.duration : null);
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    video.src = url;
  });
}
