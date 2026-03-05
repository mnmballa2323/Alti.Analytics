"use client";

import React from "react";

export function FinancialArbitrage({
    asset,
    spread,
    action
}: {
    asset: string;
    spread: number;
    action: string;
}) {
    return (
        <div className="w-full bg-[#0a0a0a] border border-amber-900/40 rounded-xl p-6 mt-4 relative overflow-hidden group">
            {/* Scanline Effect */}
            <div className="absolute top-0 left-0 w-full h-full bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:100%_4px] pointer-events-none mix-blend-overlay z-10"></div>

            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-amber-600 to-yellow-400 shadow-[0_0_15px_rgba(217,119,6,0.5)]"></div>

            <div className="flex justify-between items-center mb-6 relative z-20">
                <div>
                    <h3 className="text-xl text-amber-100 font-semibold tracking-wide flex items-center">
                        <span className="mr-2 animate-pulse text-amber-500">⚡</span>
                        Algorithmic Target
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">HFT Synthetic Strategy</p>
                </div>

                <div className="text-right">
                    <div className="text-4xl text-white font-black font-mono tracking-tighter">{asset}</div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4 relative z-20">
                <div className="bg-black/60 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
                    <p className="text-gray-500 text-xs mb-1 uppercase font-bold">Predicted Spread</p>
                    <div className="text-3xl text-amber-400 font-mono mt-2">+{spread}<span className="text-sm ml-1 text-amber-900">BPS</span></div>
                </div>

                <div className="bg-black/60 border border-gray-800 rounded-lg p-4 flex flex-col justify-center items-center text-center">
                    <p className="text-gray-500 text-xs mb-2 uppercase font-bold">Autonomous Execution</p>
                    <button className={`w-full py-2 rounded font-black text-sm uppercase tracking-widest transition-all ${action.includes('LONG') ? 'bg-green-600 hover:bg-green-500 text-white shadow-[0_0_15px_rgba(22,163,74,0.4)]' :
                            'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(220,38,38,0.4)]'
                        }`}>
                        {action}
                    </button>
                </div>
            </div>
        </div>
    );
}
