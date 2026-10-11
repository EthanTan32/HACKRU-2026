"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import VideoDropzone from "@/components/video-dropzone";
import {
  artifactUrl,
  clearPendingFile,
  getJobStatus,
  getResults,
  mediaUrl,
  peekPendingFile,
  uploadVideo,
  type AnalysisResult,
  type Classification,
  type DetectorResult,
  type DetectorStatus,
  type EvidenceEvent,
  type JobProgress,
} from "@/lib/analysis";

type Phase = "idle" | "uploading" | "queued" | "running" | "completed" | "failed";

// The six backend detectors, in the same order as the views on the home page
const detectors = [
  {
    key: "depth_consistency",
    name: "Depth",
    body: "Estimates the 3D depth of each frame and checks that it stays consistent as things move.",
  },
  {
    key: "color_consistency",
    name: "Gamma & saturation",
    body: "Compares brightness and color between frames, especially in the shadows, where generators slip.",
  },
  {
    key: "optical_flow",
    name: "Motion",
    body: "Tracks points across frames and looks for movement that warps or speeds up unnaturally.",
  },
  {
    key: "background_motion",
    name: "Background",
    body: "Checks that the background moves like one solid scene when the camera moves.",
  },
  {
    key: "facial_consistency",
    name: "Faces",
    body: "Follows facial landmarks and checks that a face keeps its shape as the head turns.",
  },
  {
    key: "text_consistency",
    name: "On-screen text",
    body: "Reads text in the video and checks that letters stay stable from frame to frame.",
  },
];
const detectorName = (key?: string) => detectors.find((d) => d.key === key)?.name ?? key ?? "";

// Typical seconds each analysis stage takes, in the order the backend runs them (DETECTORS in
// FrameTrace/backend/app/pipeline.py) followed by the verdict. Measured on 11-second clips on a
// 14-core laptop CPU; the clip-length caps on sampled frames keep this fairly steady.
const STAGE_SECONDS = [19, 0.1, 21.5, 8.5, 2.5, 3, 0.5];
const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);

// How far through the analysis it is (0 to 1), by expected time rather than by step count, given
// the latest progress report and how long the current stage has been running since
function analysisFraction(report: JobProgress, stageSeconds: number) {
  if (report.total !== STAGE_SECONDS.length) return Math.min((report.step + 0.5) / report.total, 0.99);
  const done = sum(report.durations);
  const expectedDone = sum(STAGE_SECONDS.slice(0, report.step));
  // How much slower or faster this run is going than the typical timings, once there's enough to judge
  const speed = expectedDone > 2 ? Math.min(Math.max(done / expectedDone, 0.3), 4) : 1;
  const current = STAGE_SECONDS[report.step] * speed;
  const remaining = sum(STAGE_SECONDS.slice(report.step + 1)) * speed;
  // Move steadily through the stage's expected time; if it runs long, keep creeping toward its end
  // without reaching it, so the bar never claims a stage is finished before it is
  const steady = current * 0.9;
  const within =
    stageSeconds < steady
      ? stageSeconds
      : steady + current * 0.09 * (1 - Math.exp(-(stageSeconds - steady) / (current * 0.5)));
  return (done + within) / (done + current + remaining);
}


const statusLabel: Record<DetectorStatus, string> = {
  ok: "Analyzed",
  insufficient_data: "Not enough data",
  not_enabled: "Off",
  not_available: "Unavailable",
  error: "Error",
};

// Tailwind needs full class names in the source, so each tone spells them out
const tones = {
  error: { text: "text-error", soft: "bg-error/10 border-error/30" },
  success: { text: "text-success", soft: "bg-success/10 border-success/30" },
  warning: { text: "text-warning", soft: "bg-warning/10 border-warning/30" },
  neutral: { text: "text-base-content", soft: "bg-base-content/5 border-base-content/15" },
};

type Verdict = { title: string; tone: keyof typeof tones; body: string };

// The three verdicts VerityAI shows, picked from the model's estimated chance the video is AI
// (the backend's own likely/uncertain labels aren't used)
const LIKELY_AI_FROM = 0.5;
const LIKELY_REAL_BELOW = 0.3;
const categories: Record<"likely_ai" | "possibly_ai" | "likely_real", Verdict> = {
  likely_ai: {
    title: "Likely AI",
    tone: "error",
    body: "The measurements look more like generated video than camera footage.",
  },
  possibly_ai: {
    title: "Possibly AI",
    tone: "warning",
    body: "Some signs point to generation, but not strongly enough to be sure.",
  },
  likely_real: {
    title: "Likely real",
    tone: "success",
    body: "The measurements look more like camera footage than generated video.",
  },
};

// When the model gives no probability, say why instead
const noVerdict: Record<Exclude<Classification, "likely_ai" | "likely_real" | "uncertain">, Verdict> = {
  insufficient_evidence: {
    title: "Not enough evidence",
    tone: "neutral",
    body: "Too few of the checks could measure this clip to give a verdict.",
  },
  model_unavailable: {
    title: "Verdict unavailable",
    tone: "neutral",
    body: "The AI model couldn't run on the server, so only the raw measurements are shown.",
  },
  not_trained: {
    title: "Measurements only",
    tone: "neutral",
    body: "The AI model isn't loaded on the server, so there's no verdict. The measurements below still apply.",
  },
};

function verdictFor(result: AnalysisResult): Verdict {
  const p = result.ai_probability;
  if (p === null) return noVerdict[result.classification as keyof typeof noVerdict] ?? noVerdict.model_unavailable;
  if (p >= LIKELY_AI_FROM) return categories.likely_ai;
  if (p >= LIKELY_REAL_BELOW) return categories.possibly_ai;
  return categories.likely_real;
}

const artifactLabels: Record<string, string> = {
  first_frame: "First frame",
  depth_map: "Depth map",
  gamma_shadows: "Gamma (shadows lifted)",
  saturation_boost: "Saturation boosted",
  optical_flow: "Motion field",
  optical_flow_evidence: "Motion evidence",
  facial_consistency_evidence: "Face tracking",
};

const sentence = (s: string) => {
  const text = s.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};
const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export default function Analyzer() {
  const router = useRouter();
  const urlId = useSearchParams().get("id");

  // Where this visit starts: a video handed over from the home page, an analysis named in the
  // URL (after a refresh or from a shared link), or nothing yet
  const [handoff] = useState(() => ({ file: peekPendingFile() }));

  const [phase, setPhase] = useState<Phase>(handoff.file ? "uploading" : urlId ? "queued" : "idle");
  const [file, setFile] = useState<File | null>(handoff.file);
  // Local playback URL for the chosen file, paired with the file it was made from
  const [preview, setPreview] = useState<{ file: File; url: string } | null>(null);
  const [id, setId] = useState<string | null>(handoff.file ? null : urlId);
  const [progress, setProgress] = useState(0);
  // Share of the analysis done (0 to 1), and the latest progress report it is estimated from
  const [analysisShare, setAnalysisShare] = useState(0);
  const report = useRef<{ id: string; progress: JobProgress; at: number } | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Make the local preview URL here rather than when the file is picked: React re-runs effects
  // (StrictMode in development, and Next hiding then showing a kept page), and a URL made once
  // would be revoked by the first cleanup and leave the video pointing at nothing
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    // Syncing with a browser resource (an object URL), which effects are for
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreview({ file, url });
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Sends the video and moves on to waiting for the analysis
  const upload = async (picked: File) => {
    try {
      const job = await uploadVideo(picked, setProgress);
      setId(job.video_id);
      setPhase("queued");
      // Put the analysis in the URL so a refresh or shared link comes back to it
      router.replace(`/demo?id=${job.video_id}`, { scroll: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setPhase("failed");
    }
  };

  const start = (picked: File) => {
    setFile(picked);
    setResult(null);
    setError(null);
    setProgress(0);
    setAnalysisShare(0);
    setElapsed(0);
    setId(null);
    setPhase("uploading");
    void upload(picked);
  };

  const reset = () => {
    setPhase("idle");
    setFile(null);
    setId(null);
    setResult(null);
    setError(null);
    setAnalysisShare(0);
    setElapsed(0);
  };

  const startOver = () => {
    reset();
    router.replace("/demo", { scroll: false });
  };

  // Upload a video handed over from the home page. Next keeps recently visited pages alive and
  // only hides them, so this runs each time the page is shown, not just when it first mounts;
  // as a layout effect it switches over before paint, so an old view never flashes up.
  useLayoutEffect(() => {
    const pending = peekPendingFile();
    if (!pending) return;
    clearPendingFile();
    // Responding to a handoff from another page, which is an outside event, not derived state
    /* eslint-disable react-hooks/set-state-in-effect */
    if (pending === handoff.file) {
      // First visit: the initial state already shows this video uploading
      void upload(pending);
    } else {
      // The page was kept from an earlier visit, so reset it for the new video
      start(pending);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
    // upload and start only use setters and the router, which never change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The URL changing under us means navigation (back button, or the navbar's plain /demo
  // link), not our own update after uploading: switch to that analysis, or start over
  const [seenUrlId, setSeenUrlId] = useState(urlId);
  if (urlId !== seenUrlId) {
    setSeenUrlId(urlId);
    if (urlId && urlId !== id) {
      reset();
      setId(urlId);
      setPhase("queued");
    } else if (!urlId && seenUrlId) {
      reset();
    }
  }

  // Poll the backend until the analysis finishes
  useEffect(() => {
    if (!id || (phase !== "queued" && phase !== "running")) return;
    let alive = true;
    const check = async () => {
      try {
        const job = await getJobStatus(id);
        if (!alive) return;
        if (job.status === "completed") {
          const data = await getResults(id);
          if (!alive) return;
          setResult(data);
          setPhase("completed");
        } else if (job.status === "failed") {
          setError(job.error ?? "The analysis failed.");
          setPhase("failed");
        } else {
          if (job.progress) report.current = { id, progress: job.progress, at: performance.now() };
          setPhase(job.status);
        }
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Lost contact with the analysis server.");
        setPhase("failed");
      }
    };
    void check();
    const timer = window.setInterval(check, 1500);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [id, phase]);

  // Between polls, keep moving the bar using how long the current stage has been running.
  // It only ever moves forward, even when a new report changes the estimate.
  useEffect(() => {
    if (phase !== "running" || !id) return;
    const timer = window.setInterval(() => {
      const latest = report.current;
      if (!latest || latest.id !== id) return;
      const seconds = latest.progress.stage_elapsed + (performance.now() - latest.at) / 1000;
      const share = analysisFraction(latest.progress, seconds);
      // Glide toward the estimate rather than snapping, so a revised estimate never looks like a jump
      setAnalysisShare((shown) => Math.max(shown, shown + (share - shown) * 0.15));
    }, 100);
    return () => window.clearInterval(timer);
  }, [phase, id]);

  // Elapsed-time clock while working
  const busy = phase === "uploading" || phase === "queued" || phase === "running";
  useEffect(() => {
    if (!busy) return;
    const begin = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - begin) / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const seek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    video.play().catch(() => {});
    video.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  // The local file plays without a download; otherwise (after a refresh or from a shared link)
  // stream the uploaded copy from the backend
  const previewUrl = preview && preview.file === file ? preview.url : null;
  const videoSrc = previewUrl ?? (id ? mediaUrl(id) : null);

  if (phase === "idle") {
    return (
      <div className="card mx-auto w-full max-w-2xl border border-base-content/10 bg-base-100/80">
        <div className="card-body">
          <VideoDropzone onFile={start} />
        </div>
      </div>
    );
  }

  if (phase === "failed") {
    return (
      <div className="card mx-auto w-full max-w-2xl border border-error/30 bg-base-100/80">
        <div className="card-body items-center gap-4 text-center">
          <p className="text-lg font-semibold">Something went wrong</p>
          <p className="opacity-70">{error}</p>
          <div className="flex gap-2">
            {file && (
              <button type="button" className="btn btn-success" onClick={() => start(file)}>
                Try again
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={startOver}>
              Upload a different video
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (busy) {
    // One bar for the whole wait: uploading fills the first tenth, the analysis the rest
    const UPLOAD_SHARE = 0.1;
    const fraction =
      phase === "uploading" ? progress * UPLOAD_SHARE : UPLOAD_SHARE + (1 - UPLOAD_SHARE) * analysisShare;
    const percent = Math.round(fraction * 100);

    return (
      <div className="mx-auto grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="relative aspect-video overflow-hidden rounded-3xl bg-black">
          {videoSrc && (
            <video src={videoSrc} muted loop autoPlay playsInline className="size-full object-contain opacity-60" />
          )}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 h-32 bg-linear-to-b from-transparent via-success/20 to-transparent motion-safe:animate-scan"
          />
        </div>

        <div className="card border border-base-content/15 bg-base-100">
          <div className="card-body gap-5">
            <p className="text-lg font-semibold" aria-live="polite">
              Analyzing your video
            </p>
            <div>
              <div
                role="progressbar"
                aria-label="Analysis progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
                className="h-3 overflow-hidden rounded-full bg-base-content/20"
              >
                <div
                  className="h-full rounded-full bg-success transition-[width] duration-150 ease-linear"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-sm tabular-nums">
                <span className="font-semibold">{percent}%</span>
                <span className="opacity-60">Elapsed {clock(elapsed)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;
  const verdict = verdictFor(result);
  const tone = tones[verdict.tone];
  const duration = result.video.duration_seconds;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10">
      {/* Video and verdict */}
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-4">
          <div className="overflow-hidden rounded-3xl bg-black">
            {videoSrc && (
              <video ref={videoRef} src={videoSrc} controls playsInline className="aspect-video w-full object-contain" />
            )}
          </div>
          <Timeline events={result.timeline} duration={duration} onSeek={seek} />
        </div>

        <div className={`card border ${tone.soft}`}>
          <div className="card-body items-center gap-4 py-10 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] opacity-60">Verdict</p>
            <p className={`text-4xl font-bold ${tone.text}`}>{verdict.title}</p>
            <p className="text-sm opacity-70">{verdict.body}</p>
            <p className="text-xs opacity-50">
              {duration.toFixed(1)}s · {result.video.sampled_frames} frames sampled
            </p>
            <button type="button" className="btn btn-success btn-sm mt-2" onClick={startOver}>
              Analyze another video
            </button>
            {/* The raw model output, for us: small and faint, and only fades in after a few seconds */}
            {result.ai_probability !== null && (
              <p
                title="Model's estimated probability the video is AI-generated"
                className="mt-1 font-mono text-[11px] tabular-nums tracking-wider opacity-0 motion-safe:animate-[fade-in_1.2s_ease-out_3s_forwards] motion-reduce:opacity-100"
              >
                <span className="opacity-40">p(ai) {result.ai_probability.toFixed(3)}</span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* What each check found */}
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-2xl font-bold">What each check found</h2>
          <p className="mt-1 text-sm opacity-60">
            Anomaly scores compare this clip with real footage, so higher means more unusual. On their own they
            aren&apos;t a verdict.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {detectors.map((d) => (
            <DetectorCard key={d.key} name={d.name} body={d.body} result={result.detectors[d.key]} />
          ))}
        </div>
      </section>

      {result.artifacts.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-2xl font-bold">Under the hood</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {result.artifacts.map((name) => (
              <figure key={name} className="overflow-hidden rounded-box border border-base-content/10 bg-base-100/80">
                {/* Served by the analysis backend, so next/image's optimizer can't be used here */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={artifactUrl(result.video_id, name)} alt={artifactLabels[name] ?? sentence(name)} className="aspect-video w-full bg-black object-contain" />
                <figcaption className="px-4 py-3 text-sm opacity-70">{artifactLabels[name] ?? sentence(name)}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// Flagged moments as marks along the clip, plus a list; both jump the video to that moment
function Timeline({
  events,
  duration,
  onSeek,
}: {
  events: EvidenceEvent[];
  duration: number;
  onSeek: (time: number) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  if (!events.length) {
    return (
      <p className="rounded-box border border-base-content/10 bg-base-100/60 px-4 py-3 text-sm opacity-70">
        No individual moments were flagged. That alone doesn&apos;t mean the video is real.
      </p>
    );
  }
  const shown = showAll ? events : events.slice(0, 6);

  return (
    <div className="flex flex-col gap-3 rounded-box border border-base-content/10 bg-base-100/60 p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-semibold">Flagged moments</p>
        <p className="text-xs opacity-50">Click one to jump to it</p>
      </div>

      <div className="relative h-8 rounded-field bg-base-content/5">
        {events.map((e, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onSeek(e.timestamp)}
            aria-label={`${sentence(e.type)} at ${e.timestamp.toFixed(1)} seconds`}
            title={`${e.timestamp.toFixed(1)}s · ${sentence(e.type)}`}
            className="absolute bottom-0 w-1 -translate-x-1/2 rounded-full bg-success transition-transform hover:scale-x-150"
            style={{
              left: `${Math.min(Math.max(e.timestamp / (duration || 1), 0), 1) * 100}%`,
              height: `${30 + Math.min(Math.max(e.severity, 0), 1) * 70}%`,
              opacity: 0.4 + Math.min(Math.max(e.severity, 0), 1) * 0.6,
            }}
          />
        ))}
      </div>

      <ul className="divide-y divide-base-content/10">
        {shown.map((e, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => onSeek(e.timestamp)}
              className="flex w-full items-start justify-between gap-4 py-2 text-left hover:text-success"
            >
              <span>
                <span className="text-sm font-medium">{sentence(e.type)}</span>
                <span className="block text-xs opacity-60">
                  {detectorName(e.detector)} · {e.detail}
                </span>
              </span>
              <span className="shrink-0 text-xs tabular-nums opacity-70">{clock(e.timestamp)}</span>
            </button>
          </li>
        ))}
      </ul>
      {events.length > 6 && (
        <button type="button" className="btn btn-ghost btn-xs self-start" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show fewer" : `Show all ${events.length}`}
        </button>
      )}
    </div>
  );
}

function DetectorCard({ name, body, result }: { name: string; body: string; result?: DetectorResult }) {
  const status = result?.status ?? "not_available";
  const score = result?.anomaly_index ?? null;
  const flagged = result?.events.length ?? 0;
  const barColor = score === null ? "" : score >= 0.95 ? "bg-error" : score >= 0.8 ? "bg-warning" : "bg-success";
  const metrics = Object.entries(result?.metrics ?? {});

  return (
    <div className="card border border-base-content/10 bg-base-100/80">
      <div className="card-body gap-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold">{name}</h3>
          <span className={`badge badge-sm ${status === "ok" ? "badge-success badge-outline" : "badge-ghost"}`}>
            {statusLabel[status]}
          </span>
        </div>
        <p className="text-sm opacity-60">{body}</p>

        <div className="mt-1">
          <div className="flex items-baseline justify-between text-xs">
            <span className="opacity-60">Anomaly score</span>
            <span className="tabular-nums">{score === null ? "—" : Math.round(score * 100)}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-base-content/10">
            {score !== null && <div className={`h-full rounded-full ${barColor}`} style={{ width: `${score * 100}%` }} />}
          </div>
        </div>

        <p className="text-xs opacity-60">
          {flagged ? `${flagged} flagged moment${flagged === 1 ? "" : "s"}` : "No flagged moments"}
        </p>

        {(result?.note || metrics.length > 0) && (
          <details className="text-xs opacity-70">
            <summary className="cursor-pointer select-none">Details</summary>
            {result?.note && <p className="mt-2">{result.note}</p>}
            {metrics.length > 0 && (
              <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
                {metrics.map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="opacity-70">{sentence(key)}</dt>
                    <dd className="text-right tabular-nums">
                      {typeof value === "number" ? Number(value.toFixed(3)) : (value ?? "—")}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </details>
        )}
      </div>
    </div>
  );
}
