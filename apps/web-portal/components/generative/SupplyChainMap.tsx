"use client";

import React from "react";

export function SupplyChainMap({
    region,
    severity,
    impactedVessels
}: {
    region: string;
    severity: string;
    impactedVessels: number;
}) {
    return (
        <div className="w-full bg-[#0a0a0a] border border-blue-900/50 rounded-xl p-6 mt-4 relative overflow-hidden">
            {/* Generative Visuals */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-cyan-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]"></div>

            <div className="flex justify-between items-start mb-6">
                <div>
                    <h3 className="text-xl text-blue-100 font-semibold tracking-wide">
                        🌍 Global Logistics Disturbance
                    </h3>
                    <p className="text-sm text-blue-400 mt-1 uppercase tracking-widest">{region}</p>
                </div>

                <div className={`px-3 py-1 rounded border ${severity === 'CRITICAL' ? 'bg-red-900/30 border-red-500 text-red-400' : 'bg-yellow-900/30 border-yellow-500 text-yellow-400'} font-black text-xs`}>
                    {severity}
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="bg-black/50 border border-gray-800 rounded-lg p-4">
                    <p className="text-gray-500 text-xs mb-1 uppercase">Vessels In Route</p>
                    <div className="text-3xl text-white font-mono">{impactedVessels}</div>
                </div>
                <div className="bg-black/50 border border-gray-800 rounded-lg p-4">
                    <p className="text-gray-500 text-xs mb-1 uppercase">Est. Delay</p>
                    <div className="text-3xl text-cyan-400 font-mono">14.2<span className="text-sm ml-1 text-gray-500">days</span></div>
                </div>
            </div>

            {/* Mock 3D Geospatial Map Area */}
            <div className="mt-6 w-full h-40 border border-gray-800/50 rounded-lg bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-black to-black relative flex items-center justify-center">
                <div className="absolute w-full h-full bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]"></div>
                <span className="text-blue-500/50 text-sm italic z-10">[WebGL Navigational Chart Rendered]</span>

                {/* Anomaly Blip */}
                <div className="absolute w-3 h-3 bg-red-500 rounded-full shadow-[0_0_15px_rgba(239,68,68,1)] animate-ping"></div>
            </div>
        </div>
    );
}
