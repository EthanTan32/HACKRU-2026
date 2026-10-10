import UploadDemo from "@/components/upload-demo";

export default function Home() {
  return (
    <>
      <section className="hero min-h-[calc(100svh-4rem)]">
        <div className="hero-content text-center">
          <div className="max-w-lg -translate-y-32">
            <h1 className="text-7xl font-bold">Detect AI Videos Easily</h1>
            <p className="text-xl py-12">
              VerityAI detects minor inconsistencies in AI-generated videos that are difficult to spot by humans.
            </p>
            <a href="#demo" className="btn btn-success btn-lg">
              Try the demo
            </a>
          </div>
        </div>
      </section>

      <section
        id="demo"
        className="relative isolate min-h-screen flex flex-col items-center justify-center gap-10 px-4 py-24"
      >
        {/* Soft green glows behind the demo */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute left-1/2 top-1/2 size-[44rem] -translate-x-1/2 -translate-y-1/2">
            <div className="size-full rounded-full bg-radial from-success/12 to-transparent to-70% motion-safe:animate-pulse" />
          </div>
          <div className="absolute -left-40 top-10 size-[30rem]">
            <div className="size-full rounded-full bg-radial from-emerald-400/10 to-transparent to-70% motion-safe:animate-pulse" />
          </div>
          <div className="absolute -right-40 bottom-0 size-[34rem]">
            <div className="size-full rounded-full bg-radial from-teal-400/8 to-transparent to-70% motion-safe:animate-pulse" />
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
    </>
  );
}
