import UploadDemo from "@/components/upload-demo";

export default function Home() {
  return (
    <>
      <section className="hero relative min-h-[calc(100svh-4rem)]">
        <div className="hero-content text-center">
          <div className="max-w-lg -translate-y-32">
            <h1 className="text-7xl font-bold">Detect AI Videos Easily™</h1>
            <p className="text-xl py-12">
              VerityAI detects minor inconsistencies in AI-generated videos that are difficult to spot by humans.
            </p>
            <a href="#demo" className="btn btn-success btn-lg">
              Try the demo
            </a>
          </div>
        </div>

        {/* Scroll cue: bouncing arrow between two thin lines */}
        <a
          href="#demo"
          aria-label="Scroll down to the demo"
          className="absolute bottom-10 left-1/2 flex -translate-x-1/2 items-center gap-5 opacity-70 transition-opacity hover:opacity-100"
        >
          <span className="h-0.5 w-24 bg-white/50" />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="size-6 text-white motion-safe:animate-bounce"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m0 0l-6.75-6.75M12 19.5l6.75-6.75" />
          </svg>
          <span className="h-0.5 w-24 bg-white/50" />
        </a>
      </section>

      <section
        id="demo"
        className="relative isolate min-h-screen flex flex-col items-center justify-center gap-10 px-4 py-24"
      >
        {/* Soft green glows behind the demo */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute left-1/2 top-1/2 size-[44rem] -translate-x-1/2 -translate-y-1/2">
            <div className="size-full rounded-full bg-radial from-success/12 to-transparent to-70%" />
          </div>
          <div className="absolute -left-40 top-10 size-[30rem] motion-safe:animate-drift-2">
            <div className="size-full rounded-full bg-radial from-success/12 to-transparent to-70% motion-safe:animate-pulse-slow [animation-duration:7.5s]! [animation-delay:-2s]!" />
          </div>
          <div className="absolute -right-40 bottom-0 size-[34rem] motion-safe:animate-drift-3">
            <div className="size-full rounded-full bg-radial from-success/12 to-transparent to-70% motion-safe:animate-pulse-slow [animation-duration:9s]! [animation-delay:-5s]!" />
          </div>
        </div>

        <div className="text-center">
          <h2 className="text-5xl font-bold">Try it yourself</h2>
          <p className="text-lg mt-4 opacity-70">
            Upload a video and VerityAI will check it for signs of AI generation.
          </p>
        </div>
        <UploadDemo />
      </section>

      <section id="about" className="flex flex-col items-center gap-16 px-4 py-32">
        <div className="max-w-3xl text-center">
          <h2 className="text-5xl font-bold">About VerityAI</h2>
          <p className="text-lg mt-6 opacity-70">
            AI-generated video is getting harder to tell apart from the real thing. VerityAI looks past what
            your eyes catch and checks a video frame by frame for the small inconsistencies that generation
            models leave behind.
          </p>
        </div>

        <div className="grid w-full max-w-5xl gap-6 md:grid-cols-3">
          {steps.map((step, i) => (
            <div key={step.title} className="card bg-base-100/80 border border-base-content/10">
              <div className="card-body gap-4">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 items-center justify-center rounded-full bg-success/15 text-success font-bold">
                    {i + 1}
                  </span>
                  <h3 className="card-title">{step.title}</h3>
                </div>
                <p className="opacity-70">{step.body}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap justify-center gap-3">
          {signals.map((signal) => (
            <span key={signal} className="badge badge-outline badge-success badge-lg">
              {signal}
            </span>
          ))}
        </div>

        <p className="text-sm opacity-50">Built at HackRU 2026.</p>
      </section>
    </>
  );
}

const steps = [
  {
    title: "Upload",
    body: "Drop in any video clip. It plays right in your browser so you can check you picked the right one.",
  },
  {
    title: "Analyze",
    body: "Our model scans the video frame by frame, comparing motion, lighting and fine detail over time.",
  },
  {
    title: "Get a verdict",
    body: "See how likely the video is to be AI-generated, along with the moments that raised a flag.",
  },
];

const signals = [
  "Unnatural motion",
  "Lighting mismatches",
  "Warping textures",
  "Flickering details",
  "Inconsistent faces",
];
