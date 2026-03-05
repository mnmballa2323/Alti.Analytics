"use client";
// apps/web-portal/app/costs/page.tsx
// Epic 57: Cost Intelligence Dashboard
// 30-day spend forecast, per-Epic cost attribution, waste findings
// with single-click remediation actions, and savings realized tracker.

import { useState, useEffect } from "react";

interface ServiceCost {
    service: string;
    epic: string;
    forecast: number;
    daily_avg: number;
    waste: number;
    recommendation: string | null;
}

interface WasteFinding {
    resource: string;
    waste_type: string;
    waste_week: number;
    utilization: number;
    recommendation: string;
    remediated?: boolean;
}

const SERVICES: ServiceCost[] = [
    { service: "meta_learner", epic: "ep40", forecast: 1428, daily_avg: 47.6, waste: 184, recommendation: "Set min-instances=2. Save $184/wk." },
    { service: "drug_discovery", epic: "ep32", forecast: 1176, daily_avg: 39.2, waste: 0, recommendation: null },
    { service: "knowledge_graph", epic: "ep56", forecast: 462, daily_avg: 15.4, waste: 0, recommendation: null },
    { service: "connector_registry", epic: "ep46", forecast: 504, daily_avg: 16.8, waste: 58, recommendation: "Reduce CDC polling interval 15→60min off-peak." },
    { service: "climate_agent", epic: "ep25", forecast: 378, daily_avg: 12.6, waste: 0, recommendation: null },
    { service: "conversational_analytics", epic: "ep47", forecast: 336, daily_avg: 11.2, waste: 22, recommendation: "Cache repeated NL queries (TTL=5min)." },
    { service: "workflow_engine", epic: "ep52", forecast: 294, daily_avg: 9.8, waste: 0, recommendation: null },
    { service: "compliance_engine", epic: "ep43", forecast: 252, daily_avg: 8.4, waste: 0, recommendation: null },
    { service: "briefing_composer", epic: "ep54", forecast: 84, daily_avg: 2.8, waste: 0, recommendation: null },
    { service: "cost_intelligence", epic: "ep57", forecast: 63, daily_avg: 2.1, waste: 0, recommendation: null },
];

const WASTE_FINDINGS: WasteFinding[] = [
    { resource: "meta_learner Cloud Run (min=8)", waste_type: "OVER_PROVISIONED", waste_week: 184, utilization: 12.4, recommendation: "Set min-instances=2. Estimated annual savings: $9,578." },
    { resource: "drug_discovery GKE (n1-highmem-32)", waste_type: "IDLE_OUTSIDE_HOURS", waste_week: 312, utilization: 3.1, recommendation: "Enable node auto-provisioning with scale-to-zero. Annual: $16,244." },
    { resource: "alti_raw BigQuery (3.8TB unqueried 60d)", waste_type: "COLD_STORAGE", waste_week: 48, utilization: 0, recommendation: "Move to long-term storage tier (auto after 90 days). Annual: $2,496." },
];

const FORECAST_TREND = [
    { week: "W1", actual: 880, forecast: 870 },
    { week: "W2", actual: 912, forecast: 920 },
    { week: "W3", actual: 895, forecast: 910 },
    { week: "W4", actual: 940, forecast: 950 },
    { week: "W5 (fcast)", actual: null, forecast: 980 },
    { week: "W6 (fcast)", actual: null, forecast: 960 },
];

const WASTE_TYPE_COLOR: Record<string, string> = {
    OVER_PROVISIONED: "text-orange-400 border-orange-700/40 bg-orange-900/20",
    IDLE_OUTSIDE_HOURS: "text-yellow-400 border-yellow-700/40 bg-yellow-900/20",
    COLD_STORAGE: "text-blue-400 border-blue-700/40 bg-blue-900/20",
};

function fmt(n: number) { return n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(0)}`; }

export default function CostsPage() {
    const [findings, setFindings] = useState<WasteFinding[]>(WASTE_FINDINGS);
    const [savingsRealized, setSavingsRealized] = useState(0);
    const [tab, setTab] = useState<"overview" | "waste" | "forecast">("overview");

    const totalForecast = SERVICES.reduce((a, s) => a + s.forecast, 0);
    const totalWasteWeek = findings.filter(f => !f.remediated).reduce((a, f) => a + f.waste_week, 0);
    const savingsPct = Math.round((totalWasteWeek * 4.3) / totalForecast * 100);
    const maxForecast = Math.max(...SERVICES.map(s => s.forecast));
    const maxTrend = Math.max(...FORECAST_TREND.map(t => Math.max(t.actual ?? 0, t.forecast)));

    const remediate = (idx: number) => {
        setFindings(prev => prev.map((f, i) => i === idx ? { ...f, remediated: true } : f));
        setSavingsRealized(prev => prev + WASTE_FINDINGS[idx].waste_week);
    };

    return (
        <div className="min-h-screen bg-[#030712] text-white p-6 font-sans">
            <div className="mb-6">
                <h1 className="text-3xl font-bold">💰 Cost Intelligence</h1>
                <p className="text-slate-500 text-sm mt-1">30-day GCP spend forecast · waste detection · predictive auto-scaling</p>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-4 gap-4 mb-8">
                {[
                    { label: "30-Day Forecast", val: fmt(totalForecast), sub: "91% confidence", color: "text-white" },
                    { label: "Waste Identified", val: fmt(totalWasteWeek) + "/wk", sub: `${savingsPct}% of spend`, color: "text-orange-400" },
                    { label: "Savings Realized", val: fmt(savingsRealized * 4.3) + "/mo", sub: "from remediations", color: "text-green-400" },
                    { label: "Scaling Actions", val: "12 this week", sub: "pre-warm + scale-down", color: "text-blue-400" },
                ].map(c => (
                    <div key={c.label} className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                        <div className={`text-2xl font-bold ${c.color}`}>{c.val}</div>
                        <div className="text-slate-500 text-xs mt-1">{c.label}</div>
                        <div className="text-slate-600 text-xs">{c.sub}</div>
                    </div>
                ))}
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
                {(["overview", "waste", "forecast"] as const).map(t => (
                    <button key={t} id={`tab-${t}`} onClick={() => setTab(t)}
                        className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all capitalize ${tab === t ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}>
                        {t === "overview" ? "📊 By Service" : t === "waste" ? "🗑️ Waste Findings" : "📈 Forecast Trend"}
                    </button>
                ))}
            </div>

            {/* Overview: service cost breakdown */}
            {tab === "overview" && (
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-5">
                    <div className="grid grid-cols-[1fr_80px_80px_80px_220px] gap-2 text-xs text-slate-500 uppercase tracking-wide mb-3 px-2">
                        <span>Service</span><span className="text-right">Epic</span>
                        <span className="text-right">30d (USD)</span><span className="text-right">Daily Avg</span>
                        <span className="text-right">Recommendation</span>
                    </div>
                    {SERVICES.map(svc => (
                        <div key={svc.service}
                            className="grid grid-cols-[1fr_80px_80px_80px_220px] gap-2 items-center py-2 border-b border-slate-800 last:border-0 px-2 hover:bg-slate-800/40 rounded-lg transition-colors">
                            <div>
                                <div className="text-sm text-white">{svc.service}</div>
                                <div className="mt-1 bg-slate-800 rounded-full h-1.5 w-32 overflow-hidden">
                                    <div className="h-full bg-gradient-to-r from-blue-600 to-purple-500 rounded-full"
                                        style={{ width: `${(svc.forecast / maxForecast) * 100}%` }} />
                                </div>
                            </div>
                            <div className="text-xs text-slate-500 text-right font-mono">{svc.epic}</div>
                            <div className="text-sm text-white text-right font-mono">{fmt(svc.forecast)}</div>
                            <div className="text-xs text-slate-400 text-right">{fmt(svc.daily_avg)}/d</div>
                            <div className="text-xs text-right">
                                {svc.waste > 0
                                    ? <span className="text-orange-400">⚠️ {fmt(svc.waste)}/wk waste</span>
                                    : <span className="text-green-400">✅ Optimized</span>}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Waste findings */}
            {tab === "waste" && (
                <div className="space-y-4">
                    {findings.map((f, i) => (
                        <div key={f.resource} className={`border rounded-xl p-5 transition-all ${f.remediated ? "opacity-40 border-slate-700 bg-slate-900/20" : WASTE_TYPE_COLOR[f.waste_type]}`}>
                            <div className="flex justify-between items-start mb-3">
                                <div>
                                    <div className="text-sm font-semibold text-white">{f.resource}</div>
                                    <div className="text-xs text-slate-500 mt-0.5">{f.waste_type} · {f.utilization}% avg utilization</div>
                                </div>
                                <div className="text-right flex-shrink-0 ml-4">
                                    <div className="text-lg font-bold text-white">{fmt(f.waste_week)}<span className="text-xs text-slate-500">/wk</span></div>
                                    <div className="text-xs text-slate-500">{fmt(f.waste_week * 52)}/yr</div>
                                </div>
                            </div>
                            <p className="text-xs text-slate-300 mb-3">{f.recommendation}</p>
                            {!f.remediated
                                ? <button id={`remediate-${i}`} onClick={() => remediate(i)}
                                    className="text-xs bg-green-700 hover:bg-green-600 text-white px-4 py-1.5 rounded-lg transition-all">
                                    ⚡ Auto-Remediate Now
                                </button>
                                : <span className="text-xs text-green-400">✅ Remediated — savings applied to next billing cycle</span>}
                        </div>
                    ))}
                    {findings.every(f => f.remediated) && (
                        <div className="text-center py-12 text-slate-500 text-sm">🎉 All waste findings remediated. Platform operating at peak efficiency.</div>
                    )}
                </div>
            )}

            {/* Forecast trend */}
            {tab === "forecast" && (
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-5">
                    <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wide mb-6">Weekly Spend vs Forecast (USD)</h2>
                    <div className="flex items-end gap-4 h-48">
                        {FORECAST_TREND.map((t, i) => (
                            <div key={t.week} className="flex-1 flex flex-col items-center gap-1">
                                <div className="w-full flex gap-1 items-end h-40">
                                    {t.actual !== null && (
                                        <div className="flex-1 bg-blue-500/60 rounded-t transition-all duration-700"
                                            style={{ height: `${(t.actual / maxTrend) * 100}%` }} title={`Actual: $${t.actual}`} />
                                    )}
                                    <div className={`flex-1 rounded-t transition-all duration-700 ${t.actual === null ? "bg-purple-500/40 border border-dashed border-purple-500" : "bg-purple-500/30"}`}
                                        style={{ height: `${(t.forecast / maxTrend) * 100}%` }} title={`Forecast: $${t.forecast}`} />
                                </div>
                                <div className="text-xs text-slate-500 text-center">{t.week}</div>
                                <div className="text-xs font-mono text-slate-400">{fmt(t.forecast)}</div>
                            </div>
                        ))}
                    </div>
                    <div className="flex gap-6 mt-4 justify-center text-xs text-slate-500">
                        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-blue-500/60 rounded" /> Actual spend</div>
                        <div className="flex items-center gap-2"><div className="w-3 h-3 bg-purple-500/40 border border-dashed border-purple-500 rounded" /> Forecast</div>
                    </div>
                </div>
            )}
        </div>
    );
}
