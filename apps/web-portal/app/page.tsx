"use client";

import { useState } from 'react';
import { useUIState, useActions } from 'ai/rsc';
import { motion, AnimatePresence } from 'framer-motion';
import { AI } from './actions';
import MarketTicker from '@/components/MarketTicker';
import LookerEmbed from '@/components/LookerEmbed';
import GlassPanel from '@/components/ux/GlassPanel'; // Updated import
import DigitalTwinGlobe from '@/components/3d-globe/DigitalTwinGlobe'; // New import
import { Activity, Cpu, Hexagon, Bot, User, Crosshair, Map, ShieldAlert, Target } from 'lucide-react'; // Updated import
import { clsx, type ClassValue } from 'clsx'; // New import
import { twMerge } from 'tailwind-merge'; // New import

// --- Utility for Tailwind classes ---
function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export default function Home() {
    // Scaffolded state for the Universal Actuation UI Hook
    const hasActiveEdgeAlert = true;

    // AI SDK State
    const [messages, setMessages] = useUIState<typeof AI>();
    const { submitMessage } = useActions<typeof AI>();
    const [inputValue, setInputValue] = useState('');

    return (
        <main className="min-h-screen p-8 lg:p-12 text-slate-200 selection:bg-fuchsia-500 selection:text-white relative overflow-hidden bg-[#0A0A0A]">

            {/* Ambient Background Gradients */}
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-900/20 blur-[120px] rounded-full pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-fuchsia-900/20 blur-[120px] rounded-full pointer-events-none" />

            {/* AUTONOMOUS ACTUATION ALERT BANNER */}
            <AnimatePresence>
                {hasActiveEdgeAlert && (
                    <motion.div
                        initial={{ opacity: 0, y: -50 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -50 }}
                        className="absolute top-0 left-0 w-full bg-red-600/90 text-white px-6 py-3 flex items-center justify-between shadow-2xl z-50 backdrop-blur-md border-b border-red-500/50"
                    >
                        <div className="flex items-center gap-3">
                            <motion.span
                                animate={{ scale: [1, 1.2, 1] }}
                                transition={{ repeat: Infinity, duration: 2 }}
                                className="text-2xl"
                            >
                                ⚠️
                            </motion.span>
                            <div>
                                <h3 className="font-bold uppercase tracking-widest text-sm flex items-center gap-2">
                                    <Activity size={16} /> Autonomous Actuation Executed
                                </h3>
                                <p className="text-xs opacity-90 font-mono">Swarm resolved an anomaly via Trade Execution [Receipt: ACT_999888777]</p>
                            </div>
                        </div>
                        <button className="text-xs bg-red-800 hover:bg-red-900 px-4 py-2 rounded uppercase font-bold tracking-wider transition-colors border border-red-500/30">
                            Review Action
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Header */}
            <motion.header
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-12 border-b border-white/5 pb-8 flex justify-between items-end relative z-10 mt-12"
            >
                <div>
                    <div className="flex items-center gap-3 mb-2 text-fuchsia-500">
                        <Hexagon size={28} className="animate-spin-slow" />
                        <span className="font-mono text-sm tracking-widest uppercase">Kernel Omniverse</span>
                    </div>
                    <h1 className="text-5xl lg:text-6xl font-black tracking-tight bg-gradient-to-br from-white via-slate-300 to-slate-500 text-transparent bg-clip-text">
                        Alti.Analytics Engine
                    </h1>
                    <p className="mt-4 text-slate-400 max-w-xl text-lg font-light leading-relaxed">
                        Google Cloud Native Decision Intelligence. Processing 500k+ events/sec via BigQuery & Gemini Swarms.
                    </p>
                </div>

                {/* User Context/Tenant Mock */}
                <div className="text-right text-xs font-mono text-slate-500 space-y-1 bg-slate-900/50 p-4 rounded-xl border border-white/5 backdrop-blur-md shadow-inner">
                    <div className="text-emerald-500 flex items-center justify-end gap-2">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        SYSTEM: ONLINE
                    </div>
                    <div>TENANT: GLOBAL_MARKETS_01</div>
                    <div className="text-fuchsia-400/80">LATENCY: 4ms</div>
                </div>
            </motion.header>

            {/* Grid Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
                {/* Left Column: Epic 16 3D Digital Twin & Data Streams */}
                <div className="lg:col-span-1 space-y-8">
                    {/* EPIC 16: Supply Chain Digital Twin 3D View */}
                    <GlassPanel variant="subtle" className="h-[450px] p-0 overflow-hidden flex flex-col justify-start">
                        <div className="p-4 border-b border-white/5 bg-black/40 flex items-center justify-between z-10">
                            <div className="flex items-center gap-2">
                                <Map className="w-5 h-5 text-emerald-400" />
                                <h2 className="text-white font-medium text-lg">Supply Chain Omniverse</h2>
                            </div>
                            <div className="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded border border-emerald-500/20">
                                LIVE
                            </div>
                        </div>
                        <div className="flex-1 w-full h-full relative">
                            <DigitalTwinGlobe />
                        </div>
                    </GlassPanel>

                    <GlassPanel variant="subtle" className="p-6 space-y-6">
                        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                            <Activity size={18} className="text-emerald-500" /> Ingestion Streams
                        </h3>
                        {/* Context/Placeholder for Pub/Sub Pipeline Stats */}
                        <div className="p-4 bg-slate-950/80 border border-white/5 rounded-xl space-y-3 font-mono text-xs">
                            <div className="flex justify-between items-center text-slate-400">
                                <span>Dataflow Sync:</span>
                                <span className="text-emerald-400 bg-emerald-900/30 px-2 py-1 rounded">HEALTHY</span>
                            </div>
                            <div className="flex justify-between items-center text-slate-400">
                                <span>Pub/Sub Throughput:</span>
                                <span className="text-white">2,401 msg/s</span>
                            </div>
                        </div>
                    </GlassPanel>
                </div>

                {/* Right Column: AI Agent Interface */}
                <div className="lg:col-span-2">
                    <GlassPanel variant="vibrant" className="h-full flex flex-col relative overflow-hidden">
                        <div className="p-6 border-b border-white/5 bg-fuchsia-950/20 backdrop-blur-md flex justify-between items-center">
                            <h3 className="text-sm font-bold text-white uppercase tracking-widest flex items-center gap-2">
                                <Hexagon size={18} className="text-fuchsia-400" /> Sentient Manifestation
                            </h3>
                            <span className="text-xs font-mono text-fuchsia-300/60 bg-fuchsia-900/30 px-3 py-1 rounded-full border border-fuchsia-500/20">
                                VERCEL AI SDK . STREAM UI
                            </span>
                        </div>

                        <div className="flex-1 min-h-[500px] flex flex-col relative w-full pb-4">
                            {/* Chat Window / Component Render Space */}
                            <div className="flex-1 p-6 space-y-8 overflow-y-auto mb-20 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    className="flex justify-start"
                                >
                                    <div className="bg-slate-900/60 p-5 rounded-2xl rounded-tl-sm border border-white/10 w-full max-w-2xl shadow-lg backdrop-blur-sm">
                                        <p className="text-slate-300 leading-relaxed">
                                            I am the upgraded Sentient Agent. I manifest bespoke UI components on-demand using streaming React Server Components. Describe a logistics or market anomaly to observe generative actuation.
                                        </p>
                                    </div>
                                </motion.div>

                                <AnimatePresence mode="popLayout">
                                    {messages.map((message) => (
                                        <motion.div
                                            key={message.id}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="flex justify-start w-full"
                                        >
                                            <div className="w-full">
                                                {message.display}
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>
                            </div>

                            {/* Input Box */}
                            <div className="absolute bottom-0 left-0 w-full p-6 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent pt-12">
                                <form
                                    className="flex w-full space-x-4 relative"
                                    onSubmit={async (e) => {
                                        e.preventDefault();
                                        if (!inputValue.trim()) return;

                                        // Add user message to UI state
                                        setMessages((currentMessages) => [
                                            ...currentMessages,
                                            {
                                                id: Date.now(),
                                                display: (
                                                    <div className="flex justify-end w-full mb-6 relative z-10">
                                                        <div className="bg-fuchsia-600/20 text-fuchsia-100 p-4 rounded-2xl rounded-tr-sm border border-fuchsia-500/30 shadow-[0_0_15px_rgba(217,70,239,0.15)] backdrop-blur-md">
                                                            {inputValue}
                                                        </div>
                                                    </div>
                                                ),
                                            },
                                        ]);

                                        const currentInput = inputValue;
                                        setInputValue('');

                                        // Submit and get response component from server
                                        const responseMessage = await submitMessage(currentInput);
                                        setMessages((currentMessages) => [
                                            ...currentMessages,
                                            responseMessage,
                                        ]);
                                    }}
                                >
                                    <div className="relative w-full shadow-2xl rounded-xl">
                                        <input
                                            type="text"
                                            value={inputValue}
                                            onChange={(e) => setInputValue(e.target.value)}
                                            placeholder="Simulate an anomaly..."
                                            className="w-full bg-slate-950/80 border border-white/10 rounded-xl px-5 py-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-fuchsia-500/50 backdrop-blur-md transition-all font-light"
                                        />
                                        {/* Subtle inner glow */}
                                        <div className="absolute inset-0 rounded-xl pointer-events-none shadow-[inset_0_0_20px_rgba(255,255,255,0.02)]" />
                                    </div>
                                    <button
                                        type="submit"
                                        className="px-8 py-4 bg-fuchsia-600 hover:bg-fuchsia-500 text-white rounded-xl font-bold tracking-wider transition-all shadow-[0_0_20px_rgba(217,70,239,0.3)] hover:shadow-[0_0_30px_rgba(217,70,239,0.5)] active:scale-95 flex items-center gap-2"
                                    >
                                        Execute
                                    </button>
                                </form>
                            </div>
                        </div>
                    </GlassPanel>
                </div >
            </div >
        </main >
    );
}
