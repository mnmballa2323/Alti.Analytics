'use client';

import { useState, useEffect } from 'react';

// Define the shape of our live market data element
interface TickerData {
    symbol: string;
    price: number;
    quantity: number;
    timestamp: string;
}

export default function MarketTicker() {
    const [ticker, setTicker] = useState<TickerData | null>(null);

    // In a real scenario, this connects to a WebSocket or polls the Kong API Gateway layer
    useEffect(() => {
        const fetchLatestTrade = async () => {
            // Mock data fetching replacing actual API querying to BigQuery/Redis
            const mockResult: TickerData = {
                symbol: 'BTCUSDT',
                price: 64500.50 + (Math.random() * 50 - 25), // Random fluctuation
                quantity: Math.random() * 2,
                timestamp: new Date().toISOString()
            };
            setTicker(mockResult);
        };

        fetchLatestTrade();
        const interval = setInterval(fetchLatestTrade, 3000); // 3 second polling

        return () => clearInterval(interval);
    }, []);

    return (
        <div className="p-6 bg-slate-900 text-white rounded-xl shadow-2xl border border-slate-700 w-full max-w-md mx-auto space-y-4">
            <h2 className="text-xl font-bold tracking-wider text-slate-300">LIVE MARKET STREAM</h2>
            {ticker ? (
                <div className="flex flex-col space-y-2">
                    <div className="flex justify-between items-center text-3xl font-mono text-emerald-400">
                        <span>{ticker.symbol}</span>
                        <span>${ticker.price.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm text-slate-400 font-mono">
                        <span>Vol: {ticker.quantity.toFixed(4)}</span>
                        <span>{new Date(ticker.timestamp).toLocaleTimeString()}</span>
                    </div>
                </div>
            ) : (
                <div className="animate-pulse text-slate-500 font-mono">Waiting for data stream...</div>
            )}
        </div>
    );
}
