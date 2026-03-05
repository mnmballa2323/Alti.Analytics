"use client";

import { useState } from 'react';
import { useUIState, useActions } from 'ai/rsc';
import { AI } from './actions';
import MarketTicker from '@/components/MarketTicker';
import LookerEmbed from '@/components/LookerEmbed';

export default function Home() {
    // Scaffolded state for the Universal Actuation UI Hook
    const hasActiveEdgeAlert = true;

    // AI SDK State
    const [messages, setMessages] = useUIState<typeof AI>();
    const { submitMessage } = useActions<typeof AI>();
    const [inputValue, setInputValue] = useState('');

    return (
        <main className="min-h-screen p-12 bg-black text-slate-200 selection:bg-fuchsia-500 selection:text-white relative">

            {/* AUTONOMOUS ACTUATION ALERT BANNER */}
            {hasActiveEdgeAlert && (
                <div className="absolute top-0 left-0 w-full bg-red-600/90 text-white px-6 py-3 flex items-center justify-between border-b-4 border-red-800 animate-pulse shadow-2xl z-50">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">⚠️</span>
                        <div>
                            <h3 className="font-bold uppercase tracking-widest text-sm">Autonomous Actuation Executed</h3>
                            <p className="text-xs opacity-90">Swarm resolved an anomaly via Trade Execution [Receipt: ACT_999888777]</p>
                        </div>
                    </div>
                    <button className="text-xs bg-red-800 hover:bg-red-900 px-4 py-2 rounded uppercase font-bold tracking-wider transition-colors border border-red-500">
                        Review Action
                    </button>
                </div>
            )}

            {/* Header */}
            <header className="mb-16 border-b border-white/10 pb-8 flex justify-between items-end">
                <div>
                    <h1 className="text-5xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-emerald-400 to-fuchsia-500 text-transparent bg-clip-text">
                        Alti.Analytics Engine
                    </h1>
                    <p className="mt-2 text-slate-400 max-w-xl text-lg">
                        Google Cloud Native Decision Intelligence. Processing 500k+ events/sec via BigQuery & Gemini Agents.
                    </p>
                </div>

                {/* User Context/Tenant Mock */}
                <div className="text-right text-sm font-mono text-slate-500">
                    <div className="text-emerald-500">SYSTEM: ONLINE</div>
                    <div>TENANT: GLOBAL_MARKETS_01</div>
                </div>
            </header>

            {/* Grid Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Left Column: Data Streams */}
                <div className="lg:col-span-1 space-y-8">
                    <section className="space-y-4">
                        <h3 className="text-lg font-bold text-slate-300 uppercase tracking-widest border-l-4 border-emerald-500 pl-3">
                            Ingestion Streams
                        </h3>
                        <MarketTicker />

                        {/* Context/Placeholder for Pub/Sub Pipeline Stats */}
                        <div className="p-4 bg-slate-900 border border-slate-700/50 rounded-xl space-y-2">
                            <div className="flex justify-between text-xs font-mono text-slate-400">
                                <span>Dataflow Pipeline Status:</span>
                                <span className="text-emerald-400">HEALTHY</span>
                            </div>
                            <div className="flex justify-between text-xs font-mono text-slate-400">
                                <span>Pub/Sub Throughput:</span>
                                <span>2,401 msg/s</span>
                            </div>
                        </div>
                    </section>

                    <section className="space-y-4 pt-4 border-t border-slate-800">
                        <LookerEmbed />
                    </section>
                </div>

                {/* Right Column: AI Agent Interface */}
                <div className="lg:col-span-2">
                    <section className="space-y-4 h-full flex flex-col">
                        <h3 className="text-lg font-bold text-slate-300 uppercase tracking-widest border-l-4 border-fuchsia-500 pl-3">
                            Sentient UI (Generative Context)
                        </h3>

                        <div className="flex-1 min-h-[500px] border border-slate-700/50 bg-slate-900 rounded-xl overflow-hidden flex flex-col relative w-full pb-4">
                            {/* Chat Window / Component Render Space */}
                            <div className="flex-1 p-6 space-y-6 overflow-y-auto mb-16">
                                <div className="flex justify-start">
                                    <div className="bg-slate-800 p-4 rounded-xl rounded-tl-none border border-slate-700 w-full max-w-2xl">
                                        <p className="text-slate-300">
                                            I am the upgraded Sentient Agent. I can now manifest bespoke UI components (Supply Chain Maps, Arbitrage Displays) on-demand based on the telemetry I analyze. Throw an anomaly scenario at me.
                                        </p>
                                    </div>
                                </div>

                                {messages.map((message) => (
                                    <div key={message.id} className="flex justify-start w-full">
                                        <div className="w-full">
                                            {message.display}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Input Box */}
                            <div className="absolute bottom-0 left-0 w-full p-4 bg-slate-800 border-t border-slate-700 flex space-x-4">
                                <form
                                    className="flex w-full space-x-4"
                                    onSubmit={async (e) => {
                                        e.preventDefault();

                                        // Add user message to UI state
                                        setMessages((currentMessages) => [
                                            ...currentMessages,
                                            {
                                                id: Date.now(),
                                                display: (
                                                    <div className="flex justify-end w-full mb-4">
                                                        <div className="bg-fuchsia-600/20 text-fuchsia-100 p-4 rounded-xl rounded-tr-none border border-fuchsia-500/30">
                                                            {inputValue}
                                                        </div>
                                                    </div>
                                                ),
                                            },
                                        ]);

                                        // Submit and get response component from server
                                        const responseMessage = await submitMessage(inputValue);
                                        setMessages((currentMessages) => [
                                            ...currentMessages,
                                            responseMessage,
                                        ]);

                                        setInputValue('');
                                    }}
                                >
                                    <input
                                        type="text"
                                        value={inputValue}
                                        onChange={(e) => setInputValue(e.target.value)}
                                        placeholder="Describe a logistics or trading anomaly to trigger generative UI..."
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-slate-200 focus:outline-none focus:ring-1 focus:ring-fuchsia-500"
                                    />
                                    <button
                                        type="submit"
                                        className="px-6 py-3 bg-fuchsia-600 hover:bg-fuchsia-500 text-white rounded-lg font-bold transition-colors"
                                    >
                                        Execute
                                    </button>
                                </form>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        </main>
    );
}
