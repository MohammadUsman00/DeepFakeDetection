import React from "react";
import { Cpu, Layers, Zap } from "lucide-react";

const ITEMS = [
  { icon: Cpu, label: "CPU-friendly inference", sub: "Batch-scored face crops" },
  { icon: Layers, label: "Explainable overlays", sub: "Top-K Grad-CAM frames" },
  { icon: Zap, label: "Async jobs", sub: "Progress via REST + live channel" },
] as const;

export function LandingTrustStrip() {
  return (
    <section className="border-b border-border/40 bg-muted/20">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:grid-cols-3 sm:px-6">
        {ITEMS.map(({ icon: Icon, label, sub }) => (
          <div
            key={label}
            className="flex gap-4 rounded-2xl border border-border/50 bg-card/30 p-5 backdrop-blur-sm"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">{label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
