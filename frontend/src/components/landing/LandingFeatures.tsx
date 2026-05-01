import React from "react";
import { Eye, Film, Image as ImageIcon, ShieldCheck } from "lucide-react";

const CARDS = [
  {
    icon: Film,
    title: "Video & image",
    body: "Upload MP4/MOV or JPEG/PNG. Video runs are sampled over time with largest-face selection per frame.",
    accent: "text-primary",
  },
  {
    icon: Eye,
    title: "Transparent signals",
    body: "See a calibrated authenticity-style score plus per-frame uncertainty when the pipeline is less confident.",
    accent: "text-secondary",
  },
  {
    icon: ShieldCheck,
    title: "Account-aware jobs",
    body: "Signed-in users get jobs tied to their account with free-tier daily limits—ready for SaaS deployments.",
    accent: "text-primary",
  },
  {
    icon: ImageIcon,
    title: "Artifact delivery",
    body: "Heatmaps and summaries are fetched over HTTPS using bearer-authenticated API calls with account ownership checks.",
    accent: "text-secondary",
  },
] as const;

export function LandingFeatures() {
  return (
    <section id="features" className="scroll-mt-24 border-b border-border/40 bg-background">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-primary">Features</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Built for clarity, not black boxes</h2>
          <p className="mt-4 text-muted-foreground">
            Every step is designed so end users understand what was analyzed and how confident the system is.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {CARDS.map(({ icon: Icon, title, body, accent }) => (
            <article
              key={title}
              className="group rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-muted/20 p-6 shadow-lg transition hover:border-primary/30 hover:shadow-xl"
            >
              <Icon className={`h-9 w-9 ${accent}`} strokeWidth={1.5} aria-hidden />
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
