import { createAI, getMutableAIState, streamUI } from "ai/rsc";
import { google } from "@ai-sdk/google";
import { z } from "zod";
import React from "react";
import { SupplyChainMap } from "../components/generative/SupplyChainMap";
import { FinancialArbitrage } from "../components/generative/FinancialArbitrage";

// This server action uses the Gemini model to analyze a user's prompt (or an anomaly report)
// and dynamically stream back a React component rather than just text.
export async function submitMessage(message: str) {
    "use server";

    const result = await streamUI({
        model: google("gemini-1.5-pro-latest"),
        system: `You are the Alti.Analytics Sentient UI Generator. 
    Analyze the incoming anomaly report. If it relates to physical logistics or supply chains, 
    render the SupplyChainMap. If it involves complex market trading or equities, 
    render the FinancialArbitrage view. You must prioritize rendering UI over text.`,
        prompt: message,
        text: ({ content, done }) => {
            if (done) {
                return <div className="p-4 bg-gray-900 rounded-lg text-green-400 mt-2">{content}</div>;
            }
            return <div className="text-gray-400">Thinking...</div>;
        },
        tools: {
            renderSupplyChainMap: {
                description: 'Render an interactive Supply Chain Map representing a logistics anomaly.',
                parameters: z.object({
                    region: z.string().describe('The geographic region of the anomaly (e.g., "Suez Canal")'),
                    severity: z.string().describe('The severity level (e.g., "CRITICAL")'),
                    impacted_vessels: z.number().describe('Estimated number of impacted cargo vessels'),
                }),
                generate: async function* ({ region, severity, impacted_vessels }) {
                    yield <div className="animate-pulse text-blue-400">Loading geospatial data for {region}...</div>;

                    // Simulate latency fetching complex data
                    await new Promise((resolve) => setTimeout(resolve, 1500));

                    return (
                        <SupplyChainMap
                            region={region}
                            severity={severity}
                            impactedVessels={impacted_vessels}
                        />
                    );
                },
            },
            renderFinancialArbitrage: {
                description: 'Render an interactive Financial Arbitrage dashboard for a market anomaly.',
                parameters: z.object({
                    asset: z.string().describe('The primary asset (e.g., "BTC/USD")'),
                    predicted_spread: z.number().describe('The modeled spread in basis points'),
                    recommended_action: z.string().describe('The autonomous trade action (e.g., "EXECUTE_LONG")'),
                }),
                generate: async function* ({ asset, predicted_spread, recommended_action }) {
                    yield <div className="animate-pulse text-yellow-400">Calculating order book depth for {asset}...</div>;

                    await new Promise((resolve) => setTimeout(resolve, 1500));

                    return (
                        <FinancialArbitrage
                            asset={asset}
                            spread={predicted_spread}
                            action={recommended_action}
                        />
                    );
                },
            }
        }
    });

    return {
        id: Date.now(),
        display: result.value,
    };
}

export const AI = createAI({
    actions: {
        submitMessage,
    },
    initialAIState: [],
    initialUIState: [],
});
