import React from "react";
import { AlertTriangle } from "lucide-react";

export function LandingDisclaimer() {
  return (
    <section className="border-b border-border/40 bg-amber-500/[0.06]">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="flex gap-4 rounded-2xl border border-amber-500/25 bg-amber-500/5 p-6 sm:items-start">
          <AlertTriangle className="h-6 w-6 shrink-0 text-amber-400" aria-hidden />
          <div>
            <h2 className="text-lg font-semibold text-foreground">Important limitations</h2>
            <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-muted-foreground">
              <li>Optimized for face manipulation signals; other edits may not be surfaced.</li>
              <li>Grad-CAM shows where the model attended—not ground-truth causal proof of editing.</li>
              <li>Calibration can vary on out-of-domain content without domain-specific fine-tuning.</li>
              <li>Do not treat outputs as legal evidence without expert review and chain-of-custody processes.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
