"use client";

import { useState } from "react";

type Article = { source: string; year: number; title: string; url: string };

const risks: {
  tab: string;
  title: string;
  body: string;
  icon: React.ReactNode;
  articles: Article[];
}[] = [
  {
    tab: "Misinformation",
    title: "Fake news that looks like real news",
    body: "A fabricated clip of a politician, official or breaking news event can reach millions of people before fact-checkers catch up, and corrections rarely travel as far as the original. In 2022, hackers planted a deepfake of Ukraine's president telling his soldiers to surrender on a Ukrainian news site.",
    icon: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="M12 9v4M12 16h.01" />
      </>
    ),
    articles: [
      {
        source: "NPR",
        year: 2022,
        title: "Deepfake video of Zelenskyy could be 'tip of the iceberg' in info war, experts warn",
        url: "https://www.npr.org/2022/03/16/1087062648/deepfake-video-zelenskyy-experts-war-manipulation-ukraine-russia",
      },
    ],
  },
  {
    tab: "Fraud",
    title: "Scams with a familiar face",
    body: "Scammers can now impersonate a boss, colleague or relative on a live video call. In 2024, a finance worker in Hong Kong paid out about $25 million after a call in which the company's \"CFO\" and other colleagues were all deepfakes.",
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .8 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5V8M12 16v1.5" />
      </>
    ),
    articles: [
      {
        source: "CNN",
        year: 2024,
        title: "Finance worker pays out $25 million after video call with deepfake 'chief financial officer'",
        url: "https://edition.cnn.com/2024/02/04/asia/deepfake-cfo-scam-hong-kong-intl-hnk",
      },
    ],
  },
  {
    tab: "Personal harm",
    title: "Anyone can be targeted",
    body: "A person's face can be put into a fake video without their consent, then used to harass, humiliate or blackmail them. Schools are now dealing with students making explicit deepfakes of their classmates, and many U.S. states have passed new laws in response.",
    icon: (
      <>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5" />
      </>
    ),
    articles: [
      {
        source: "AP via PBS News",
        year: 2026,
        title: "Rise of deepfake cyberbullying poses a growing problem for schools",
        url: "https://www.pbs.org/newshour/education/ap-report-rise-of-deepfake-cyberbullying-poses-a-growing-problem-for-schools",
      },
      {
        source: "CBS News",
        year: 2023,
        title: "New Jersey high school students accused of making AI-generated pornographic images of classmates",
        url: "https://www.cbsnews.com/news/westfield-high-school-ai-pornographic-images-students/",
      },
    ],
  },
  {
    tab: "Doubt",
    title: "Real footage gets dismissed",
    body: "The more common fakes become, the easier it is to wave away the truth. Researchers call this the \"liar's dividend\": someone caught on camera can simply claim the video is AI. People have already tried this defense in court.",
    icon: (
      <>
        <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
        <circle cx="12" cy="12" r="3" />
        <path d="M4 4l16 16" />
      </>
    ),
    articles: [
      {
        source: "NPR",
        year: 2023,
        title: "People are trying to claim real videos are deepfakes. The courts are not amused",
        url: "https://www.npr.org/2023/05/08/1174132413/people-are-trying-to-claim-real-videos-are-deepfakes-the-courts-are-not-amused",
      },
    ],
  },
];

// One risk at a time with related news coverage. Advances on its own (paused on hover or focus);
// the progress bar's animation ending is what moves to the next slide.
export default function RiskCarousel() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const go = (i: number) => setIndex((i + risks.length) % risks.length);

  return (
    <div
      className="rounded-3xl bg-linear-to-br from-success/40 via-base-content/10 to-success/5 p-px"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="relative overflow-hidden rounded-[calc(1.5rem-1px)] bg-base-100/85 backdrop-blur">
        {/* Video-style scanlines and a slow sweeping beam */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "repeating-linear-gradient(to bottom, rgb(255 255 255 / 0.025) 0 1px, transparent 1px 4px)",
          }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 h-32 bg-linear-to-b from-transparent via-success/8 to-transparent motion-safe:animate-scan motion-reduce:hidden"
        />

        {/* Slides are stacked in one grid cell, so the panel keeps the height of the tallest */}
        <div className="relative grid">
          {risks.map((risk, i) => {
            const active = i === index;
            return (
              <div
                key={risk.tab}
                role="tabpanel"
                id={`risk-${i}`}
                aria-labelledby={`risk-tab-${i}`}
                inert={!active}
                className={`col-start-1 row-start-1 grid transition duration-500 ease-out motion-reduce:transition-none md:grid-cols-[1.4fr_1fr] ${
                  active ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-4 opacity-0"
                }`}
              >
                <div className="p-8">
                  <div className="flex items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-success/12 text-success">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="size-6"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={1.6}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        {risk.icon}
                      </svg>
                    </span>
                    <span className="text-sm font-semibold tabular-nums opacity-50">
                      {String(i + 1).padStart(2, "0")} / {String(risks.length).padStart(2, "0")}
                    </span>
                  </div>
                  <h3 className="mt-5 text-2xl font-bold">{risk.title}</h3>
                  <p className="mt-3 leading-relaxed opacity-70">{risk.body}</p>
                </div>

                <div className="flex flex-col gap-3 border-t border-base-content/10 bg-base-content/[0.03] p-8 md:border-t-0 md:border-l">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-success">In the news</p>
                  {risk.articles.map((article) => (
                    <a
                      key={article.url}
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group rounded-xl border border-base-content/10 bg-base-100/60 p-4 transition-colors hover:border-success/50"
                    >
                      <p className="text-xs opacity-50">
                        {article.source} · {article.year}
                      </p>
                      <p className="mt-1 font-medium leading-snug">
                        {article.title}
                        <span className="ml-1 inline-block text-success transition-transform group-hover:translate-x-0.5">
                          ↗
                        </span>
                      </p>
                    </a>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Tabs with an autoplay progress bar under the active one, plus prev/next */}
        <div className="relative flex items-center gap-2 border-t border-base-content/10 px-4 py-3">
          <div role="tablist" aria-label="Risks of AI-generated video" className="flex flex-1 flex-wrap gap-1">
            {risks.map((risk, i) => {
              const active = i === index;
              return (
                <button
                  key={risk.tab}
                  type="button"
                  role="tab"
                  id={`risk-tab-${i}`}
                  aria-selected={active}
                  aria-controls={`risk-${i}`}
                  onClick={() => go(i)}
                  className={`relative overflow-hidden rounded-lg px-3 py-2 text-sm transition-colors ${
                    active ? "bg-success/10 text-success" : "opacity-60 hover:opacity-100"
                  }`}
                >
                  {risk.tab}
                  {active && (
                    <span
                      key={index}
                      aria-hidden="true"
                      onAnimationEnd={() => go(index + 1)}
                      style={{ animationPlayState: paused ? "paused" : "running" }}
                      className="absolute bottom-0 left-0 h-0.5 w-full origin-left bg-success animate-carousel motion-reduce:hidden"
                    />
                  )}
                </button>
              );
            })}
          </div>
          <button type="button" aria-label="Previous" onClick={() => go(index - 1)} className="btn btn-ghost btn-sm btn-square">
            ‹
          </button>
          <button type="button" aria-label="Next" onClick={() => go(index + 1)} className="btn btn-ghost btn-sm btn-square">
            ›
          </button>
        </div>
      </div>
    </div>
  );
}
