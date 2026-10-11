"use client";

import { useEffect, useRef } from "react";

const rand = (min: number, max: number) => min + Math.random() * (max - min);

// One random horizontal slice of the word, nudged sideways
const slice = () => {
  const top = rand(0, 75);
  const height = rand(8, 30);
  return {
    opacity: rand(0.5, 0.85),
    transform: `translateX(${rand(-4, 4).toFixed(1)}px)`,
    clipPath: `inset(${top}% 0 ${Math.max(0, 100 - top - height)}% 0)`,
  };
};

// A word that briefly "corrupts" like a bad video frame, at random moments
export default function GlitchText({ children }: { children: string }) {
  const layerA = useRef<HTMLSpanElement>(null);
  const layerB = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer: ReturnType<typeof setTimeout>;

    const burst = () => {
      for (const layer of [layerA.current, layerB.current]) {
        if (!layer) continue;
        const steps = Math.round(rand(2, 4));
        const frames = Array.from({ length: steps }, slice);
        layer.animate([...frames, { opacity: 0 }], {
          duration: rand(160, 340),
          easing: "steps(1, end)",
          delay: rand(0, 60),
        });
      }
      // Usually wait a second or few; sometimes stutter again almost immediately
      const next = Math.random() < 0.25 ? rand(120, 300) : rand(900, 3500);
      timer = setTimeout(burst, next);
    };
    timer = setTimeout(burst, rand(600, 1500));
    return () => clearTimeout(timer);
  }, []);

  return (
    <span className="relative inline-block">
      {children}
      <span
        ref={layerA}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 text-success opacity-0"
      >
        {children}
      </span>
      <span
        ref={layerB}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 text-[color-mix(in_oklch,var(--color-success)_55%,white)] opacity-0"
      >
        {children}
      </span>
    </span>
  );
}
