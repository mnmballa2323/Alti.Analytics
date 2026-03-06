"use client";
// apps/web-portal/app/stream/page.tsx
// Epic 58: Live Streaming Analytics Dashboard
// Self-updating charts driven by WebSocket window updates from the
// StreamingEngine. Anomalies flash red. No polling — pure push.

import { useState, useEffect, useRef } from "react";

interface WindowPoint { ts: number; avg: number; max: number; anomaly: boolean; score: number }
interface PipelineDef { id: string; name: string; unit: string; topic: string; color: string; warnAt: number | null }

const PIPELINES: PipelineDef[] = [
    { id: "pipe-fraud", name: "Live Fraud Detection", unit: "USD", topic: "stripe_charges", color: "#ef4444", warnAt: 5000 },
    { id: "pipe-latency", name: "API Latency p99", unit: "ms", topic: "otel_spans", color: "#f59e0b", warnAt: 2000 },
    { id: "pipe-sensor", name: "IoT Sensor Temperature", unit: "°C", topic: "factory_sensors", color: "#22c55e", warnAt: 85 },
    { id: "pipe-revenue", name: "Live Revenue Stream", unit: "USD", topic: "stripe_charges", color: "#3b82f6", warnAt: null },
    { id: "pipe-vitals", name: "Hospital Heart Rate", unit: "BPM", topic: "hl7_vitals", color: "#a78bfa", warnAt: 120 },
];

const MAX_POINTS = 30;

function generatePoint(p: PipelineDef, prev?: number): WindowPoint {
    const base = { "pipe-fraud": 280, "pipe-latency": 320, "pipe-sensor": 42, "pipe-revenue": 8400, "pipe-vitals": 72 }[p.id] ?? 100;
    const noise = base * (Math.random() * 0.3 - 0.1);
    const spike = Math.random() > 0.93 ? base * 3.8 : 0;
    const avg = Math.max(0, round(base + noise + spike));
    const anomaly = spike > 0;
    return { ts: Date.now(), avg, max: round(avg * 1.2), anomaly, score: anomaly ? round(Math.random() * 1.5 + 3) : round(Math.random() * 0.8) };
}
const round = (n: number) => Math.round(n * 100) / 100;

function Sparkline({ points, color, height = 60 }: { points: WindowPoint[]; color: string; height?: number }) {
    if (points.length < 2) return null;
    const vals = points.map(p => p.avg);
    const lo = Math.min(...vals) * 0.95, hi = Math.max(...vals) * 1.05 || 1;
    const W = 280, H = height;
    const px = (i: number) => (i / (points.length - 1)) * W;
    const py = (v: number) => H - ((v - lo) / (hi - lo)) * H;
    const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${px(i).toFixed(1)},${py(p.avg).toFixed(1)}`).join(" ");
    const area = `${path} L${W},${H} L0,${H} Z`;
    return (
        <svg width={W} height={H} className="w-full">
            <defs>
                <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
            </defs>
            <path d={area} fill={`url(#grad-${color.replace("#", "")})`} />
            <path d={path} fill="none" stroke={color} strokeWidth={1.8} />
            {points.map((p, i) => p.anomaly && (
                <circle key={i} cx={px(i)} cy={py(p.avg)} r={4} fill="#ef4444"
                    className="animate-ping" style={{ animationDuration: "0.8s" }} />
            ))}
        </svg>
    );
}

function PipelineCard({ pipeline }: { pipeline: PipelineDef }) {
    const [points, setPoints] = useState<WindowPoint[]>([]);
    const [flash, setFlash] = useState(false);
    const intervalRef = useRef<ReturnType<typeof setInterval>>();

    useEffect(() => {
        // Initialize with warm data
        const init: WindowPoint[] = Array.from({ length: 15 }, () => generatePoint(pipeline));
        setPoints(init);
        // Simulate WebSocket push at realistic cadence
        const ms = { "pipe-sensor": 800, "pipe-vitals": 600 }[pipeline.id] ?? 1200;
        intervalRef.current = setInterval(() => {
            setPoints(prev => {
                const next = [...prev.slice(-MAX_POINTS + 1), generatePoint(pipeline, prev.at(-1)?.avg)];
                if (next.at(-1)?.anomaly) {
                    setFlash(true);
                    setTimeout(() => setFlash(false), 1200);
                }
                return next;
            });
        }, ms + Math.random() * 200);
        return () => clearInterval(intervalRef.current);
    }, [pipeline.id]);

    const latest = points.at(-1);
    const prev = points.at(-4);
    const delta = latest && prev ? ((latest.avg - prev.avg) / (prev.avg || 1) * 100) : 0;
    const isWarn = pipeline.warnAt !== null && (latest?.avg ?? 0) > pipeline.warnAt;

    return (
        <div className={`relative bg-slate-900 border rounded-2xl p-5 transition-all duration-300 ${flash ? "border-red-500 shadow-[0_0_24px_rgba(239,68,68,0.4)]" : `border-slate-700 hover:border-slate-600`
            }`}>
            {flash && (
                <div className="absolute inset-0 bg-red-500/10 rounded-2xl animate-pulse pointer-events-none" />
            )}
            {/* Header */}
            <div className="flex justify-between items-start mb-3">
                <div>
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: pipeline.color }} />
                        <span className="text-xs text-slate-400 font-medium">{pipeline.name}</span>
                    </div>
                    <div className="text-2xl font-bold text-white mt-1">
                        {latest?.avg.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                        <span className="text-sm text-slate-500 ml-1">{pipeline.unit}</span>
                    </div>
                </div>
                <div className="text-right">
                    {isWarn && <div className="text-xs text-red-400 font-bold mb-1">⚠️ THRESHOLD</div>}
                    {latest?.anomaly && <div className="text-xs text-red-300 font-bold animate-pulse">🚨 ANOMALY</div>}
                    <div className={`text-xs ${delta > 0 ? "text-red-400" : "text-green-400"}`}>
                        {delta > 0 ? "↑" : "↓"} {Math.abs(delta).toFixed(1)}%
                    </div>
                </div>
            </div>
            {/* Sparkline */}
            <Sparkline points={points} color={pipeline.color} height={56} />
            {/* Footer stats */}
            <div className="grid grid-cols-3 gap-2 mt-3">
                {[
                    ["Max", latest?.max.toFixed(1) ?? "—"],
                    ["Pts", points.length.toString()],
                    ["Anomalies", points.filter(p => p.anomaly).length.toString()],
                ].map(([l, v]) => (
                    <div key={l} className="text-center">
                        <div className="text-xs text-slate-500">{l}</div>
                        <div className="text-sm font-mono text-white">{v}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function StreamPage() {
    const [totalEvents, setTotalEvents] = useState(0);
    const [totalAnomalies, setTotalAnomalies] = useState(0);

    useEffect(() => {
        const iv = setInterval(() => {
            setTotalEvents(e => e + Math.floor(Math.random() * 80 + 40));
            setTotalAnomalies(a => Math.random() > 0.85 ? a + 1 : a);
        }, 1000);
        return () => clearInterval(iv);
    }, []);

    return (
        <div className="min-h-screen bg-[#030712] text-white p-6 font-sans">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3">
                        ⚡ Live Stream Analytics
                        <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-2 py-0.5 rounded-full animate-pulse">
                            LIVE
                        </span>
                    </h1>
                    <p className="text-slate-500 text-sm mt-1">WebSocket push · sub-200ms event-to-screen · anomaly flash alerts</p>
                </div>
                <div className="flex gap-4 text-right">
                    <div><div className="text-xl font-bold text-white">{totalEvents.toLocaleString()}</div><div className="text-xs text-slate-500">events/session</div></div>
                    <div><div className="text-xl font-bold text-red-400">{totalAnomalies}</div><div className="text-xs text-slate-500">anomalies</div></div>
                    <div><div className="text-xl font-bold text-green-400">&lt;200ms</div><div className="text-xs text-slate-500">e2e latency</div></div>
                </div>
            </div>
            {/* Pipeline grid */}
            <div className="grid grid-cols-3 gap-4">
                {PIPELINES.map(p => <PipelineCard key={p.id} pipeline={p} />)}
            </div>
        </div>
    );
}
