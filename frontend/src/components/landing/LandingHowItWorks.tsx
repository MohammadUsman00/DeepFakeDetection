import React from "react";
import { Upload, ScanLine, BarChart3, FileJson } from "lucide-react";

const STEPS = [
  {
    n: "01",
    title: "Choose & upload",
    body: "Pick video or image, then send the file to the API. Limits follow your deployment configuration.",
    icon: Upload,
  },
  {
    n: "02",
    title: "Detect & crop faces",
    body: "Faces are localized (e.g. MTCNN) and cropped for scoring—largest face per frame for video.",
    icon: ScanLine,
  },
  {
    n: "03",
    title: "Score & aggregate",
    body: "EfficientNet-style logits feed a robust aggregation so a single headline score reflects the clip.",
    icon: BarChart3,
  },
  {
    n: "04",
    title: "Review results",
    body: "Inspect the authenticity bar, top suspicious frames, and optional Grad-CAM overlays.",
    icon: FileJson,
  },
] as const;

export function LandingHowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-24 border-b border-border/40 bg-muted/10">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-secondary">How it works</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">A straight-line pipeline</h2>
          <p className="mt-4 text-muted-foreground">
            From raw media to an explainable report—no guesswork about which stage you are in.
          </p>
        </div>

        <ol className="mt-14 grid gap-8 lg:grid-cols-2">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
            <li key={step.n} className="relative flex gap-5">
              <div className="flex shrink-0 flex-col items-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 text-sm font-bold text-primary ring-1 ring-white/10">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                {i < STEPS.length - 1 && (
                  <span className="mt-3 hidden w-px flex-1 bg-gradient-to-b from-border to-transparent lg:block" aria-hidden />
                )}
              </div>
              <div className="pb-2">
                <span className="font-mono text-[10px] font-semibold text-muted-foreground">{step.n}</span>
                <h3 className="mt-1 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
