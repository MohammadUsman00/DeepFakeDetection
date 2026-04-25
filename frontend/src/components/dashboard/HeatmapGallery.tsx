"use client";

import React from "react";
import { Scan } from "lucide-react";
import { cn } from "@/lib/cn";
import { authHeaders } from "@/lib/auth";

export type HeatmapItem = {
  frame_index: number;
  p_fake: number;
  heatmap_overlay_url?: string | null;
};

type Props = {
  items: HeatmapItem[];
  className?: string;
};

export function HeatmapGallery({ items, className }: Props) {
  const withUrls = items.filter((x) => x.heatmap_overlay_url);

  if (withUrls.length === 0) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/20 py-14 text-center",
          className
        )}
      >
        <Scan className="mb-3 h-10 w-10 text-muted-foreground/50" aria-hidden />
        <p className="text-sm font-medium text-muted-foreground">No Grad-CAM overlays for this run</p>
        <p className="mt-1 max-w-md text-xs text-muted-foreground/80">
          Explainability maps are generated for the top suspicious frames when the pipeline completes successfully.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2", className)}>
      {withUrls.map((h) => (
        <figure
          key={h.frame_index}
          className="overflow-hidden rounded-xl border border-border bg-muted/20 shadow-sm transition-shadow hover:shadow-md"
        >
          <HeatmapImage
            src={h.heatmap_overlay_url!}
            frameIndex={h.frame_index}
          />
          <figcaption className="flex items-center justify-between border-t border-border/60 bg-background/40 px-3 py-2 font-mono text-[11px] text-muted-foreground">
            <span>Frame {h.frame_index}</span>
            <span className="text-foreground/90">p_fake {(h.p_fake * 100).toFixed(1)}%</span>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

function HeatmapImage({ src, frameIndex }: { src: string; frameIndex: number }) {
  const [objectUrl, setObjectUrl] = React.useState<string>("");
  const [loadError, setLoadError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    let createdUrl = "";
    const controller = new AbortController();

    const load = async () => {
      try {
        setLoadError(null);
        const res = await fetch(src, {
          headers: { ...authHeaders() },
          signal: controller.signal,
        });
        if (!res.ok) {
          throw new Error(`artifact ${res.status}`);
        }
        const blob = await res.blob();
        if (!active) return;
        createdUrl = URL.createObjectURL(blob);
        setObjectUrl(createdUrl);
      } catch {
        if (active) setLoadError("Unable to load overlay");
      }
    };

    load();

    return () => {
      active = false;
      controller.abort();
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [src]);

  if (loadError) {
    return (
      <div className="flex aspect-video w-full items-center justify-center bg-muted/30 text-xs text-muted-foreground">
        {loadError}
      </div>
    );
  }

  if (!objectUrl) {
    return (
      <div className="flex aspect-video w-full items-center justify-center bg-muted/30 text-xs text-muted-foreground">
        Loading frame {frameIndex}...
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={objectUrl}
      alt={`Grad-CAM overlay for frame ${frameIndex}`}
      className="aspect-video w-full object-cover"
      loading="lazy"
    />
  );
}
