"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { io } from "socket.io-client";
import {
  Shield,
  Upload,
  FileVideo,
  FileImage,
  Search,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Cpu,
  Scan,
  ArrowRight,
} from "lucide-react";
import { WorkflowRail } from "@/components/dashboard/WorkflowRail";
import { AuthenticityScorePanel } from "@/components/dashboard/AuthenticityScorePanel";
import { HeatmapGallery } from "@/components/dashboard/HeatmapGallery";
import { LandingNav } from "@/components/landing/LandingNav";
import { LandingHero } from "@/components/landing/LandingHero";
import { LandingTrustStrip } from "@/components/landing/LandingTrustStrip";
import { LandingFeatures } from "@/components/landing/LandingFeatures";
import { LandingHowItWorks } from "@/components/landing/LandingHowItWorks";
import { LandingTech } from "@/components/landing/LandingTech";
import { LandingDisclaimer } from "@/components/landing/LandingDisclaimer";
import { LandingFaq } from "@/components/landing/LandingFaq";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { cn } from "@/lib/cn";
import { authHeaders, clearToken, getToken, isAuthRequired } from "@/lib/auth";

type ForensicMode = "VIDEO" | "IMAGE" | null;
type InvestigationStage = "SELECTION" | "UPLOAD" | "ANALYSIS" | "RESULT";

interface BackendResultSummary {
  final_score: number | null;
  confidence_label?: string;
  low_confidence?: boolean;
  low_confidence_reason?: string | null;
  frames_used_for_score?: number;
  model_version?: string;
  pipeline_version?: string;
  score_interpretation?: string;
  top_k_suspicious?: Array<{
    frame_index: number;
    p_fake: number;
    heatmap_overlay_url?: string | null;
  }>;
}

interface AnalysisResult extends BackendResultSummary {
  is_fake: boolean;
  confidence: number;
  label: string;
}

function scrollToAnalyzerSection() {
  document.getElementById("analyzer")?.scrollIntoView({ behavior: "smooth" });
}

export default function ForensicDashboard() {
  const [mode, setMode] = useState<ForensicMode>(null);
  const [stage, setStage] = useState<InvestigationStage>("SELECTION");
  const [file, setFile] = useState<File | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState("");
  const [jobStage, setJobStage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [logs, setLogs] = useState<string[]>(["Session started — ready for upload"]);
  const [error, setError] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [needLogin, setNeedLogin] = useState(false);

  const logsRef = useRef<HTMLDivElement>(null);
  const jobIdRef = useRef<string | null>(null);
  jobIdRef.current = jobId;

  const addLog = useCallback((msg: string) => {
    const ts = new Date().toLocaleTimeString("en-GB", { hour12: false });
    setLogs((prev) => [...prev, `[${ts}] ${msg}`].slice(-80));
  }, []);

  useEffect(() => {
    if (!isAuthRequired()) {
      setNeedLogin(false);
      setAuthReady(true);
      return;
    }
    setNeedLogin(!getToken());
    setAuthReady(true);
  }, []);

  useEffect(() => {
    const socketInstance = io({
      path: "/api/socket.io",
      transports: ["websocket", "polling"],
      reconnectionAttempts: 5,
    });
    socketInstance.on("connect", () => addLog("Live channel connected"));
    socketInstance.on("connect_error", () => addLog("Live channel unavailable — using HTTP polling"));
    socketInstance.on("analysis_update", (data: { job_id?: string; progress?: number; state?: string }) => {
      if (data.job_id && data.job_id !== jobIdRef.current) return;
      if (typeof data.progress === "number") setAnalysisProgress(data.progress);
      if (data.state) setJobState(data.state);
    });
    return () => {
      socketInstance.disconnect();
    };
  }, [addLog]);

  useEffect(() => {
    if (stage !== "ANALYSIS" || !jobId) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const res = await fetch(`/api/results/${jobId}`, { headers: { ...authHeaders() } });
        if (!res.ok) {
          if (res.status === 404) {
            setError("Job not found.");
            setStage("UPLOAD");
          }
          return;
        }
        const data = await res.json();
        if (cancelled) return;

        setJobState(data.state ?? "");
        setJobStage(data.stage ?? "");
        setAnalysisProgress(typeof data.progress_percent === "number" ? data.progress_percent : 0);

        if (data.state === "COMPLETED" && data.result) {
          const r = data.result as BackendResultSummary;
          const fs = r.final_score;
          const is_fake = fs !== null && fs !== undefined ? fs >= 0.5 : false;
          const confidence = fs !== null && fs !== undefined ? fs * 100 : 0;
          setResult({
            ...r,
            is_fake,
            confidence,
            label: r.confidence_label || (is_fake ? "Elevated manipulation signal" : "Consistent with authentic capture"),
          });
          setStage("RESULT");
          addLog("Analysis complete — results ready");
          return;
        }

        if (data.state === "FAILED") {
          const msg = data.error?.message || data.error?.error_code || "Analysis failed";
          setError(msg);
          setStage("UPLOAD");
          addLog(`Failed: ${msg}`);
        }
      } catch {
        setError("Cannot reach API. Is the backend running? (see README)");
      }
    };

    tick();
    const id = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [stage, jobId]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  const handleModeSelect = (m: ForensicMode) => {
    setMode(m);
    setStage("UPLOAD");
    addLog(`Mode: ${m}`);
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      addLog(`File: ${f.name} (${(f.size / 1024 / 1024).toFixed(2)} MB)`);
    }
  };

  const startAnalysis = async () => {
    if (!file || !mode) return;
    setStage("ANALYSIS");
    setError(null);
    setAnalysisProgress(0);
    setJobState("");
    setJobStage("");
    setResult(null);
    addLog("Submitting job…");

    const fd = new FormData();
    fd.append("file", file);
    const endpoint = mode === "VIDEO" ? "/api/analyze-video" : "/api/analyze-image";

    try {
      const res = await fetch(endpoint, { method: "POST", headers: { ...authHeaders() }, body: fd });
      if (!res.ok) throw new Error("upload failed");
      const data = await res.json();
      setJobId(data.job_id);
      addLog(`Job ${data.job_id} — polling /api/results/…`);
    } catch {
      setError("Upload failed. Check API and Next.js rewrites (BACKEND_PROXY_URL).");
      setStage("UPLOAD");
      addLog("Upload error");
    }
  };

  const reset = () => {
    setMode(null);
    setStage("SELECTION");
    setFile(null);
    setResult(null);
    setAnalysisProgress(0);
    setJobId(null);
    setJobState("");
    setJobStage("");
    setError(null);
    addLog("New session");
  };

  const signOut = () => {
    clearToken();
    setNeedLogin(isAuthRequired());
    reset();
  };

  const analyzerCard = (
    <div className="rounded-2xl border border-border/80 bg-card/30 shadow-2xl backdrop-blur-xl">
      <div className="border-b border-border/60 px-4 py-4 sm:px-6">
        <WorkflowRail stage={stage} />
      </div>

      <div className="border-b border-border/60 px-6 py-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-muted-foreground">Workspace</p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight">
              {stage === "SELECTION" && "Choose input type"}
              {stage === "UPLOAD" && "Upload media"}
              {stage === "ANALYSIS" && "Processing"}
              {stage === "RESULT" && "Results"}
            </h2>
          </div>
          <button
            type="button"
            onClick={reset}
            className="self-start rounded-lg border border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:bg-muted/50 hover:text-foreground sm:self-auto"
          >
            Reset session
          </button>
        </div>
      </div>

      <div className="p-6 sm:p-8">
        {error && (
          <div
            role="alert"
            className="mb-8 flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground"
          >
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {stage === "SELECTION" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => handleModeSelect("VIDEO")}
              className="group flex flex-col items-start gap-4 rounded-2xl border border-border bg-muted/20 p-6 text-left transition hover:border-primary/50 hover:bg-primary/5"
            >
              <FileVideo className="h-10 w-10 text-primary transition group-hover:scale-105" />
              <div>
                <h3 className="font-semibold">Video</h3>
                <p className="mt-1 text-sm text-muted-foreground">MP4 or MOV · sampled frames, largest face per frame</p>
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                Continue <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleModeSelect("IMAGE")}
              className="group flex flex-col items-start gap-4 rounded-2xl border border-border bg-muted/20 p-6 text-left transition hover:border-secondary/50 hover:bg-secondary/5"
            >
              <FileImage className="h-10 w-10 text-secondary transition group-hover:scale-105" />
              <div>
                <h3 className="font-semibold">Image</h3>
                <p className="mt-1 text-sm text-muted-foreground">JPEG or PNG · single face analysis</p>
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-secondary">
                Continue <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </button>
          </div>
        )}

        {stage === "UPLOAD" && (
          <div className="mx-auto max-w-xl">
            <button
              type="button"
              onClick={() => setStage("SELECTION")}
              className="mb-6 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              ← Change type
            </button>
            <div className="relative">
              <input
                type="file"
                onChange={handleFile}
                className="absolute inset-0 z-10 cursor-pointer opacity-0"
                accept={mode === "VIDEO" ? "video/mp4,video/quicktime" : "image/jpeg,image/png"}
              />
              <div
                className={cn(
                  "flex min-h-[200px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border bg-muted/10 p-8 transition hover:border-primary/40"
                )}
              >
                {file ? (
                  <>
                    <CheckCircle2 className="mb-3 h-12 w-12 text-primary" />
                    <p className="text-center font-medium">{file.name}</p>
                    <p className="mt-1 text-sm text-muted-foreground">Ready to analyze</p>
                  </>
                ) : (
                  <>
                    <Upload className="mb-3 h-12 w-12 text-muted-foreground" />
                    <p className="font-medium">Drop a file here or click to browse</p>
                    <p className="mt-1 text-sm text-muted-foreground">Max size per server configuration</p>
                  </>
                )}
              </div>
            </div>
            {file && (
              <button
                type="button"
                onClick={startAnalysis}
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3.5 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90"
              >
                <Search className="h-4 w-4" />
                Start analysis
              </button>
            )}
          </div>
        )}

        {stage === "ANALYSIS" && (
          <div className="mx-auto max-w-md text-center">
            <div className="relative mx-auto mb-8 h-20 w-20">
              <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
              <div
                className="absolute inset-0 animate-spin rounded-full border-2 border-primary border-t-transparent"
                style={{ animationDuration: "0.9s" }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <Scan className="h-8 w-8 text-primary" />
              </div>
            </div>
            <p className="text-sm font-medium text-foreground">Running pipeline</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {jobState || "—"} · {jobStage || "—"}
            </p>
            <div className="mx-auto mt-8 h-2 max-w-xs overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, analysisProgress))}%` }}
              />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold tabular-nums text-primary">{analysisProgress}%</p>
            <p className="mt-2 text-xs text-muted-foreground">Live progress from GET /api/results</p>
          </div>
        )}

        {stage === "RESULT" && result && (
          <div className="space-y-10">
            <AuthenticityScorePanel
              finalScore={result.final_score}
              confidenceLabel={result.confidence_label}
              lowConfidence={result.low_confidence}
              framesUsed={result.frames_used_for_score}
            />

            <section>
              <h3 className="mb-4 text-sm font-semibold tracking-tight">Explainability · top frames</h3>
              <HeatmapGallery items={result.top_k_suspicious ?? []} />
            </section>

            <section className="rounded-xl border border-border/60 bg-muted/10 p-5">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Run metadata</h4>
              <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Model version</dt>
                  <dd className="font-mono text-foreground">{result.model_version ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Pipeline version</dt>
                  <dd className="font-mono text-foreground">{result.pipeline_version ?? "—"}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-muted-foreground">Interpretation</dt>
                  <dd className="text-foreground/90">{result.score_interpretation ?? "—"}</dd>
                </div>
              </dl>
            </section>

            <button
              type="button"
              onClick={reset}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-border py-3 text-sm font-medium text-muted-foreground transition hover:bg-muted/30 hover:text-foreground"
            >
              <RefreshCw className="h-4 w-4" />
              New analysis
            </button>
          </div>
        )}
      </div>

      <div className="border-t border-border/60 bg-muted/10 px-4 py-3">
        <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          <Cpu className="h-3 w-3" />
          Event log
        </div>
        <div
          ref={logsRef}
          className="mt-2 max-h-24 overflow-y-auto font-mono text-[10px] leading-relaxed text-muted-foreground/90"
        >
          {logs.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      </div>
    </div>
  );

  const signInGate = (
    <div className="rounded-2xl border border-dashed border-primary/40 bg-gradient-to-br from-primary/10 via-card/40 to-secondary/10 p-10 text-center shadow-xl backdrop-blur-md">
      <Shield className="mx-auto h-14 w-14 text-primary" />
      <h2 className="mt-6 text-2xl font-semibold tracking-tight">Sign in to use the analyzer</h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
        This deployment requires an account. Register for the free tier (daily limits apply), then return here to upload
        video or images.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/login"
          className="inline-flex min-w-[140px] items-center justify-center rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="inline-flex min-w-[140px] items-center justify-center rounded-xl border border-border bg-muted/30 px-6 py-3 text-sm font-semibold transition hover:bg-muted/50"
        >
          Create account
        </Link>
      </div>
    </div>
  );

  if (!authReady) {
    return <div className="min-h-screen bg-background" aria-busy="true" />;
  }

  return (
    <div className="relative min-h-screen bg-background bg-app-mesh text-foreground">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(16,185,129,0.12),transparent)]" />

      <LandingNav onSignOut={signOut} />

      <LandingHero onScrollToAnalyzer={scrollToAnalyzerSection} />

      <LandingTrustStrip />
      <LandingFeatures />
      <LandingHowItWorks />
      <LandingTech />

      <section id="analyzer" className="scroll-mt-28 border-b border-border/40">
        <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:py-20">
          <div className="mb-8 max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-primary">Analyzer</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Run a screening</h2>
            <p className="mt-3 text-base text-muted-foreground">
              Upload media below. Progress updates come from <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">/api/results</code>{" "}
              with optional live updates over Socket.IO.
            </p>
          </div>

          {needLogin ? signInGate : analyzerCard}
        </div>
      </section>

      <LandingDisclaimer />
      <LandingFaq />
      <LandingFooter />
    </div>
  );
}
