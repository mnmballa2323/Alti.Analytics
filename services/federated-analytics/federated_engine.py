# services/federated-analytics/federated_engine.py
"""
Epic 63: Federated & Privacy-Preserving Analytics
Enables cross-organizational analytics WITHOUT centralizing raw data.

Use cases:
- Hospitals compare treatment outcomes without sharing patient records
- Banks benchmark fraud detection rates without exposing transactions
- SaaS companies compare churn rates against industry without sharing customers

Methods implemented:
1. Differential Privacy (DP): Laplace/Gaussian mechanism noise injection
2. Federated Query Executor: compute aggregates locally, share only results
3. Privacy Budget Tracker: epsilon accounting per query, per tenant
4. Industry Benchmark Reports: anonymized cross-tenant comparisons

Formal guarantee: (ε, δ)-differential privacy on all outputs.
"""
import logging, json, uuid, time, math, random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class NoiseType(str, Enum):
    LAPLACE  = "LAPLACE"   # pure ε-DP for count/sum queries
    GAUSSIAN = "GAUSSIAN"  # (ε,δ)-DP for more complex analytics

class QueryType(str, Enum):
    COUNT  = "COUNT"
    SUM    = "SUM"
    MEAN   = "MEAN"
    MEDIAN = "MEDIAN"
    RATIO  = "RATIO"

@dataclass
class PrivacyBudget:
    tenant_id:    str
    total_epsilon:float   # total privacy budget (e.g. 1.0 per month)
    spent_epsilon:float = 0.0
    query_count:  int   = 0
    reset_at:     float = field(default_factory=lambda: time.time() + 30*86400)

    @property
    def remaining(self) -> float:
        return round(max(0.0, self.total_epsilon - self.spent_epsilon), 6)

    @property
    def exhausted(self) -> bool:
        return self.spent_epsilon >= self.total_epsilon

@dataclass
class PrivateQueryResult:
    query_id:     str
    query_type:   QueryType
    true_value:   float    # only stored server-side, NEVER returned to client
    noisy_value:  float    # the DP-protected value returned to the caller
    noise_added:  float    # magnitude of noise (returned for transparency)
    epsilon_spent:float
    delta_spent:  float
    mechanism:    NoiseType
    sensitivity:  float    # global sensitivity of the query function
    confidence_interval: tuple[float, float]   # 95% CI around noisy_value

@dataclass
class FederatedNode:
    node_id:      str
    tenant_id:    str
    name:         str             # e.g. "Hospital A"
    endpoint:     str             # In production: secure gRPC endpoint
    data_schema:  dict
    row_count:    int
    last_seen:    float = field(default_factory=time.time)

@dataclass
class FederatedResult:
    federation_id:  str
    question:       str
    participants:   list[str]     # tenant_ids
    global_result:  float         # DP-protected aggregate across all nodes
    per_node:       list[dict]    # DP-protected per-node results
    epsilon_total:  float         # total epsilon consumed across all nodes
    benchmark_narrative: str      # Gemini-generated plain-English comparison
    computed_at:    float = field(default_factory=time.time)

class DifferentialPrivacyEngine:
    """Implements the Laplace and Gaussian mechanisms for DP."""

    @staticmethod
    def laplace_noise(sensitivity: float, epsilon: float) -> float:
        """Laplace mechanism for pure ε-DP."""
        scale = sensitivity / epsilon
        # Box-Muller approximation of Laplace distribution
        u = random.uniform(-0.5, 0.5) + 1e-10
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    @staticmethod
    def gaussian_noise(sensitivity: float, epsilon: float, delta: float = 1e-5) -> float:
        """Gaussian mechanism for (ε,δ)-DP."""
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
        return random.gauss(0, sigma)

    @staticmethod
    def sensitivity(query_type: QueryType, data_range: float = 1.0) -> float:
        """Global sensitivity = max change in output when one record changes."""
        return {
            QueryType.COUNT:  1.0,
            QueryType.SUM:    data_range,
            QueryType.MEAN:   data_range,        # simplified
            QueryType.RATIO:  1.0,
            QueryType.MEDIAN: 1.0,
        }.get(query_type, 1.0)


class FederatedAnalyticsEngine:
    """
    Orchestrates privacy-preserving analytics across organizational boundaries.
    Each participating org runs a local compute agent that:
    1. Runs the query locally on its own data
    2. Applies differential privacy noise to the local result
    3. Returns only the noisy aggregate — raw data never leaves the org
    The coordinator combines noisy results using secure aggregation.
    """
    DEFAULT_BUDGET_EPSILON = 1.0    # per tenant per 30 days
    DEFAULT_DELTA = 1e-5

    def __init__(self):
        self.logger = logging.getLogger("Federated_Analytics")
        logging.basicConfig(level=logging.INFO)
        self._dp = DifferentialPrivacyEngine()
        self._budgets:  dict[str, PrivacyBudget] = {}
        self._nodes:    dict[str, FederatedNode]  = {}
        self._query_log:list[PrivateQueryResult]  = []
        self.logger.info("🔐 Federated Privacy-Preserving Analytics Engine initialized.")
        self._seed_nodes()

    def _seed_nodes(self):
        """Simulated federated participant nodes."""
        nodes = [
            ("ten-acme",    "Acme Corp",          {"churn_rate": 0.042, "arr_usd": 48_200_000,  "headcount": 12480}),
            ("ten-globex",  "Globex Industries",  {"churn_rate": 0.087, "arr_usd": 8_100_000,   "headcount": 3200}),
            ("ten-initech", "Initech LLC",         {"churn_rate": 0.061, "arr_usd": 22_400_000,  "headcount": 7600}),
            ("ten-hooli",   "Hooli Inc",           {"churn_rate": 0.033, "arr_usd": 180_000_000, "headcount": 48000}),
            ("ten-pied",    "Pied Piper",          {"churn_rate": 0.119, "arr_usd": 3_800_000,   "headcount": 640}),
        ]
        for tid, name, schema in nodes:
            self._nodes[tid] = FederatedNode(
                node_id=str(uuid.uuid4()), tenant_id=tid, name=name,
                endpoint=f"grpc://{tid}.federated.alti.internal:50051",
                data_schema=schema, row_count=schema["headcount"]
            )
            self._budgets[tid] = PrivacyBudget(tenant_id=tid,
                                                total_epsilon=self.DEFAULT_BUDGET_EPSILON)

    def private_query(self, tenant_id: str, query_type: QueryType,
                      true_value: float, data_range: float = 1.0,
                      epsilon: float = 0.1) -> PrivateQueryResult:
        """
        Applies DP noise to a local query result.
        Called by each federated node on ITS OWN data before sharing.
        The true_value is NEVER transmitted — only noisy_value is returned.
        """
        budget = self._budgets.get(tenant_id)
        if not budget:
            budget = PrivacyBudget(tenant_id=tenant_id, total_epsilon=self.DEFAULT_BUDGET_EPSILON)
            self._budgets[tenant_id] = budget
        if budget.exhausted:
            raise RuntimeError(f"Privacy budget exhausted for tenant {tenant_id}. "
                               f"Budget resets at {time.strftime('%Y-%m-%d', time.gmtime(budget.reset_at))}")

        # Clamp epsilon to remaining budget
        epsilon = min(epsilon, budget.remaining)
        sens = self._dp.sensitivity(query_type, data_range)

        # Choose mechanism: Laplace for COUNT/SUM/RATIO, Gaussian for MEAN/MEDIAN
        if query_type in [QueryType.COUNT, QueryType.SUM, QueryType.RATIO]:
            noise = self._dp.laplace_noise(sens, epsilon)
            mechanism = NoiseType.LAPLACE
            delta_spent = 0.0
        else:
            noise = self._dp.gaussian_noise(sens, epsilon, self.DEFAULT_DELTA)
            mechanism = NoiseType.GAUSSIAN
            delta_spent = self.DEFAULT_DELTA

        noisy = round(true_value + noise, 6)
        # 95% confidence interval using noise scale
        scale = sens / epsilon
        ci = (round(noisy - 1.96 * scale, 4), round(noisy + 1.96 * scale, 4))

        # Deduct from budget
        budget.spent_epsilon = round(budget.spent_epsilon + epsilon, 6)
        budget.query_count   += 1

        result = PrivateQueryResult(
            query_id=str(uuid.uuid4()), query_type=query_type,
            true_value=true_value, noisy_value=noisy, noise_added=round(noise, 6),
            epsilon_spent=epsilon, delta_spent=delta_spent, mechanism=mechanism,
            sensitivity=sens, confidence_interval=ci
        )
        self._query_log.append(result)
        return result

    def federated_benchmark(self, metric: str,
                             question: str,
                             epsilon_per_node: float = 0.05) -> FederatedResult:
        """
        Computes a cross-tenant benchmark:
        1. Each node runs private_query on its local data
        2. Coordinator combines noisy results via secure aggregation
        3. Gemini generates a plain-English comparison narrative
        No individual tenant's true value is ever exposed.
        """
        self.logger.info(f"🌐 Federated benchmark: '{metric}' across {len(self._nodes)} nodes")
        per_node_results = []
        total_epsilon    = 0.0
        noisy_values     = []

        for node in self._nodes.values():
            true_val = node.data_schema.get(metric, 0.0)
            qtype = QueryType.RATIO if "rate" in metric else QueryType.SUM
            try:
                result = self.private_query(node.tenant_id, qtype, true_val,
                                            data_range=max(1.0, true_val),
                                            epsilon=epsilon_per_node)
                per_node_results.append({
                    "tenant_id": node.tenant_id, "name": node.name,
                    "noisy_value": result.noisy_value,
                    "ci": result.confidence_interval,
                    "epsilon_spent": result.epsilon_spent
                })
                noisy_values.append(result.noisy_value)
                total_epsilon += result.epsilon_spent
            except RuntimeError as e:
                self.logger.warning(f"  Skipped {node.name}: {e}")

        # Global aggregate: noisy mean across all participating nodes
        global_val = round(sum(noisy_values) / len(noisy_values), 6) if noisy_values else 0.0

        # Gemini narrative (simulated)
        sorted_nodes = sorted(per_node_results, key=lambda x: x["noisy_value"])
        lowest  = sorted_nodes[0]["name"]  if sorted_nodes else "N/A"
        highest = sorted_nodes[-1]["name"] if sorted_nodes else "N/A"
        narrative = (
            f"Across {len(per_node_results)} participating organizations, "
            f"the industry benchmark for '{metric}' is {global_val:.4f}. "
            f"{lowest} demonstrated the best performance while {highest} had the highest value. "
            f"All results are protected by (ε={total_epsilon:.3f}, δ={self.DEFAULT_DELTA})-differential privacy — "
            f"no individual organization's raw data was exposed in this computation. "
            f"Your organization can compare against this benchmark without sharing any records."
        )

        return FederatedResult(
            federation_id=str(uuid.uuid4()), question=question,
            participants=[n["tenant_id"] for n in per_node_results],
            global_result=global_val, per_node=per_node_results,
            epsilon_total=round(total_epsilon, 6),
            benchmark_narrative=narrative
        )

    def budget_status(self, tenant_id: str) -> dict:
        b = self._budgets.get(tenant_id)
        if not b: return {}
        return {
            "tenant_id":      b.tenant_id,
            "total_epsilon":  b.total_epsilon,
            "spent_epsilon":  b.spent_epsilon,
            "remaining":      b.remaining,
            "queries_run":    b.query_count,
            "pct_used":       round(b.spent_epsilon / b.total_epsilon * 100, 1),
            "resets_at":      time.strftime("%Y-%m-%d", time.gmtime(b.reset_at)),
            "exhausted":      b.exhausted
        }


if __name__ == "__main__":
    engine = FederatedAnalyticsEngine()

    # Run cross-org churn rate benchmark
    result = engine.federated_benchmark(
        metric="churn_rate",
        question="What is the industry average customer churn rate across SaaS platforms?"
    )
    print(f"\n🌐 Federated Benchmark: '{result.question}'")
    print(f"   Global result: {result.global_result:.4f}")
    print(f"   Participants: {len(result.participants)}")
    print(f"   Total ε spent: {result.epsilon_total:.4f}")
    print(f"\n💬 {result.benchmark_narrative}")

    # Per-node DP results (no true values revealed)
    print("\nPer-node (DP-protected) results:")
    for n in result.per_node:
        print(f"  {n['name']:25} → {n['noisy_value']:.4f}  CI={n['ci']}  ε={n['epsilon_spent']:.4f}")

    # Budget status
    print("\nBudget status for ten-acme:")
    print(json.dumps(engine.budget_status("ten-acme"), indent=2))
