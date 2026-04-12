import React from "react";

const STACK = [
  {
    name: "EfficientNet-B0",
    role: "Core classifier backbone for face crops—tunable weights via INFER_MODEL_WEIGHTS_PATH.",
  },
  {
    name: "Face pipeline",
    role: "MTCNN (with optional fallbacks) to find faces before inference.",
  },
  {
    name: "Grad-CAM",
    role: "Optional attention maps on the top-K highest-uncertainty frames for quick visual review.",
  },
  {
    name: "FastAPI + Celery",
    role: "REST API for uploads and results; background workers for heavy video runs when configured.",
  },
] as const;

export function LandingTech() {
  return (
    <section id="technology" className="scroll-mt-24 border-b border-border/40 bg-background">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-primary">Technology</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Stack you can reason about</h2>
          <p className="mt-4 text-muted-foreground">
            Components are standard, swappable, and documented in the repository—suitable for thesis demos and product pilots.
          </p>
        </div>

        <ul className="mt-12 divide-y divide-border/60 rounded-2xl border border-border/60 bg-card/40">
          {STACK.map((row) => (
            <li key={row.name} className="flex flex-col gap-1 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
              <span className="font-semibold text-foreground">{row.name}</span>
              <span className="max-w-xl text-sm text-muted-foreground">{row.role}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
