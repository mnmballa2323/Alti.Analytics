'use client';

export default function LookerEmbed() {
    // In a production setup, you would use:
    // import { LookerEmbedSDK } from '@looker/embed-sdk'
    // along with a secure SSO URL generation flow via the backend API.

    return (
        <div className="w-full h-full min-h-[500px] bg-slate-900 border border-slate-700/50 rounded-xl overflow-hidden flex flex-col relative">
            <div className="p-4 border-b border-slate-700 bg-slate-800 flex justify-between items-center">
                <h3 className="text-lg font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Enterprise BI (Looker)
                </h3>
                <span className="text-xs font-mono text-slate-500 bg-slate-900 px-3 py-1 rounded-full border border-slate-700">Embedded Mode</span>
            </div>

            {/* Simulation of an iFrame connecting to Looker Studio or Looker Instance */}
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
                <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
                <p className="text-slate-400 font-mono text-sm max-w-md">
                    Connecting securely to <strong>Looker API</strong> via Single Sign-On (SSO). <br />
                    Loading semantic model: <span className="text-blue-400">`live_market_data.view.lkml`</span>
                </p>
            </div>

            {/* Mock Dashboard Render */}
            <div className="absolute inset-0 top-[69px] bg-slate-900 p-6 opacity-0 hover:opacity-100 transition-opacity duration-1000 flex flex-col gap-6">
                <div className="grid grid-cols-4 gap-4">
                    <div className="bg-slate-800 p-4 rounded border border-slate-700">
                        <p className="text-xs text-slate-400">Avg Heart Rate</p>
                        <p className="text-2xl font-bold text-emerald-400">145 BPM</p>
                    </div>
                    <div className="bg-slate-800 p-4 rounded border border-slate-700">
                        <p className="text-xs text-slate-400">Max Sprint</p>
                        <p className="text-2xl font-bold text-blue-400">32.1 km/h</p>
                    </div>
                    <div className="bg-slate-800 p-4 rounded border border-slate-700">
                        <p className="text-xs text-slate-400">Total Distance</p>
                        <p className="text-2xl font-bold text-fuchsia-400">112.4 km</p>
                    </div>
                    <div className="bg-slate-800 p-4 rounded border border-red-900/50">
                        <p className="text-xs text-red-400">High Risk Players</p>
                        <p className="text-2xl font-bold text-red-500">2</p>
                    </div>
                </div>
                <div className="flex-1 border border-slate-700 rounded bg-slate-800/50 flex items-center justify-center">
                    <span className="text-slate-500 font-mono text-sm">[Looker Drillable Chart Rendering Area]</span>
                </div>
            </div>
        </div>
    );
}
