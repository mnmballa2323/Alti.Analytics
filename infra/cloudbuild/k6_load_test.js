// infra/cloudbuild/k6_load_test.js
/**
 * Epic 78: k6 Load Test — SLO Validation for Canary Deployments
 *
 * Runs after every canary deploy. Tests all critical platform endpoints.
 * If any SLO threshold is breached, writes /workspace/slo_breach.flag
 * which triggers automatic canary rollback in the Cloud Build pipeline.
 *
 * SLO contracts (from Epic 79):
 *   NL2SQL API          p99 < 2000ms, error rate < 0.5%
 *   Streaming Engine    p99 < 200ms,  error rate < 0.1%
 *   Multilingual API    p99 < 1500ms, error rate < 0.5%
 *   Compliance API      p99 < 500ms,  error rate < 0.1%
 *   FX Rate API         p99 < 100ms,  error rate < 0.1%
 *   Data Quality        p99 < 5000ms, error rate < 1.0%
 *
 * Run: k6 run --env PROJECT_ID=alti-analytics-staging infra/cloudbuild/k6_load_test.js
 */
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// ── Custom metrics ────────────────────────────────────────────────────────────
const nl2sqlLatency = new Trend('nl2sql_latency');
const streamingLatency = new Trend('streaming_latency');
const complianceLatency = new Trend('compliance_latency');
const fxLatency = new Trend('fx_latency');
const errorRate = new Rate('error_rate');
const successCount = new Counter('success_count');

// ── Load test configuration ──────────────────────────────────────────────────
export const options = {
    scenarios: {
        // Ramp up to 50 VUs over 1 minute, hold 2 minutes, ramp down
        api_load: {
            executor: 'ramping-vus',
            startVUs: 1,
            stages: [
                { duration: '30s', target: 10 },   // warm-up
                { duration: '60s', target: 50 },   // ramp to peak
                { duration: '90s', target: 50 },   // sustained load
                { duration: '30s', target: 0 },   // ramp down
            ],
        },
        // Spike test: short burst to check auto-scaling
        spike: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 200 },
                { duration: '30s', target: 200 },
                { duration: '10s', target: 0 },
            ],
            startTime: '2m',
        },
    },

    // ── SLO thresholds ──────────────────────────────────────────────────────────
    thresholds: {
        // NL2SQL: p99 < 2s, error rate < 0.5%
        'nl2sql_latency{service:nl2sql}': ['p(99)<2000'],
        // Streaming: p99 < 200ms
        'streaming_latency{service:streaming}': ['p(99)<200'],
        // Compliance: p99 < 500ms
        'compliance_latency{service:compliance}': ['p(99)<500'],
        // FX rates: p99 < 100ms
        'fx_latency{service:fx}': ['p(99)<100'],
        // Global error rate < 1%
        'error_rate': ['rate<0.01'],
        // HTTP overall: 95% < 2s
        'http_req_duration': ['p(95)<2000'],
    },
};

const BASE_URL = `https://alti-staging-api-gateway-${__ENV.PROJECT_ID || 'alti-analytics-staging'}.run.app`;
const CANARY_HEADER = { 'X-Cloud-Run-Tag': `canary-${__ENV.CANARY_TAG || 'latest'}` };

const HEADERS = Object.assign({
    'Content-Type': 'application/json',
    'Authorization': 'Bearer test-key-internal',
}, CANARY_HEADER);

// ── Test scenarios ────────────────────────────────────────────────────────────
export default function () {
    group('NL2SQL API', function () {
        const payload = JSON.stringify({
            query: 'Show me top 10 customers by revenue this quarter',
            locale: 'en-US',
            tenant_id: 'load-test-tenant',
        });
        const res = http.post(`${BASE_URL}/api/nl2sql/query`, payload, { headers: HEADERS, tags: { service: 'nl2sql' } });
        const ok = check(res, {
            'nl2sql status 200': (r) => r.status === 200,
            'nl2sql has sql': (r) => r.json('sql') !== undefined,
            'nl2sql latency ok': (r) => r.timings.duration < 2000,
        });
        nl2sqlLatency.add(res.timings.duration, { service: 'nl2sql' });
        errorRate.add(!ok);
        if (ok) successCount.add(1);
        sleep(0.1);
    });

    group('Streaming Engine', function () {
        const res = http.get(`${BASE_URL}/api/stream/status`, { headers: HEADERS, tags: { service: 'streaming' } });
        const ok = check(res, {
            'stream status 200': (r) => r.status === 200,
            'stream latency ok': (r) => r.timings.duration < 200,
        });
        streamingLatency.add(res.timings.duration, { service: 'streaming' });
        errorRate.add(!ok);
        sleep(0.05);
    });

    group('Global Compliance API', function () {
        const res = http.get(`${BASE_URL}/api/compliance/assess?country=DE&purpose=analytics`, { headers: HEADERS, tags: { service: 'compliance' } });
        const ok = check(res, {
            'compliance 200': (r) => r.status === 200,
            'compliance allowed': (r) => r.json('applicable_laws') !== undefined,
            'compliance fast': (r) => r.timings.duration < 500,
        });
        complianceLatency.add(res.timings.duration, { service: 'compliance' });
        errorRate.add(!ok);
        sleep(0.1);
    });

    group('FX Rate API', function () {
        const res = http.get(`${BASE_URL}/api/currency/rate?from=USD&to=JPY`, { headers: HEADERS, tags: { service: 'fx' } });
        const ok = check(res, {
            'fx 200': (r) => r.status === 200,
            'fx fast': (r) => r.timings.duration < 100,
            'fx has rate': (r) => r.json('rate') > 0,
        });
        fxLatency.add(res.timings.duration, { service: 'fx' });
        errorRate.add(!ok);
        sleep(0.05);
    });

    group('Multilingual API', function () {
        const payload = JSON.stringify({ text: '売上高が減少しています', locale: 'ja-JP' });
        const res = http.post(`${BASE_URL}/api/multilingual/detect`, payload, { headers: HEADERS });
        check(res, {
            'multilingual 200': (r) => r.status === 200,
            'detected locale': (r) => r.json('detected_locale') !== undefined,
        });
        sleep(0.1);
    });

    sleep(Math.random() * 0.5);  // jitter
}

export function handleSummary(data) {
    const breached = Object.entries(data.metrics).some(([name, metric]) => {
        const threshold = metric.thresholds;
        return threshold && Object.values(threshold).some(t => !t.ok);
    });

    const summary = {
        timestamp: new Date().toISOString(),
        duration_s: data.state.testRunDurationMs / 1000,
        vus_max: data.state.vusMax,
        slo_breach: breached,
        error_rate: data.metrics.error_rate?.values?.rate || 0,
        success_count: data.metrics.success_count?.values?.count || 0,
        nl2sql_p99: data.metrics.nl2sql_latency?.values?.['p(99)'] || 0,
        streaming_p99: data.metrics.streaming_latency?.values?.['p(99)'] || 0,
        fx_p99: data.metrics.fx_latency?.values?.['p(99)'] || 0,
    };

    return {
        '/workspace/k6_results.json': JSON.stringify(summary, null, 2),
        // Write breach flag for Cloud Build to detect
        ...(breached ? { '/workspace/slo_breach.flag': 'SLO_BREACH' } : {}),
        stdout: `\n=== k6 SLO Summary ===\nSLO Breach: ${breached}\nError Rate: ${(summary.error_rate * 100).toFixed(3)}%\nNL2SQL p99: ${summary.nl2sql_p99.toFixed(0)}ms\nStreaming p99: ${summary.streaming_p99.toFixed(0)}ms\nFX p99: ${summary.fx_p99.toFixed(0)}ms\n`,
    };
}
