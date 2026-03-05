'use client';

import { useState, useEffect } from 'react';

// Simulating optical tracking telemetry
interface PlayerTelemetry {
    id: string;
    x: number; // 0-105 meters (pitch length)
    y: number; // 0-68 meters (pitch width)
    speed: number;
    heartRate: number;
    injuryRiskScore: number; // 0.0 to 1.0 from Vertex AI Model
}

export default function TacticalPitch() {
    const [players, setPlayers] = useState<PlayerTelemetry[]>([]);

    useEffect(() => {
        // Simulate the 10Hz IoT WebSocket stream
        const simulateStream = () => {
            const newPlayers: PlayerTelemetry[] = [];
            for (let i = 1; i <= 11; i++) {
                // Base positions for a 4-3-3 formation
                const baseX = 10 + (i * 8);
                const baseY = 10 + ((i % 5) * 12);

                newPlayers.push({
                    id: `Player ${i}`,
                    x: Math.max(0, Math.min(105, baseX + (Math.random() * 6 - 3))),
                    y: Math.max(0, Math.min(68, baseY + (Math.random() * 6 - 3))),
                    speed: Math.random() * 25,
                    heartRate: 140 + Math.random() * 40,
                    injuryRiskScore: Math.random() > 0.85 ? 0.8 : 0.1 // Randomly flag a high risk player
                });
            }
            setPlayers(newPlayers);
        };

        simulateStream();
        const interval = setInterval(simulateStream, 1000); // Poll 1Hz for UI smoothness
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="p-6 bg-slate-900 border border-slate-700/50 rounded-xl space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold text-slate-300 uppercase tracking-widest border-l-4 border-fuchsia-500 pl-3">
                    Tactical Pitch Vision
                </h3>
                <div className="flex space-x-3 text-xs font-mono">
                    <span className="text-emerald-400">● Nominal Load</span>
                    <span className="text-red-500 animate-pulse">● High Injury Risk (ACWR)</span>
                </div>
            </div>

            {/* Pitch Rendering Area */}
            <div className="relative w-full aspect-[105/68] bg-emerald-900/40 border-2 border-slate-500/50 rounded overflow-hidden">
                {/* Pitch Markings (Simplified) */}
                <div className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-500/30"></div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full border border-slate-500/30"></div>

                {/* Player Dots */}
                {players.map((p) => {
                    // Map 105x68 meters to percentage
                    const leftPct = (p.x / 105) * 100;
                    const topPct = (p.y / 68) * 100;
                    const isHighRisk = p.injuryRiskScore > 0.5;

                    return (
                        <div
                            key={p.id}
                            className={`absolute w-3 h-3 -ml-1.5 -mt-1.5 rounded-full shadow-[0_0_10px_rgba(0,0,0,0.5)] transition-all duration-300 ${isHighRisk ? 'bg-red-500 shadow-red-500/50' : 'bg-emerald-400 shadow-emerald-400/50'
                                }`}
                            style={{ left: `${leftPct}%`, top: `${topPct}%` }}
                            title={`${p.id} - HR: ${Math.round(p.heartRate)} - Risk: ${p.injuryRiskScore.toFixed(2)}`}
                        >
                            {isHighRisk && (
                                <div className="absolute -inset-2 rounded-full border border-red-500 animate-ping opacity-75"></div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
