"use client";

import { useEffect, useRef } from "react";

// A viewfinder that follows the cursor and shows the depth map in place of the real video.
// The depth video sits on top, clipped to the viewfinder; everything is updated directly
// on the DOM each frame, so React never re-renders.
export default function DepthReveal() {
  const boxRef = useRef<HTMLDivElement>(null);
  const realRef = useRef<HTMLVideoElement>(null);
  const depthRef = useRef<HTMLVideoElement>(null);
  const finderRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const box = boxRef.current;
    const real = realRef.current;
    const depth = depthRef.current;
    const finder = finderRef.current;
    const hint = hintRef.current;
    if (!box || !real || !depth || !finder || !hint) return;

    const now = () => performance.now() / 1000;
    const target = { x: 0, y: 0 };
    const pos = { x: 0, y: 0 };
    let open = 0; // 0 = closed, 1 = fully open
    let inside = false;
    let lastMove = -10;

    // Viewfinder size at full open, relative to the video
    const finderSize = () => {
      const w = Math.max(160, box.clientWidth * 0.32);
      return { w, h: w * 0.62 };
    };

    const onMove = (e: PointerEvent) => {
      const rect = box.getBoundingClientRect();
      target.x = e.clientX - rect.left;
      target.y = e.clientY - rect.top;
      // Start the viewfinder where the cursor enters instead of sliding in from a corner
      if (!inside && open < 0.01) {
        pos.x = target.x;
        pos.y = target.y;
      }
      inside = true;
      lastMove = now();
    };
    const onLeave = () => {
      inside = false;
    };
    box.addEventListener("pointermove", onMove);
    box.addEventListener("pointerleave", onLeave);

    // Keep the depth video on the same frame as the real one
    const sync = () => {
      depth.currentTime = real.currentTime;
    };
    real.addEventListener("playing", sync);
    real.addEventListener("seeked", sync);

    // Only play and animate while the section is on screen
    let visible = false;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) {
        real.play().catch(() => {});
        depth.play().catch(() => {});
      } else {
        real.pause();
        depth.pause();
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

      // Open while the cursor is moving over the video, close after it rests or leaves
      const active = inside && t - lastMove < 1.5;
      open += ((active ? 1 : 0) - open) * (1 - Math.exp(-(active ? 6 : 3) * dt));

      // Keep the full-size viewfinder inside the video so its frame and label never get cut off
      const W = box.clientWidth;
      const H = box.clientHeight;
      const full = finderSize();
      const cx = Math.min(Math.max(target.x, full.w / 2), W - full.w / 2);
      const cy = Math.min(Math.max(target.y, full.h / 2), H - full.h / 2);

      // Slightly lagging follow, frame-rate independent
      const follow = 1 - Math.exp(-10 * dt);
      pos.x += (cx - pos.x) * follow;
      pos.y += (cy - pos.y) * follow;

      // Grow from a smaller frame as it opens
      const scale = 0.6 + 0.4 * open;
      const w = full.w * scale;
      const h = full.h * scale;
      const left = pos.x - w / 2;
      const top = pos.y - h / 2;

      depth.style.clipPath =
        open < 0.01
          ? "inset(50% 50% 50% 50%)"
          : `inset(${top}px ${W - left - w}px ${H - top - h}px ${left}px round 12px)`;
      depth.style.opacity = String(Math.min(open * 1.5, 1));
      finder.style.transform = `translate(${left}px, ${top}px)`;
      finder.style.width = `${w}px`;
      finder.style.height = `${h}px`;
      finder.style.opacity = String(open);
      hint.style.opacity = String(Math.max(0, 1 - open * 3) * 0.8);

      if (!real.paused && Math.abs(depth.currentTime - real.currentTime) > 0.15) sync();
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
  }, []);

  return (
    <div ref={boxRef} className="relative aspect-video w-full overflow-hidden rounded-3xl bg-black">
      <video
        ref={realRef}
        src="/videos/real.mp4"
        muted
        loop
        playsInline
        preload="auto"
        className="absolute inset-0 size-full object-cover"
      />
      <video
        ref={depthRef}
        src="/videos/depth.mp4"
        muted
        loop
        playsInline
        preload="auto"
        aria-hidden="true"
        className="absolute inset-0 size-full object-cover"
        style={{ clipPath: "inset(50% 50% 50% 50%)", opacity: 0 }}
      />

      {/* Viewfinder frame: thin outline, corner brackets, label and a slow scan line */}
      <div
        ref={finderRef}
        aria-hidden="true"
        className="pointer-events-none absolute left-0 top-0 overflow-hidden rounded-xl border border-success/30 opacity-0"
      >
        <span className="absolute left-0 top-0 size-5 rounded-tl-xl border-l-2 border-t-2 border-success" />
        <span className="absolute right-0 top-0 size-5 rounded-tr-xl border-r-2 border-t-2 border-success" />
        <span className="absolute bottom-0 left-0 size-5 rounded-bl-xl border-b-2 border-l-2 border-success" />
        <span className="absolute bottom-0 right-0 size-5 rounded-br-xl border-b-2 border-r-2 border-success" />
        <span className="absolute left-3 top-3 rounded bg-success px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-black">
          Depth map
        </span>
        <div className="absolute inset-x-0 h-16 bg-linear-to-b from-transparent via-success/15 to-transparent motion-safe:animate-scan motion-reduce:hidden" />
      </div>

      <p
        ref={hintRef}
        className="pointer-events-none absolute bottom-4 left-4 rounded-full bg-black/50 px-3 py-1 text-sm text-white backdrop-blur"
      >
        Move your cursor over the video to reveal its depth
      </p>
    </div>
  );
}
