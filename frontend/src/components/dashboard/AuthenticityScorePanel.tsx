"use client";

import React from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/cn";
import { Activity, AlertTriangle, Shield } from "lucide-react";

type Props = {
  finalScore: number | null | undefined;
  confidenceLabel?: string;
  lowConfidence?: boolean;
  framesUsed?: number | null;
  className?: string;
};

function scoreColor(pFake: number): string {
  if (pFake < 0.35) return "#10b981";
  if (pFake < 0.65) return "#f59e0b";
  return "#ef4444";
}

export function AuthenticityScorePanel({
  finalScore,
  confidenceLabel,
  lowConfidence,
  framesUsed,
  className,
}: Props) {
  const p = finalScore != null && !Number.isNaN(Number(finalScore)) ? Number(finalScore) : null;
  const pct = p != null ? Math.round(p * 1000) / 10 : null;
  const chartData = [{ name: "P(fake)", value: pct ?? 0 }];

  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-gradient-to-br from-card/90 to-muted/30 p-6 shadow-xl",
        className
      )}
    >
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Authenticity signal
          </p>
          <h3 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
            {confidenceLabel ?? "Result"}
          </h3>
          {lowConfidence && (
            <p className="mt-2 inline-flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              Low confidence — use as indicative only
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border/80 bg-background/50 px-4 py-3">
          {p != null && p >= 0.5 ? (
            <Activity className="h-8 w-8 text-destructive opacity-90" aria-hidden />
          ) : (
            <Shield className="h-8 w-8 text-primary opacity-90" aria-hidden />
          )}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Fake probability</p>
            <p className="text-3xl font-mono font-bold tabular-nums" style={{ color: p != null ? scoreColor(p) : "#94a3b8" }}>
              {pct != null ? `${pct}%` : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <XAxis type="number" domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} />
            <YAxis type="category" dataKey="name" width={56} tick={{ fill: "#64748b", fontSize: 10 }} hide />
            <Tooltip
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(v: number) => [`${v}%`, "P(fake)"]}
            />
            <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={28}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={p != null ? scoreColor(p) : "#475569"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {framesUsed != null && (
        <p className="mt-4 text-center text-[11px] text-muted-foreground">
          Aggregated over <span className="font-mono font-semibold text-foreground">{framesUsed}</span> face
          frames
        </p>
      )}
    </div>
  );
}
