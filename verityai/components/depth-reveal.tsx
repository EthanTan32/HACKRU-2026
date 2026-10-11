"use client";

import { useEffect, useRef, useState } from "react";

type Mode = "real" | "ai";

// The video under the viewfinder, for the real clip and the AI-generated one
const baseSrc: Record<Mode, string> = {
  real: "/videos/real.mp4",
  ai: "/videos/ai/real.mp4",
};

// Analysis views that can be shown through the viewfinder, in arrow order.
const overlays = [
  {
    label: "Depth map",
    src: { real: "/videos/depth.mp4", ai: "/videos/ai/depth.mp4" },
    description:
      "A real camera records a real 3D scene, so depth changes smoothly as people and the camera move. Generated video has no actual geometry behind it, so its depth tends to warp from frame to frame: surfaces bend, objects pop forward or sink back, and backgrounds drift in ways real footage never does.",
  },
  {
    label: "Saturated",
    src: { real: "/videos/saturated.mp4", ai: "/videos/ai/saturated.mp4" },
    description:
      "Boosting saturation exaggerates small color differences until they are easy to see. In real footage an object keeps a steady color under steady light, while generated video tends to let hues drift, bleed across edges and shimmer in fine textures like skin, hair and foliage.",
  },
  {
    label: "Gamma",
    src: { real: "/videos/gamma.mp4", ai: "/videos/ai/gamma.mp4" },
    description:
      "Lifting the shadows with a gamma curve exposes the dark regions, where generation models are weakest. Real sensor noise is fine and consistent, but AI video tends to show shadows that boil and flicker between frames, smeared detail, and shading that doesn't match the light in the scene.",
  },
];

// A viewfinder that follows the cursor and shows an analysis view in place of the real video.
// Each overlay video sits on top, clipped to the viewfinder, and only the selected one is shown;
// the viewfinder is updated directly on the DOM each frame, so React only re-renders on arrow
// clicks and when switching between the real and AI clips.
export default function DepthReveal() {
  const [mode, setMode] = useState<Mode>("real");
  const boxRef = useRef<HTMLDivElement>(null);
  const realRef = useRef<HTMLVideoElement>(null);
  const overlayRefs = useRef<(HTMLVideoElement | null)[]>([]);
  const finderRef = useRef<HTMLDivElement>(null);

  const [index, setIndex] = useState(0);
  // The animation loop reads the selected overlay from a ref so it never has to restart
  const indexRef = useRef(0);
  const go = (i: number) => {
    const next = (i + overlays.length) % overlays.length;
    indexRef.current = next;
    setIndex(next);
  };

  useEffect(() => {
    const box = boxRef.current;
    const real = realRef.current;
    const views = overlayRefs.current.filter((v): v is HTMLVideoElement => v !== null);
    const finder = finderRef.current;
    if (!box || !real || views.length !== overlays.length || !finder) return;

    const now = () => performance.now() / 1000;
    const target = { x: 0, y: 0 };
    const pos = { x: 0, y: 0 };
    let placed = false; // first frame snaps the viewfinder to its resting corner
    let inside = false;
    let lastMove = -10;
    let holdUntil = -10; // after the cursor leaves, the viewfinder stays put until this time

    // Gap between the resting viewfinder and the top-right edges of the video
    const REST_MARGIN = 16;
    // How long the cursor can rest over the video, and how long it can be gone from it,
    // before the viewfinder heads back to its corner
    const IDLE_RETURN = 1.5;
    const LEAVE_RETURN = 5;

    // Viewfinder size, relative to the video
    const finderSize = () => {
      const w = Math.max(160, box.clientWidth * 0.32);
      return { w, h: w * 0.62 };
    };

    const onMove = (e: PointerEvent) => {
      const rect = box.getBoundingClientRect();
      target.x = e.clientX - rect.left;
      target.y = e.clientY - rect.top;
      inside = true;
      lastMove = now();
      holdUntil = -10;
    };
    const onLeave = () => {
      inside = false;
      // Only hold if it was following the cursor; if it had already gone back, leave it there
      const t = now();
      if (t - lastMove < IDLE_RETURN) holdUntil = t + LEAVE_RETURN;
    };
    box.addEventListener("pointermove", onMove);
    box.addEventListener("pointerleave", onLeave);

    // Which overlay is on screen, and the one it is fading in over after an arrow click
    let shown = indexRef.current;
    let previous = -1;
    let switchedAt = -10;
    const FADE = 0.3;

    // Keep every overlay on the same frame as the real video. Hidden overlays can simply jump
    // to the right time, but a jump on a visible one stutters, so small drift there is eased out
    // by nudging its playback speed instead.
    const sync = () => {
      views.forEach((view, i) => {
        if (view.readyState < 1) return;
        let drift = view.currentTime - real.currentTime;
        // Measure across the loop point, so 0.1s after the start isn't read as a whole clip behind
        const duration = real.duration;
        if (duration && Math.abs(drift) > duration / 2) drift -= Math.sign(drift) * duration;

        const onScreen = i === shown || i === previous;
        if (!onScreen || Math.abs(drift) > 0.5) {
          if (Math.abs(drift) > 0.15) view.currentTime = real.currentTime;
          view.playbackRate = 1;
        } else {
          view.playbackRate = Math.abs(drift) < 0.02 ? 1 : Math.min(1.1, Math.max(0.9, 1 - drift * 2));
        }
      });
    };
    real.addEventListener("playing", sync);
    real.addEventListener("seeked", sync);

    // Only play and animate while the section is on screen
    let visible = false;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      for (const video of [real, ...views]) {
        if (visible) video.play().catch(() => {});
        else video.pause();
      }
    });
    observer.observe(box);

    let frame = 0;
    let last = now();
    const tick = () => {
      frame = requestAnimationFrame(tick);
      const t = now();
      const dt = Math.min(t - last, 0.1);
      last = t;
      if (!visible) return;

      // Follow the cursor while it moves over the video, and stay where it left off for a while
      // after it leaves; return to the corner once it rests or has been gone long enough
      const active = (inside && t - lastMove < IDLE_RETURN) || t < holdUntil;

      const W = box.clientWidth;
      const H = box.clientHeight;
      const { w, h } = finderSize();
      let cx: number;
      let cy: number;
      if (active) {
        // Keep the viewfinder inside the video so its frame and label never get cut off
        cx = Math.min(Math.max(target.x, w / 2), W - w / 2);
        cy = Math.min(Math.max(target.y, h / 2), H - h / 2);
      } else {
        // Rest in the top-right corner, just off the edges
        cx = W - w / 2 - REST_MARGIN;
        cy = h / 2 + REST_MARGIN;
      }

      if (!placed) {
        pos.x = cx;
        pos.y = cy;
        placed = true;
      }

      // Slightly lagging follow, a gentler glide on the way back, frame-rate independent
      const follow = 1 - Math.exp(-(active ? 10 : 5) * dt);
      pos.x += (cx - pos.x) * follow;
      pos.y += (cy - pos.y) * follow;

      const left = pos.x - w / 2;
      const top = pos.y - h / 2;

      const clip = `inset(${top}px ${W - left - w}px ${H - top - h}px ${left}px round 12px)`;

      // Fade the newly picked overlay in on top of the old one, which stays fully visible
      // underneath until the fade finishes, so the real video never shows through mid-switch
      if (indexRef.current !== shown) {
        previous = shown;
        shown = indexRef.current;
        switchedAt = t;
      }
      const fadeIn = Math.min((t - switchedAt) / FADE, 1);
      if (fadeIn >= 1) previous = -1;
      views.forEach((view, i) => {
        view.style.clipPath = clip;
        view.style.zIndex = i === shown ? "2" : i === previous ? "1" : "0";
        view.style.opacity = i === shown ? String(fadeIn) : i === previous ? "1" : "0";
      });
      finder.style.transform = `translate(${left}px, ${top}px)`;
      finder.style.width = `${w}px`;
      finder.style.height = `${h}px`;
      finder.style.opacity = "1";

      if (!real.paused) sync();
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      box.removeEventListener("pointermove", onMove);
      box.removeEventListener("pointerleave", onLeave);
      real.removeEventListener("playing", sync);
      real.removeEventListener("seeked", sync);
    };
    // Switching clips swaps every video's source, so start playback and syncing over
  }, [mode]);

  const { label, description } = overlays[index];

  return (
    <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      {/* Arrows, video and title in one row; the real / AI toggle sits under the video */}
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-5">
        <ArrowButton direction="previous" onClick={() => go(index - 1)} />

        <div ref={boxRef} className="relative aspect-video w-full overflow-hidden rounded-3xl bg-black">
          <video
            ref={realRef}
            src={baseSrc[mode]}
            muted
            loop
            playsInline
            preload="auto"
            className="absolute inset-0 size-full object-cover"
          />
          {overlays.map((overlay, i) => (
            <video
              key={overlay.label}
              ref={(el) => {
                overlayRefs.current[i] = el;
              }}
              src={overlay.src[mode]}
              muted
              loop
              playsInline
              preload="auto"
              aria-hidden="true"
              className="absolute inset-0 size-full object-cover"
              style={{ clipPath: "inset(50% 50% 50% 50%)", opacity: 0 }}
            />
          ))}

          {/* Viewfinder frame: thin outline, corner brackets, label and a slow scan line */}
          <div
            ref={finderRef}
            aria-hidden="true"
            className="pointer-events-none absolute left-0 top-0 z-10 overflow-hidden rounded-xl border border-success/30 opacity-0"
          >
            <span className="absolute left-0 top-0 size-5 rounded-tl-xl border-l-2 border-t-2 border-success" />
            <span className="absolute right-0 top-0 size-5 rounded-tr-xl border-r-2 border-t-2 border-success" />
            <span className="absolute bottom-0 left-0 size-5 rounded-bl-xl border-b-2 border-l-2 border-success" />
            <span className="absolute bottom-0 right-0 size-5 rounded-br-xl border-b-2 border-r-2 border-success" />
            <span className="absolute left-3 top-3 rounded bg-success px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-black">
              {label}
            </span>
            <div className="absolute inset-x-0 h-16 bg-linear-to-b from-transparent via-success/15 to-transparent motion-safe:animate-scan motion-reduce:hidden" />
          </div>
        </div>

        {/* Name of the selected view, read top to bottom */}
        <p
          aria-live="polite"
          className="shrink-0 text-lg font-semibold uppercase tracking-[0.3em] text-success [writing-mode:vertical-rl]"
        >
          {label}
        </p>

        <ArrowButton direction="next" onClick={() => go(index + 1)} />

        <div role="group" aria-label="Video source" className="join col-start-2 justify-self-center">
          {(["real", "ai"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={`btn join-item btn-sm min-w-24 ${mode === m ? "btn-success" : "btn-ghost border-base-content/20"}`}
            >
              {m === "real" ? "Real" : "AI"}
            </button>
          ))}
        </div>

        <p className="col-start-2 -mt-2 justify-self-center text-sm opacity-60">
          Move your cursor over the video to look beneath it
        </p>
      </div>

      {/* How the analysis works, then why the selected view matters.
          Styled like the viewfinder: thin frame, green corner brackets and a green accent rail. */}
      <div className="relative rounded-box border border-base-content/10 bg-base-100/70 backdrop-blur">
        <span aria-hidden="true" className="absolute -left-px -top-px size-4 rounded-tl-box border-l-2 border-t-2 border-success" />
        <span aria-hidden="true" className="absolute -right-px -top-px size-4 rounded-tr-box border-r-2 border-t-2 border-success" />
        <span aria-hidden="true" className="absolute -bottom-px -left-px size-4 rounded-bl-box border-b-2 border-l-2 border-success" />
        <span aria-hidden="true" className="absolute -bottom-px -right-px size-4 rounded-br-box border-b-2 border-r-2 border-success" />

        <div className="card-body gap-6 leading-relaxed">
          <p className="opacity-70">
            VerityAI breaks each clip into measurable properties of the video, like its depth, color
            saturation and response in the shadows. Each one is plugged into mathematical functions that
            score how consistently it changes from frame to frame, and those scores are fed into a fusion
            LLM that weighs all the evidence together to decide whether the video is real or generated.
          </p>

          {/* Green rail beside the part that changes with the arrows */}
          <div className="border-l-2 border-success pl-4">
            <p key={index} aria-live="polite" className="motion-safe:animate-fade-in">
              <span className="font-semibold text-success">{label}.</span>{" "}
              <span className="opacity-70">{description}</span>
            </p>
          </div>

          {/* Which of the views is selected, one segment per arrow stop */}
          <div aria-hidden="true" className="flex gap-1.5">
            {overlays.map((overlay, i) => (
              <span
                key={overlay.label}
                className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                  i === index ? "bg-success" : "bg-base-content/15"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ArrowButton({ direction, onClick }: { direction: "previous" | "next"; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={direction === "previous" ? "Previous view" : "Next view"}
      onClick={onClick}
      className="btn btn-circle btn-ghost shrink-0"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="size-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d={direction === "previous" ? "M15.75 19.5L8.25 12l7.5-7.5" : "M8.25 4.5l7.5 7.5-7.5 7.5"}
        />
      </svg>
    </button>
  );
}
