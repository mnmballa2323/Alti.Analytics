"use client";
// apps/web-portal/app/studio/page.tsx
// Epic 51: No-Code Intelligence Studio
// Drag-and-drop dashboard builder for non-technical users.
// Pre-built widget marketplace + proactive Gemini insight push.

import { useState } from "react";

// ── Widget Marketplace ──────────────────────────────────────────────
const WIDGET_LIBRARY = [
    { id: "churn_risk", icon: "📉", label: "Churn Risk Feed", desc: "Top 20 at-risk accounts + LTV", color: "from-red-900/50 to-red-800/30", border: "border-red-700/40" },
    { id: "revenue_forecast", icon: "📈", label: "Revenue Forecast", desc: "12-month ML projection", color: "from-green-900/50 to-green-800/30", border: "border-green-700/40" },
    { id: "anomaly_feed", icon: "🚨", label: "Anomaly Alert Feed", desc: "Real-time data anomalies", color: "from-orange-900/50 to-orange-800/30", border: "border-orange-700/40" },
    { id: "kpi_summary", icon: "🎯", label: "KPI Summary Card", desc: "Custom metric with trend", color: "from-blue-900/50 to-blue-800/30", border: "border-blue-700/40" },
    { id: "nl_query", icon: "💬", label: "Ask Anything", desc: "Embedded NL query widget", color: "from-purple-900/50 to-purple-800/30", border: "border-purple-700/40" },
    { id: "compliance_score", icon: "🛡️", label: "Compliance Score", desc: "Live posture for 9 frameworks", color: "from-cyan-900/50 to-cyan-800/30", border: "border-cyan-700/40" },
    { id: "data_sources", icon: "🔌", label: "Connected Sources", desc: "Connector health status", color: "from-teal-900/50 to-teal-800/30", border: "border-teal-700/40" },
    { id: "model_card", icon: "🔎", label: "Model Explainability", desc: "SHAP top drivers for model", color: "from-violet-900/50 to-violet-800/30", border: "border-violet-700/40" },
];

// ── Proactive Insights (Gemini push) ───────────────────────────────
const PROACTIVE_INSIGHTS = [
    { id: 1, severity: "high", icon: "🔴", title: "Churn spike detected", body: "Customer churn probability for the Manufacturing segment rose 14% in the last 24h — 8 accounts now at critical risk.", action: "View accounts", ts: "2 min ago" },
    { id: 2, severity: "medium", icon: "🟡", title: "Revenue forecast revised", body: "Q2 projection updated to $48.2M (+6% vs. last model). Primary driver: enterprise expansion from Acme Corp cohort.", action: "View forecast", ts: "18 min ago" },
    { id: 3, severity: "low", icon: "🟢", title: "Data quality score improved", body: "Snowflake connector data quality rose from 91.2% to 97.4% after last night's schema migration.", action: "View report", ts: "2h ago" },
];

type WidgetDef = typeof WIDGET_LIBRARY[0];

function Widget({ def, onRemove }: { def: WidgetDef; onRemove: () => void }) {
    const DATA: Record<string, React.ReactNode> = {
        churn_risk: <div className="space-y-1">{["CUST-0021", "CUST-0089", "CUST-0142"].map((c, i) => (<div key={c} className="flex justify-between text-xs"><span className="text-slate-400">{c}</span><span className="text-red-400">{(0.94 - i * 0.06).toFixed(2)}</span></div>))}</div>,
        revenue_forecast: <div className="flex items-end gap-1 h-12">{[40, 55, 48, 62, 58, 70, 65, 80].map((v, i) => (<div key={i} className="flex-1 bg-green-500/60 rounded-t" style={{ height: `${v}%` }} />))}</div>,
        anomaly_feed: <div className="space-y-1 text-xs">{["Spike in null values · stripe_charges", "Schema drift · snowflake.orders"].map(a => (<div key={a} className="text-orange-300 truncate">⚠️ {a}</div>))}</div>,
        kpi_summary: <div className="text-center"><div className="text-3xl font-bold text-white">$8.4M</div><div className="text-xs text-green-400 mt-1">↑ 18% vs last month</div></div>,
        nl_query: <input className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500" placeholder="Ask your data anything..." />,
        compliance_score: <div className="flex gap-1">{[98, 97, 100, 99, 100].map((s, i) => (<div key={i} className="flex-1 text-center text-xs"><div className="text-green-400 font-bold">{s}</div><div className="text-slate-600 text-[9px]">fw{i + 1}</div></div>))}</div>,
        data_sources: <div className="space-y-1 text-xs">{[["Salesforce", "🟢"], ["Snowflake", "🟢"], ["HubSpot", "🟡"]].map(([s, d]) => (<div key={s} className="flex justify-between"><span className="text-slate-400">{s}</span><span>{d}</span></div>))}</div>,
        model_card: <div className="space-y-1 text-xs">{[["days_since_login", "+0.41"], ["support_tickets", "+0.28"], ["nps_score", "-0.19"]].map(([f, v]) => (<div key={f} className="flex justify-between"><span className="text-slate-400 truncate">{f}</span><span className={Number(v) > 0 ? "text-red-400" : "text-green-400"}>{v}</span></div>))}</div>,
    };

    return (
        <div className={`bg-gradient-to-br ${def.color} border ${def.border} rounded-xl p-4 group relative`}>
            <div className="flex justify-between items-start mb-3">
                <div>
                    <span className="text-lg">{def.icon}</span>
                    <span className="text-sm font-semibold text-white ml-2">{def.label}</span>
                </div>
                <button id={`remove-${def.id}`} onClick={onRemove}
                    className="text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all text-xs">✕</button>
            </div>
            <div>{DATA[def.id] ?? <div className="text-slate-500 text-xs">Loading...</div>}</div>
        </div>
    );
}

export default function StudioPage() {
    const [canvas, setCanvas] = useState<WidgetDef[]>([WIDGET_LIBRARY[0], WIDGET_LIBRARY[1], WIDGET_LIBRARY[2], WIDGET_LIBRARY[3]]);
    const [dragId, setDragId] = useState<string | null>(null);
    const [tab, setTab] = useState<"canvas" | "insights">("canvas");

    const addWidget = (def: WidgetDef) => { if (!canvas.find(w => w.id === def.id)) setCanvas(c => [...c, def]); };
    const removeWidget = (id: string) => setCanvas(c => c.filter(w => w.id !== id));

    return (
        <div className="min-h-screen bg-[#030712] text-white flex font-sans overflow-hidden">
            {/* Sidebar: Widget Library */}
            <aside className="w-64 border-r border-slate-800 p-4 flex-shrink-0">
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Widget Library</div>
                <div className="space-y-2">
                    {WIDGET_LIBRARY.map(def => (
                        <button id={`add-widget-${def.id}`} key={def.id} onClick={() => addWidget(def)}
                            draggable onDragStart={() => setDragId(def.id)}
                            className={`w-full text-left p-3 rounded-xl border ${def.border} bg-gradient-to-r ${def.color} hover:scale-[1.02] transition-all`}>
                            <div className="text-sm font-semibold text-white">{def.icon} {def.label}</div>
                            <div className="text-xs text-slate-400 mt-0.5">{def.desc}</div>
                        </button>
                    ))}
                </div>
            </aside>

            {/* Main area */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Toolbar */}
                <div className="border-b border-slate-800 px-6 py-3 flex items-center justify-between">
                    <div className="flex gap-2">
                        {(["canvas", "insights"] as const).map(t => (
                            <button key={t} id={`tab-${t}`} onClick={() => setTab(t)}
                                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${tab === t ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}>
                                {t === "canvas" ? "🎨 Dashboard" : "✨ Insights"}
                            </button>
                        ))}
                    </div>
                    <div className="flex gap-2">
                        <button id="export-pdf" className="text-xs text-slate-400 hover:text-white border border-slate-700 px-3 py-1.5 rounded-lg transition-all">📄 Export PDF</button>
                        <button id="share-btn" className="text-xs text-white bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded-lg transition-all">🔗 Share</button>
                    </div>
                </div>

                {/* Canvas or Insights */}
                <div className="flex-1 overflow-y-auto p-6">
                    {tab === "canvas" ? (
                        <>
                            <p className="text-slate-600 text-xs mb-4">Drag widgets from the left panel or click + to add. Drop anywhere to reorder.</p>
                            <div className="grid grid-cols-2 gap-4">
                                {canvas.map(def => <Widget key={def.id} def={def} onRemove={() => removeWidget(def.id)} />)}
                                {canvas.length === 0 && (
                                    <div className="col-span-2 h-64 border-2 border-dashed border-slate-700 rounded-xl flex items-center justify-center text-slate-600 text-sm">
                                        + Add widgets from the library on the left
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="space-y-4 max-w-2xl">
                            <p className="text-sm text-slate-500">Gemini is watching your data streams 24/7. Here's what it found:</p>
                            {PROACTIVE_INSIGHTS.map(ins => (
                                <div key={ins.id} className={`border rounded-xl p-5 ${ins.severity === "high" ? "border-red-700/40 bg-red-900/20" : ins.severity === "medium" ? "border-yellow-700/40 bg-yellow-900/20" : "border-green-700/40 bg-green-900/20"}`}>
                                    <div className="flex justify-between items-start mb-2">
                                        <span className="font-semibold text-white text-sm">{ins.icon} {ins.title}</span>
                                        <span className="text-slate-600 text-xs">{ins.ts}</span>
                                    </div>
                                    <p className="text-slate-300 text-sm">{ins.body}</p>
                                    <button id={`insight-action-${ins.id}`} className="mt-3 text-xs text-blue-400 hover:text-blue-300 transition-colors">{ins.action} →</button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
