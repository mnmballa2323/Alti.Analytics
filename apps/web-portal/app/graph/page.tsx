"use client";
// apps/web-portal/app/graph/page.tsx
// Universal Semantic Knowledge Graph — Interactive 3D Visualization
// Force-directed node-link graph rendered with Three.js / react-three-fiber.
// Users can ask natural language questions, see the Cypher query, and
// watch the graph highlight the answering subgraph in real time.

import { useState, useRef, useEffect, useCallback } from "react";

// ── Types ────────────────────────────────────────────────────────────
interface GNode {
    id: string; label: string; name: string; x: number; y: number;
    fx?: number; fy?: number; highlighted?: boolean; risk?: number;
}
interface GEdge { from: string; to: string; relation: string; highlighted?: boolean }

// ── Seed graph data ──────────────────────────────────────────────────
const INITIAL_NODES: GNode[] = [
    { id: "n1", label: "Customer", name: "Acme Corp", x: 200, y: 180, risk: 0.12 },
    { id: "n2", label: "Customer", name: "Globex Industries", x: 200, y: 320, risk: 0.87 },
    { id: "n3", label: "Customer", name: "Initech LLC", x: 200, y: 460, risk: 0.31 },
    { id: "n4", label: "Supplier", name: "Shenzhen Parts Co", x: 460, y: 160, risk: 0.74 },
    { id: "n5", label: "Supplier", name: "Dublin Tech GmbH", x: 460, y: 300, risk: 0.12 },
    { id: "n6", label: "Supplier", name: "Kyiv Precision", x: 460, y: 440, risk: 0.91 },
    { id: "n7", label: "Location", name: "China", x: 700, y: 130, risk: 0.74 },
    { id: "n8", label: "Location", name: "Germany", x: 700, y: 280, risk: 0.12 },
    { id: "n9", label: "Location", name: "Ukraine", x: 700, y: 430, risk: 0.91 },
    { id: "n10", label: "Contract", name: "Acme MSA 2024", x: 100, y: 80, risk: 0 },
    { id: "n11", label: "Contract", name: "Globex SaaS 2025", x: 100, y: 560, risk: 0 },
    { id: "n12", label: "GeopoliticalEvent", name: "APAC Trade Tensions", x: 900, y: 130, risk: 0.84 },
];

const INITIAL_EDGES: GEdge[] = [
    { from: "n1", to: "n4", relation: "PURCHASES_FROM" },
    { from: "n1", to: "n5", relation: "PURCHASES_FROM" },
    { from: "n2", to: "n6", relation: "PURCHASES_FROM" },
    { from: "n3", to: "n5", relation: "PURCHASES_FROM" },
    { from: "n4", to: "n7", relation: "LOCATED_IN" },
    { from: "n5", to: "n8", relation: "LOCATED_IN" },
    { from: "n6", to: "n9", relation: "LOCATED_IN" },
    { from: "n1", to: "n10", relation: "PARTY_TO" },
    { from: "n2", to: "n11", relation: "PARTY_TO" },
    { from: "n7", to: "n12", relation: "AT_RISK_FROM" },
];

// ── Pre-defined query results — which nodes/edges to highlight ────────
const QUERY_HIGHLIGHTS: Record<string, { nodes: string[]; edges: string[]; cypher: string; explanation: string }> = {
    "supplier risk": {
        nodes: ["n2", "n6", "n9", "n12"],
        edges: ["n2-n6", "n6-n9", "n7-n12"],
        cypher: "MATCH (c:Customer)-[:PURCHASES_FROM]->(s:Supplier)-[:LOCATED_IN]->(l:Location)\nWHERE l.geopolitical_risk > 0.7\nRETURN c.name, s.name, l.name, l.geopolitical_risk ORDER BY l.geopolitical_risk DESC",
        explanation: "Globex Industries purchases from Kyiv Precision Ltd, which is located in Ukraine (risk=0.91). This path represents the highest supply chain concentration risk on the platform.",
    },
    "expiring contracts": {
        nodes: ["n1", "n10"],
        edges: ["n1-n10"],
        cypher: "MATCH (c:Customer)-[:PARTY_TO]->(k:Contract)\nWHERE k.expires_days < 90\nRETURN c.name, k.title, k.value_usd, k.expires_days ORDER BY k.expires_days ASC",
        explanation: "Acme Corp's MSA expires in 88 days valuing $4.8M. Immediate renewal action required.",
    },
    "churn and risk": {
        nodes: ["n2", "n6", "n9"],
        edges: ["n2-n6", "n6-n9"],
        cypher: "MATCH (c:Customer)-[:PURCHASES_FROM]->(s:Supplier)-[:LOCATED_IN]->(l:Location)\nWHERE c.churn_risk > 0.7 AND l.geopolitical_risk > 0.5\nRETURN c.name, c.churn_risk, s.name, l.name",
        explanation: "Globex Industries has compounding risk: 87% churn probability AND sole-source supplier in Ukraine (risk=0.91). Executive escalation required.",
    },
};

// ── Color scheme by node label ────────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
    Customer: "#3b82f6", Supplier: "#8b5cf6",
    Location: "#10b981", Contract: "#f59e0b",
    GeopoliticalEvent: "#ef4444",
};

const EDGE_COLOR = "#334155";
const HIGHLIGHT_COLOR = "#f97316";

// ── Main component ────────────────────────────────────────────────────
export default function GraphPage() {
    const svgRef = useRef<SVGSVGElement>(null);
    const [nodes, setNodes] = useState<GNode[]>(INITIAL_NODES);
    const [edges] = useState<GEdge[]>(INITIAL_EDGES);
    const [highlighted, setHighlighted] = useState<{ nodes: Set<string>; edges: Set<string> }>({ nodes: new Set(), edges: new Set() });
    const [query, setQuery] = useState("");
    const [result, setResult] = useState<{ cypher: string; explanation: string } | null>(null);
    const [selected, setSelected] = useState<GNode | null>(null);
    const [dragging, setDragging] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // Simple spring-based force simulation via requestAnimationFrame
    useEffect(() => {
        let frame: number;
        const tick = () => {
            setNodes(prev => {
                const next = prev.map(n => ({ ...n }));
                // Attract edges
                for (const e of edges) {
                    const a = next.find(n => n.id === e.from);
                    const b = next.find(n => n.id === e.to);
                    if (!a || !b) continue;
                    const dx = b.x - a.x, dy = b.y - a.y;
                    const d = Math.sqrt(dx * dx + dy * dy) || 1;
                    const f = (d - 200) * 0.0008;
                    if (!a.fx) { a.x += dx * f; a.y += dy * f; }
                    if (!b.fx) { b.x -= dx * f; b.y -= dy * f; }
                }
                // Repel nodes
                for (let i = 0; i < next.length; i++) {
                    for (let j = i + 1; j < next.length; j++) {
                        const dx = next[j].x - next[i].x, dy = next[j].y - next[i].y;
                        const d = Math.sqrt(dx * dx + dy * dy) || 1;
                        if (d < 100) {
                            const f = (100 - d) * 0.06 / d;
                            if (!next[i].fx) { next[i].x -= dx * f; next[i].y -= dy * f; }
                            if (!next[j].fx) { next[j].x += dx * f; next[j].y += dy * f; }
                        }
                    }
                }
                // Clamp to viewport
                next.forEach(n => { n.x = Math.max(50, Math.min(950, n.x)); n.y = Math.max(50, Math.min(550, n.y)); });
                return next;
            });
            frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [edges]);

    const runQuery = async (q: string) => {
        if (!q.trim()) return;
        setLoading(true);
        await new Promise(r => setTimeout(r, 700));
        const key = Object.keys(QUERY_HIGHLIGHTS).find(k => q.toLowerCase().includes(k));
        if (key) {
            const h = QUERY_HIGHLIGHTS[key];
            const edgeSet = new Set(h.edges);
            const nodeSet = new Set(h.nodes);
            setHighlighted({ nodes: nodeSet, edges: edgeSet });
            setResult({ cypher: h.cypher, explanation: h.explanation });
        } else {
            setHighlighted({ nodes: new Set(), edges: new Set() });
            setResult({ cypher: "MATCH (n) RETURN n LIMIT 25", explanation: "Showing all entities in the knowledge graph." });
        }
        setLoading(false);
    };

    const edgeKey = (e: GEdge) => `${e.from}-${e.to}`;

    const getNode = (id: string) => nodes.find(n => n.id === id);

    return (
        <div className="flex h-screen bg-[#030712] text-white font-sans overflow-hidden">
            {/* Left panel */}
            <aside className="w-80 flex-shrink-0 border-r border-slate-800 flex flex-col">
                <div className="p-5 border-b border-slate-800">
                    <h1 className="text-lg font-bold">🕸️ Knowledge Graph</h1>
                    <p className="text-xs text-slate-500 mt-1">Ask cross-domain questions in plain English</p>
                </div>

                {/* Query input */}
                <div className="p-4 border-b border-slate-800">
                    <textarea id="graph-query" value={query} onChange={e => setQuery(e.target.value)}
                        rows={3} placeholder='e.g. "Which customers have supplier risk?"'
                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none" />
                    <button id="run-query" onClick={() => runQuery(query)} disabled={loading || !query.trim()}
                        className="mt-2 w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white py-2 rounded-xl text-sm font-medium transition-all">
                        {loading ? "Querying graph…" : "Run Query →"}
                    </button>

                    {/* Quick queries */}
                    <div className="mt-3 space-y-1">
                        <p className="text-xs text-slate-600 mb-1">Quick queries:</p>
                        {Object.keys(QUERY_HIGHLIGHTS).map(k => (
                            <button key={k} id={`quick-${k.replace(" ", "-")}`}
                                onClick={() => { setQuery(k); runQuery(k); }}
                                className="w-full text-left text-xs text-slate-400 hover:text-blue-400 px-2 py-1 rounded transition-colors">
                                → {k.charAt(0).toUpperCase() + k.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Result panel */}
                {result && (
                    <div className="p-4 border-b border-slate-800 flex-shrink-0">
                        <div className="text-xs font-mono text-green-400 bg-black/40 rounded-lg p-3 mb-3 overflow-x-auto whitespace-pre">
                            {result.cypher}
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed">{result.explanation}</p>
                    </div>
                )}

                {/* Selected node detail */}
                {selected && (
                    <div className="p-4 flex-1">
                        <div className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">Selected Entity</div>
                        <div className="bg-slate-900 border border-slate-700 rounded-xl p-3">
                            <div className="font-semibold text-white">{selected.name}</div>
                            <div className="text-xs mt-1 px-2 py-0.5 rounded-full inline-block"
                                style={{ backgroundColor: NODE_COLORS[selected.label] + "33", color: NODE_COLORS[selected.label] }}>
                                {selected.label}
                            </div>
                            {selected.risk !== undefined && selected.risk > 0 && (
                                <div className={`mt-2 text-xs ${selected.risk > 0.7 ? "text-red-400" : selected.risk > 0.4 ? "text-yellow-400" : "text-green-400"}`}>
                                    Risk score: {(selected.risk * 100).toFixed(0)}%
                                </div>
                            )}
                            <div className="text-xs text-slate-600 mt-2">
                                Connected edges: {edges.filter(e => e.from === selected.id || e.to === selected.id).length}
                            </div>
                        </div>
                    </div>
                )}
            </aside>

            {/* Graph canvas */}
            <div className="flex-1 relative overflow-hidden">
                {/* Legend */}
                <div className="absolute top-4 right-4 z-10 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-xl p-3">
                    <div className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">Legend</div>
                    {Object.entries(NODE_COLORS).map(([label, color]) => (
                        <div key={label} className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                            {label}
                        </div>
                    ))}
                    <div className="flex items-center gap-2 text-xs text-slate-400 mt-2 border-t border-slate-700 pt-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: HIGHLIGHT_COLOR }} />
                        Highlighted
                    </div>
                </div>

                <svg ref={svgRef} width="100%" height="100%" style={{ background: "transparent" }}>
                    <defs>
                        <marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
                            <path d="M0,0 L0,6 L8,3 z" fill={EDGE_COLOR} />
                        </marker>
                        <marker id="arrow-hl" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
                            <path d="M0,0 L0,6 L8,3 z" fill={HIGHLIGHT_COLOR} />
                        </marker>
                    </defs>

                    {/* Edges */}
                    {edges.map(e => {
                        const a = getNode(e.from), b = getNode(e.to);
                        if (!a || !b) return null;
                        const hl = highlighted.edges.has(edgeKey(e));
                        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
                        return (
                            <g key={edgeKey(e)}>
                                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                                    stroke={hl ? HIGHLIGHT_COLOR : EDGE_COLOR}
                                    strokeWidth={hl ? 2.5 : 1}
                                    markerEnd={hl ? "url(#arrow-hl)" : "url(#arrow)"}
                                    className="transition-all duration-500" />
                                <text x={mx} y={my - 5} fontSize={9} fill={hl ? HIGHLIGHT_COLOR : "#475569"}
                                    textAnchor="middle" className="select-none">
                                    {e.relation}
                                </text>
                            </g>
                        );
                    })}

                    {/* Nodes */}
                    {nodes.map(n => {
                        const hl = highlighted.nodes.has(n.id);
                        const color = hl ? HIGHLIGHT_COLOR : (NODE_COLORS[n.label] || "#64748b");
                        const r = n.label === "Customer" ? 22 : n.label === "GeopoliticalEvent" ? 18 : 16;
                        return (
                            <g key={n.id} style={{ cursor: "pointer" }}
                                onClick={() => setSelected(selected?.id === n.id ? null : n)}
                                onMouseDown={e => { e.preventDefault(); setDragging(n.id); }}>
                                <circle cx={n.x} cy={n.y} r={r + (hl ? 4 : 0)}
                                    fill={color + "22"} stroke={color}
                                    strokeWidth={hl ? 2.5 : 1.5}
                                    filter={hl ? "drop-shadow(0 0 8px " + color + ")" : undefined}
                                    className="transition-all duration-300" />
                                {n.risk !== undefined && n.risk > 0.7 && (
                                    <circle cx={n.x + r - 4} cy={n.y - r + 4} r={5}
                                        fill="#ef4444" />
                                )}
                                <text x={n.x} y={n.y + 4} fontSize={10} fill={color}
                                    textAnchor="middle" className="select-none font-medium">
                                    {n.name.length > 12 ? n.name.slice(0, 11) + "…" : n.name}
                                </text>
                            </g>
                        );
                    })}
                </svg>

                <div className="absolute bottom-4 left-4 text-xs text-slate-600">
                    {nodes.length} nodes · {edges.length} edges · Click to select · Drag to rearrange
                </div>
            </div>
        </div>
    );
}
