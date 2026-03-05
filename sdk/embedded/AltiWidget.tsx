// sdk/embedded/AltiWidget.tsx
/**
 * Epic 53: Embedded Analytics & White-Label SDK
 * Drop-in React component for embedding Alti intelligence widgets
 * into any SaaS product. Supports full white-labeling via theme prop.
 * 
 * Install: npm install @alti/embed-sdk
 * 
 * Usage:
 *   import { AltiWidget } from "@alti/embed-sdk";
 *   <AltiWidget widgetId="churn_risk" token={jwtToken} theme={myBrandTheme} />
 */

import React, { useEffect, useRef, useState } from "react";

// ── Theme System ─────────────────────────────────────────────────────
export interface AltiTheme {
    primaryColor: string;
    backgroundColor: string;
    textColor: string;
    borderRadius: string;
    fontFamily: string;
    accentColor: string;
}

const DEFAULT_THEME: AltiTheme = {
    primaryColor: "#3b82f6",
    backgroundColor: "#0f172a",
    textColor: "#f1f5f9",
    borderRadius: "12px",
    fontFamily: "Inter, system-ui, sans-serif",
    accentColor: "#8b5cf6",
};

// ── Widget Registry ──────────────────────────────────────────────────
type WidgetId =
    | "churn_risk"
    | "revenue_forecast"
    | "anomaly_feed"
    | "kpi_card"
    | "nl_query"
    | "compliance_score";

interface WidgetData {
    churn_risk: { accounts: { id: string; name: string; risk: number }[] };
    revenue_forecast: { months: { month: string; actual?: number; forecast: number }[] };
    anomaly_feed: { anomalies: { table: string; score: number; detected: string }[] };
    kpi_card: { label: string; value: string; trend: string; change_pct: number };
    nl_query: { placeholder: string };
    compliance_score: { frameworks: { name: string; score: number }[] };
}

// ── AltiWidget Component ─────────────────────────────────────────────
export interface AltiWidgetProps {
    /** Widget type from the Alti catalog */
    widgetId: WidgetId;
    /** JWT scoped to this tenant + widget — generated in embed configurator */
    token: string;
    /** Optional Alti API base URL (for self-hosted deployments) */
    baseUrl?: string;
    /** Optional theme override for white-labeling */
    theme?: Partial<AltiTheme>;
    /** Callback fired when a user interacts with the widget */
    onEvent?: (event: { type: string; payload: unknown }) => void;
    className?: string;
    style?: React.CSSProperties;
}

export const AltiWidget: React.FC<AltiWidgetProps> = ({
    widgetId, token, baseUrl = "https://api.alti.ai", theme = {}, onEvent, className, style
}) => {
    const t = { ...DEFAULT_THEME, ...theme };
    const [data, setData] = useState<unknown>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Fetch widget data from Alti API with scoped JWT
        const fetchData = async () => {
            try {
                // Production: GET {baseUrl}/v1/embed/{widgetId} with Authorization: Bearer {token}
                await new Promise(r => setTimeout(r, 600));
                const mockData: Record<string, unknown> = {
                    churn_risk: { accounts: [{ id: "C001", name: "Acme Corp", risk: 0.87 }, { id: "C002", name: "Globex Inc", risk: 0.81 }] },
                    revenue_forecast: { months: [{ month: "Apr", forecast: 8_400_000 }, { month: "May", forecast: 9_100_000 }, { month: "Jun", forecast: 9_800_000 }] },
                    anomaly_feed: { anomalies: [{ table: "stripe_charges", score: 0.94, detected: "2 min ago" }] },
                    kpi_card: { label: "Monthly Revenue", value: "$8.4M", trend: "↑", change_pct: 18 },
                    compliance_score: { frameworks: [{ name: "HIPAA", score: 98 }, { name: "SOC 2", score: 97 }, { name: "GDPR", score: 99 }] },
                };
                setData(mockData[widgetId] ?? {});
            } catch (e) {
                setError("Failed to load widget data.");
            } finally { setLoading(false); }
        };
        fetchData();
    }, [widgetId, token, baseUrl]);

    const emit = (type: string, payload: unknown) => onEvent?.({ type, payload });

    const containerStyle: React.CSSProperties = {
        backgroundColor: t.backgroundColor, color: t.textColor,
        borderRadius: t.borderRadius, fontFamily: t.fontFamily,
        border: `1px solid ${t.primaryColor}22`, padding: "16px",
        minWidth: "280px", ...style
    };

    if (loading) return (
        <div style={containerStyle} className={className}>
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                {[0, 1, 2].map(i => (
                    <div key={i} style={{
                        width: 8, height: 8, borderRadius: "50%",
                        backgroundColor: t.primaryColor, animation: `bounce 1s ${i * 0.15}s infinite`
                    }} />
                ))}
            </div>
        </div>
    );

    if (error) return (
        <div style={{ ...containerStyle, borderColor: "#ef4444" }} className={className}>
            <span style={{ color: "#ef4444", fontSize: 13 }}>⚠️ {error}</span>
        </div>
    );

    // ── Widget Renderers ───────────────────────────────────────────────
    const renderChurnRisk = (d: WidgetData["churn_risk"]) => (
        <>
            <div style={{ fontSize: 12, fontWeight: 700, color: t.primaryColor, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                🔴 Churn Risk Feed
            </div>
            {d.accounts.map(acc => (
                <div key={acc.id} onClick={() => emit("account_click", acc)}
                    style={{
                        display: "flex", justifyContent: "space-between", padding: "6px 0",
                        borderBottom: `1px solid ${t.textColor}11`, cursor: "pointer", fontSize: 13
                    }}>
                    <span style={{ color: t.textColor }}>{acc.name}</span>
                    <span style={{ color: acc.risk > 0.85 ? "#ef4444" : "#f59e0b", fontWeight: 700 }}>
                        {(acc.risk * 100).toFixed(0)}%
                    </span>
                </div>
            ))}
        </>
    );

    const renderRevenueForecast = (d: WidgetData["revenue_forecast"]) => {
        const max = Math.max(...d.months.map(m => m.forecast));
        return (
            <>
                <div style={{ fontSize: 12, fontWeight: 700, color: t.primaryColor, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    📈 Revenue Forecast
                </div>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 60 }}>
                    {d.months.map(m => (
                        <div key={m.month} style={{ flex: 1, textAlign: "center" }}>
                            <div style={{
                                height: `${(m.forecast / max) * 100}%`, minHeight: 4,
                                background: `linear-gradient(to top, ${t.primaryColor}, ${t.accentColor})`,
                                borderRadius: "4px 4px 0 0"
                            }} />
                            <div style={{ fontSize: 10, color: t.textColor + "88", marginTop: 4 }}>{m.month}</div>
                        </div>
                    ))}
                </div>
            </>
        );
    };

    const renderKpiCard = (d: WidgetData["kpi_card"]) => (
        <div style={{ textAlign: "center", padding: "8px 0" }}>
            <div style={{ fontSize: 11, color: t.textColor + "66", textTransform: "uppercase", letterSpacing: "0.08em" }}>{d.label}</div>
            <div style={{ fontSize: 32, fontWeight: 800, color: t.textColor, margin: "8px 0 4px" }}>{d.value}</div>
            <div style={{ fontSize: 13, color: d.change_pct > 0 ? "#22c55e" : "#ef4444" }}>
                {d.trend} {Math.abs(d.change_pct)}% vs last month
            </div>
        </div>
    );

    const renderCompliance = (d: WidgetData["compliance_score"]) => (
        <>
            <div style={{ fontSize: 12, fontWeight: 700, color: t.primaryColor, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                🛡️ Compliance
            </div>
            {d.frameworks.map(fw => (
                <div key={fw.name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: t.textColor + "88", width: 60 }}>{fw.name}</span>
                    <div style={{ flex: 1, background: t.textColor + "11", borderRadius: 4, height: 6 }}>
                        <div style={{ width: `${fw.score}%`, height: "100%", background: t.primaryColor, borderRadius: 4 }} />
                    </div>
                    <span style={{ fontSize: 12, color: "#22c55e", fontWeight: 700 }}>{fw.score}%</span>
                </div>
            ))}
        </>
    );

    return (
        <div id={`alti-widget-${widgetId}`} style={containerStyle} className={className}>
            {widgetId === "churn_risk" && renderChurnRisk(data as WidgetData["churn_risk"])}
            {widgetId === "revenue_forecast" && renderRevenueForecast(data as WidgetData["revenue_forecast"])}
            {widgetId === "kpi_card" && renderKpiCard(data as WidgetData["kpi_card"])}
            {widgetId === "compliance_score" && renderCompliance(data as WidgetData["compliance_score"])}
            {widgetId === "anomaly_feed" && (
                <div style={{ fontSize: 13, color: "#f59e0b" }}>
                    ⚠️ {(data as WidgetData["anomaly_feed"]).anomalies[0]?.table} anomaly detected
                </div>
            )}
            <div style={{ fontSize: 10, color: t.textColor + "33", marginTop: 12, textAlign: "right" }}>
                Powered by <a href="https://alti.ai" style={{ color: t.primaryColor }}>Alti Analytics</a>
            </div>
        </div>
    );
};

export default AltiWidget;
