"use client";
// apps/web-portal/app/chat/page.tsx
// Epic 47: Conversational Analytics Chat UI
// Business users ask questions in plain English and get live charts,
// SQL previews, executive narratives, and follow-up suggestions.

import { useState, useRef, useEffect } from "react";

interface Message {
    id: string;
    role: "user" | "assistant";
    text: string;
    sql?: string;
    chartType?: string;
    rows?: Record<string, unknown>[];
    narrative?: string;
    followUps?: string[];
    ms?: number;
}

const STARTER_QUESTIONS = [
    "Which customers are most likely to churn in the next 90 days?",
    "Show me revenue trends by month for the last year",
    "Break down our customer base by industry and ARR",
    "What is the conversion rate through our sales funnel?",
];

function BarChart({ rows }: { rows: Record<string, unknown>[] }) {
    if (!rows?.length) return null;
    const yKey = Object.keys(rows[0])[1];
    const xKey = Object.keys(rows[0])[0];
    const max = Math.max(...rows.map(r => Number(r[yKey]) || 0));
    return (
        <div className="mt-3 space-y-1">
            {rows.slice(0, 6).map((row, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="text-slate-400 w-28 truncate">{String(row[xKey])}</span>
                    <div className="flex-1 bg-slate-800 rounded-full h-4 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-700"
                            style={{ width: `${(Number(row[yKey]) / max) * 100}%` }}
                        />
                    </div>
                    <span className="text-slate-300 w-20 text-right">
                        {typeof row[yKey] === "number" && Number(row[yKey]) > 10000
                            ? `$${(Number(row[yKey]) / 1e6).toFixed(1)}M`
                            : String(row[yKey])}
                    </span>
                </div>
            ))}
        </div>
    );
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [showSql, setShowSql] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

    const sendQuestion = async (question: string) => {
        if (!question.trim() || loading) return;
        const userMsg: Message = { id: Date.now().toString(), role: "user", text: question };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        // Simulate engine response (production: POST /api/analytics/ask)
        await new Promise(r => setTimeout(r, 900 + Math.random() * 600));
        const isChurn = question.toLowerCase().includes("churn");
        const isRevenue = question.toLowerCase().includes("revenue");
        const response: Message = {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            text: "",
            sql: isChurn
                ? "SELECT customer_id, churn_probability, ltv_usd FROM alti_curated.churn_scores WHERE churn_probability > 0.7 ORDER BY ltv_usd DESC LIMIT 20"
                : "SELECT DATE_TRUNC(date, MONTH) AS month, SUM(revenue_usd) AS revenue FROM alti_curated.revenue_daily GROUP BY 1 ORDER BY 1 DESC LIMIT 12",
            chartType: isChurn ? "scatter" : "bar",
            rows: isChurn
                ? [1, 2, 3, 4].map(i => ({ customer_id: `CUST-00${i}`, ltv_usd: 280000 - i * 40000 }))
                : ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"].map(m => ({ month: m, revenue: 4_200_000 + Math.random() * 3_000_000 })),
            narrative: isChurn
                ? "⚡ 4 high-value accounts are at critical churn risk. The top at-risk customer has $280K LTV — immediate outreach is recommended. Protecting this cohort preserves an estimated $840K in ARR."
                : "📈 Revenue has grown for 5 consecutive months. Q1 2026 is tracking 18% ahead of Q1 2025, driven by enterprise expansion revenue from existing accounts.",
            followUps: isChurn
                ? ["Which CSM owns the highest-risk accounts?", "What features have churned customers stopped using?"]
                : ["How does this compare to our forecast?", "Which segments are driving growth?"],
            ms: Math.round(800 + Math.random() * 400),
        };
        setMessages(prev => [...prev, response]);
        setLoading(false);
    };

    return (
        <div className="flex flex-col h-screen bg-[#030712] text-white font-sans">
            {/* Header */}
            <div className="border-b border-slate-800 px-6 py-4 flex items-center gap-3">
                <span className="text-2xl">💬</span>
                <div>
                    <h1 className="font-bold text-white text-lg leading-tight">Conversational Analytics</h1>
                    <p className="text-slate-500 text-xs">Ask anything about your data — in plain English</p>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full gap-6">
                        <p className="text-slate-500 text-sm">Start with a question, or try one of these:</p>
                        <div className="grid grid-cols-2 gap-3 max-w-xl w-full">
                            {STARTER_QUESTIONS.map((q, i) => (
                                <button key={i} id={`starter-q-${i}`} onClick={() => sendQuestion(q)}
                                    className="text-left text-xs text-slate-300 bg-slate-900 border border-slate-700 hover:border-blue-500 rounded-xl p-3 transition-all">
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map(msg => (
                    <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        {msg.role === "user" ? (
                            <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl rounded-tr-sm max-w-lg text-sm">
                                {msg.text}
                            </div>
                        ) : (
                            <div className="max-w-2xl w-full space-y-3">
                                {/* Narrative */}
                                <div className="bg-slate-900 border border-slate-700 rounded-2xl rounded-tl-sm p-4">
                                    <p className="text-slate-200 text-sm leading-relaxed">{msg.narrative}</p>
                                    {msg.ms && <p className="text-slate-600 text-xs mt-2">⚡ {msg.ms}ms</p>}
                                </div>

                                {/* Chart */}
                                {msg.rows && <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="text-xs text-slate-500 uppercase tracking-wide">{msg.chartType} chart</span>
                                        <button id={`sql-toggle-${msg.id}`} onClick={() => setShowSql(showSql === msg.id ? null : msg.id ?? null)}
                                            className="text-xs text-blue-400 hover:text-blue-300">
                                            {showSql === msg.id ? "Hide SQL" : "View SQL"}
                                        </button>
                                    </div>
                                    {showSql === msg.id && (
                                        <pre className="text-xs text-green-400 bg-black/50 rounded-lg p-3 mb-3 overflow-x-auto">
                                            {msg.sql}
                                        </pre>
                                    )}
                                    <BarChart rows={msg.rows as Record<string, unknown>[]} />
                                </div>}

                                {/* Follow-ups */}
                                {msg.followUps && (
                                    <div className="flex gap-2 flex-wrap">
                                        {msg.followUps.map((q, i) => (
                                            <button key={i} id={`followup-${msg.id}-${i}`} onClick={() => sendQuestion(q)}
                                                className="text-xs text-slate-400 bg-slate-900 border border-slate-700 hover:border-blue-500 px-3 py-1.5 rounded-full transition-all">
                                                {q}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-slate-900 border border-slate-700 rounded-2xl px-5 py-3">
                            <div className="flex gap-1 items-center">
                                {[0, 1, 2].map(i => (
                                    <div key={i} className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                                        style={{ animationDelay: `${i * 0.15}s` }} />
                                ))}
                            </div>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="border-t border-slate-800 px-6 py-4">
                <div className="flex gap-3 max-w-3xl mx-auto">
                    <input
                        id="chat-input"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && sendQuestion(input)}
                        placeholder="Ask anything about your data..."
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <button id="send-btn" onClick={() => sendQuestion(input)} disabled={!input.trim() || loading}
                        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-5 rounded-xl transition-all text-sm font-medium">
                        Ask →
                    </button>
                </div>
            </div>
        </div>
    );
}
