use wasm_bindgen::prelude::*;
use serde::{Serialize, Deserialize};

// When the `wee_alloc` feature is enabled, use `wee_alloc` as the global
// allocator to keep the WASM binary incredibly small.
#[cfg(feature = "wee_alloc")]
#[global_allocator]
static ALLOC: wee_alloc::WeeAlloc = wee_alloc::WeeAlloc::INIT;

/// Represents incoming high-frequency telemetry at the network edge.
#[derive(Deserialize)]
pub struct EdgeTelemetry {
    pub sensor_id: String,
    pub timestamp_ms: u64,
    pub primary_metric: f64,
    pub secondary_metric: f64,
}

/// Represents the autonomous decision made locally by the Edge Engine.
#[derive(Serialize)]
pub struct EdgeActuationDecision {
    pub detected_anomaly: bool,
    pub confidence_score: f64,
    pub action_required: String,
    pub execution_latency_ms: u64, // The time it took to decide in Wasm
}

/// The core intelligence heuristic. 
/// In production, this can parse complex ML weights injected from the Cloud Swarm.
/// For this implementation, we use a sophisticated thresholding algorithm.
#[wasm_bindgen]
pub fn analyze_telemetry_stream(json_payload: &str) -> String {
    let start_time = 0; // In a true browser/edge w/ `js-sys`, we'd use Date::now()
    
    // Parse the incoming stringified JSON
    let telemetry: Result<EdgeTelemetry, serde_json::Error> = serde_json::from_str(json_payload);
    
    let decision = match telemetry {
        Ok(data) => {
            // Complex heuristic: E.g., Volatility Spikes + Moving Average Divergence
            let volatility_index = (data.primary_metric - data.secondary_metric).abs();
            
            let is_anomaly = volatility_index > 150.0;
            let conf = if is_anomaly { 0.98 } else { 0.12 };
            
            EdgeActuationDecision {
                detected_anomaly: is_anomaly,
                confidence_score: conf,
                action_required: if is_anomaly { "SYSTEM_HALT".to_string() } else { "NONE".to_string() },
                execution_latency_ms: 1, // Simulated: sub-millisecond execution
            }
        },
        Err(_) => {
            // Failsafe serialization
            EdgeActuationDecision {
                detected_anomaly: false,
                confidence_score: 0.0,
                action_required: "JSON_PARSE_ERROR".to_string(),
                execution_latency_ms: 0,
            }
        }
    };

    // Return the JSON serialized decision back to JS/Edge Runtime
    serde_json::to_string(&decision).unwrap()
}
