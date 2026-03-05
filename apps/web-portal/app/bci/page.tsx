'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Activity, BrainCircuit, Waves, Zap } from 'lucide-react';

/**
 * Epic 24: Direct Neural Interfacing
 * A telemetry dashboard visualizing the real-time EEG brainwave state of the human operator
 * and displaying the cognitive intents decoded by the Alti.Analytics ML Gateway.
 */
export default function BCIDashboard() {
    const [eegState, setEegState] = useState<number[]>(Array(8).fill(0));
    const [intentLog, setIntentLog] = useState<string[]>([]);

    // Simulate real-time GraphQL WebSockets from the EEG Translator
    useEffect(() => {
        const interval = setInterval(() => {
            // Generate random fluctuations simulating 8-channel EEG microvolts
            const newChannels = Array.from({ length: 8 }, () => (Math.random() * 80) - 40);
            setEegState(newChannels);

            // Randomly simulate a P300 spike / cognitive decision
            if (Math.random() > 0.95) {
                const actions = [
                    "AUTHORIZE_DEFI_ARBITRAGE: ETH/USDC",
                    "DISPATCH_AMR_DRONE: WH-ALPHA",
                    "REROUTE_VESSEL: MAERSK-8X",
                    "APPROVE_QUANTUM_OFFLOAD"
                ];
                const action = actions[Math.floor(Math.random() * actions.length)];
                setIntentLog(prev => [`[NEURAL SYNC] ${action}`, ...prev].slice(0, 5));
            }
        }, 200);

        return () => clearInterval(interval);
    }, []);

    return (
        <main className="min-h-screen p-12 bg-[#020617] text-white flex flex-col items-center justify-center relative overflow-hidden">
            {/* Ambient BCI Aura */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-indigo-900/20 rounded-full blur-[150px] pointer-events-none" />

            <div className="max-w-4xl w-full z-10 space-y-8">
                <header className="flex justify-between items-end border-b border-indigo-500/30 pb-6">
                    <div>
                        <h1 className="text-4xl font-black bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent flex items-center gap-4">
                            <BrainCircuit size={40} className="text-indigo-500" />
                            Neural Telemetry Link
                        </h1>
                        <p className="text-indigo-200/60 mt-2 font-mono text-sm tracking-widest">
                            Direct Brain-Computer Interface (BCI) • Alti.Analytics Swarm
                        </p>
                    </div>
                    <div className="flex items-center gap-2 px-4 py-2 bg-indigo-950/50 border border-indigo-500/50 rounded-full text-indigo-300 font-mono text-xs">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                        </span>
                        SYNC STABLE (12.4ms)
                    </div>
                </header>

                <div className="grid grid-cols-2 gap-8">
                    {/* Raw EEG Stream Viewer */}
                    <div className="bg-black/40 border border-white/5 p-6 rounded-2xl backdrop-blur-md">
                        <h3 className="text-sm font-bold text-slate-400 uppercase flex items-center gap-2 mb-6">
                            <Waves size={16} className="text-cyan-500" /> EEG Spatial Topography
                        </h3>
                        <div className="space-y-4">
                            {eegState.map((val, idx) => (
                                <div key={idx} className="flex items-center gap-4">
                                    <span className="text-xs font-mono text-slate-500 w-8">CH{idx}</span>
                                    <div className="flex-1 h-1 bg-slate-800 rounded-full relative overflow-hidden">
                                        <motion.div
                                            className="absolute h-full bg-cyan-500/80"
                                            animate={{
                                                width: `${Math.abs(val)}%`,
                                                left: val < 0 ? '50%' : '50%',
                                                x: val < 0 ? '-100%' : '0%'
                                            }}
                                            transition={{ type: "spring", bounce: 0, duration: 0.2 }}
                                        />
                                    </div>
                                    <span className="text-xs font-mono text-cyan-400 w-12 text-right">
                                        {val.toFixed(1)}μV
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Decoded ML Intents */}
                    <div className="bg-black/40 border border-white/5 p-6 rounded-2xl backdrop-blur-md flex flex-col">
                        <h3 className="text-sm font-bold text-slate-400 uppercase flex items-center gap-2 mb-6">
                            <Zap size={16} className="text-fuchsia-500" /> Decoded Intents
                        </h3>
                        <div className="flex-1 space-y-3 font-mono text-xs overflow-y-auto">
                            {intentLog.length === 0 ? (
                                <div className="text-slate-600 animate-pulse text-center mt-20">
                                    Awaiting cognitive formulation...
                                </div>
                            ) : (
                                intentLog.map((log, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className="p-3 bg-fuchsia-950/20 border border-fuchsia-500/30 text-fuchsia-300 rounded shadow-[0_0_15px_rgba(217,70,239,0.1)]"
                                    >
                                        {log}
                                    </motion.div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
}
