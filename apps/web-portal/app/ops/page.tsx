"use client";
// apps/web-portal/app/ops/page.tsx
// Epic 50: Unified Observability Operations Dashboard
// Real-time SLO status, latency heatmap, incident feed, and
// automated runbooks for the full Alti.Analytics platform fleet.

import { useState, useEffect } from "react";

interface ServiceHealth {
    name: string; p99: number; sloTarget: number;
    errorPct: number; rps: number; status: "OK" | "BURNING" | "BREACHED";
}

interface Incident {
    id: string; sev: "SEV1" | "SEV2" | "SEV3"; service: string; title: string; age: string;
}

const generate = (): ServiceHealth[] => [
    { name: "conversational_analytics", p99: 820, sloTarget: 2000, errorPct: 0.12, rps: 142, status: "OK" },
    { name: "nl_to_sql", p99: 940, sloTarget: 2000, errorPct: 0.08, rps: 88, status: "OK" },
    { name: "compliance_engine", p99: 380, sloTarget: 1000, errorPct: 0.02, rps: 210, status: "OK" },
    { name: "meta_learner", p99: 4200, sloTarget: 5000, errorPct: 0.44, rps: 12, status: "BURNING" },
    { name: "connector_registry", p99: 28400, sloTarget: 30000, errorPct: 1.1, rps: 55, status: "BURNING" },
    { name: "explainability_engine", p99: 430, sloTarget: 500, errorPct: 0.31, rps: 390, status: "OK" },
    { name: "climate_agent", p99: 5800, sloTarget: 5000, errorPct: 0.62, rps: 4, status: "BREACHED" },
    { name: "drug_discovery", p99: 420, sloTarget: 500, errorPct: 0.11, rps: 7, status: "OK" },
    { name: "tenant_manager", p99: 310, sloTarget: 2000, errorPct: 0.01, rps: 290, status: "OK" },
    { name: "reactor_twin", p99: 4100, sloTarget: 5000, errorPct: 0.05, rps: 2, status: "OK" },
    { name: "ocean_intel", p99: 3900, sloTarget: 5000, errorPct: 0.22, rps: 6, status: "OK" },
    { name: "insurance_engine", p99: 440, sloTarget: 500, errorPct: 0.09, rps: 63, status: "OK" },
];

const INCIDENTS: Incident[] = [
    { id: "INC-A4F2B9", sev: "SEV2", service: "climate_agent", title: "p99 5800ms > SLO 5000ms", age: "3m ago" },
    { id: "INC-C7D1E3", sev: "SEV3", service: "connector_registry", title: "Error rate 1.1% near budget", age: "11m ago" },
];

const SEV_COLOR: Record<string, string> = {
    SEV1: "bg-red-500/20 text-red-300 border-red-500/40",
    SEV2: "bg-orange-500/20 text-orange-300 border-orange-500/40",
    SEV3: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
};

const STATUS_DOT: Record<string, string> = {
    OK: "bg-green-400", BURNING: "bg-yellow-400 animate-pulse", BREACHED: "bg-red-500 animate-pulse"
};

export default function OpsPage() {
    const [services, setServices] = useState<ServiceHealth[]>(generate());
    const [selected, setSelected] = useState<ServiceHealth | null>(null);

    useEffect(() => {
        const iv = setInterval(() => setServices(generate()), 5000);
        return () => clearInterval(iv);
    }, []);

    const ok = services.filter(s => s.status === "OK").length;
    const burning = services.filter(s => s.status === "BURNING").length;
    const breached = services.filter(s => s.status === "BREACHED").length;
    const avgP99 = Math.round(services.reduce((a, s) => a + s.p99, 0) / services.length);

    return (
        <div className="min-h-screen bg-[#030712] text-white p-6 font-mono">
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-white">📡 Operations Center</h1>
                <p className="text-slate-500 text-sm mt-1">Real-time SLO status · {services.length} services monitored · refreshes every 5s</p>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-4 mb-8">
                {[
                    { label: "Healthy", val: ok, color: "text-green-400" },
                    { label: "Burning", val: burning, color: "text-yellow-400" },
                    { label: "Breached", val: breached, color: "text-red-400" },
                    { label: "Avg p99", val: `${avgP99}ms`, color: "text-blue-400" },
                ].map(c => (
                    <div key={c.label} className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                        <div className={`text-2xl font-bold ${c.color}`}>{c.val}</div>
                        <div className="text-slate-500 text-xs mt-1">{c.label}</div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Service heatmap */}
                <div className="col-span-2 bg-slate-900 border border-slate-700 rounded-xl p-5">
                    <h2 className="text-sm font-bold text-slate-400 mb-4 uppercase tracking-wide">Service SLO Heatmap</h2>
                    <div className="space-y-2">
                        {services.map(svc => {
                            const pct = Math.min(100, (svc.p99 / svc.sloTarget) * 100);
                            const barColor = svc.status === "BREACHED" ? "from-red-500 to-red-700"
                                : svc.status === "BURNING" ? "from-yellow-500 to-orange-500"
                                    : "from-green-500 to-emerald-600";
                            return (
                                <button id={`svc-${svc.name}`} key={svc.name}
                                    onClick={() => setSelected(svc === selected ? null : svc)}
                                    className={`w-full flex items-center gap-3 text-xs rounded-lg px-3 py-2 transition-all ${selected?.name === svc.name ? "bg-slate-800" : "hover:bg-slate-800/50"}`}>
                                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[svc.status]}`} />
                                    <span className="text-slate-400 w-44 text-left truncate">{svc.name}</span>
                                    <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                                        <div className={`h-full bg-gradient-to-r ${barColor} transition-all duration-500`} style={{ width: `${pct}%` }} />
                                    </div>
                                    <span className="text-slate-500 w-16 text-right">{svc.p99}ms</span>
                                    <span className={`w-12 text-right ${svc.errorPct > 1 ? "text-red-400" : "text-slate-500"}`}>{svc.errorPct}%</span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Right panel: incidents + detail */}
                <div className="space-y-4">
                    {/* Active Incidents */}
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-5">
                        <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wide mb-3">Active Incidents</h2>
                        {INCIDENTS.map(inc => (
                            <div key={inc.id} className={`border rounded-lg p-3 mb-2 text-xs ${SEV_COLOR[inc.sev]}`}>
                                <div className="font-bold">{inc.sev} — {inc.service}</div>
                                <div className="text-slate-400 mt-0.5">{inc.title}</div>
                                <div className="text-slate-500 mt-1 flex justify-between">
                                    <span>{inc.id}</span><span>{inc.age}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Selected service detail */}
                    {selected && (
                        <div className="bg-slate-900 border border-blue-500/30 rounded-xl p-5 text-xs">
                            <div className="font-bold text-blue-300 mb-3">{selected.name}</div>
                            {[
                                ["p99 Latency", `${selected.p99}ms`, "SLO: " + selected.sloTarget + "ms"],
                                ["Error Rate", `${selected.errorPct}%`, "Budget: 1%"],
                                ["Throughput", `${selected.rps} rps`, ""],
                                ["SLO Status", selected.status, ""],
                            ].map(([label, val, sub]) => (
                                <div key={label} className="flex justify-between py-1 border-b border-slate-800 last:border-0">
                                    <span className="text-slate-500">{label}</span>
                                    <span className={`font-bold ${selected.status === "BREACHED" && label === "SLO Status" ? "text-red-400" : "text-white"}`}>
                                        {val} <span className="text-slate-600 font-normal">{sub}</span>
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
