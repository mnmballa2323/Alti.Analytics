import MarketTicker from '@/components/MarketTicker';
import TacticalPitch from '@/components/TacticalPitch';
import LookerEmbed from '@/components/LookerEmbed';

export default function Home() {
    return (
        <main className="min-h-screen p-12 bg-black text-slate-200 selection:bg-fuchsia-500 selection:text-white">
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
                            Autonomous Analyst (Gemini)
                        </h3>

                        <div className="flex-1 min-h-[400px] border border-slate-700/50 bg-slate-900 rounded-xl overflow-hidden flex flex-col relative">
                            {/* Fake Chat Window */}
                            <div className="flex-1 p-6 space-y-6 overflow-y-auto">
                                <div className="flex justify-start">
                                    <div className="bg-slate-800 p-4 rounded-xl rounded-tl-none max-w-[80%] border border-slate-700">
                                        <p className="text-slate-300">
                                            Hello. I am your Gemini-powered Autonomous Agent. I maintain direct SQL access to our live Data Warehouse in BigQuery. How can I analyze our telemetry streams today?
                                        </p>
                                    </div>
                                </div>

                                <div className="flex justify-end">
                                    <div className="bg-fuchsia-600/20 text-fuchsia-100 p-4 rounded-xl rounded-tr-none max-w-[80%] border border-fuchsia-500/30">
                                        <p>What is the current trend for BTC over the last 15 minutes?</p>
                                    </div>
                                </div>

                                <div className="flex justify-start">
                                    <div className="bg-slate-800 p-4 rounded-xl rounded-tl-none max-w-[80%] border border-slate-700 space-y-3">
                                        <div className="text-xs font-mono text-fuchsia-400 border border-fuchsia-400/20 bg-fuchsia-400/5 p-2 rounded">
                                            🔧 Tool Call: `execute_bigquery_sql`<br />
                                            SELECT avg(price) FROM `alti_analytics_prod.live_market_data` WHERE symbol = 'BTCUSDT' AND timestamp {'>'}= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE)
                                        </div>
                                        <p className="text-slate-300">
                                            Based on my BigQuery execution over our live Dataflow sink, BTC has maintained an average price of $64,510.20 over the last 15 minutes with exceptionally high volume accumulation indicating strong buy-side pressure. I recommend increasing the delta on our systematic holding strategy.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Input Box */}
                            <div className="p-4 bg-slate-800 border-t border-slate-700 flex space-x-4">
                                <input
                                    type="text"
                                    disabled
                                    placeholder="Request analysis or SQL execution..."
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-slate-200 focus:outline-none focus:ring-1 focus:ring-fuchsia-500"
                                />
                                <button disabled className="px-6 py-3 bg-fuchsia-600 hover:bg-fuchsia-500 text-white rounded-lg font-bold transition-colors">
                                    Send
                                </button>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        </main>
    );
}
