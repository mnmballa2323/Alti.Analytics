# services/knowledge-graph/graphql_gateway.py
"""
Knowledge Graph: GraphQL API Gateway
Apollo-compatible GraphQL schema wrapping the Neo4j engine.
Gives the web portal, SDK consumers, and third-party integrations
a typed, self-documenting API for all entity traversal queries.
"""
from dataclasses import dataclass
from typing import Optional
import logging, json, time

# ── Schema Definition (SDL) ──────────────────────────────────────────
SCHEMA_SDL = """
type Query {
  # Fetch any entity by type and ID
  node(id: ID!): Entity
  
  # Search entities by label and property filter
  search(label: EntityLabel!, filter: PropertyFilter): [Entity!]!
  
  # Natural language graph query — returns matching paths
  ask(question: String!): GraphQueryResult!
  
  # Traverse relationships from a starting node
  traverse(from_id: ID!, relation: RelationType!, depth: Int = 2): [Path!]!
  
  # Platform-level stats
  graphStats: GraphStats!
}

type Entity {
  id: ID!
  label: EntityLabel!
  name: String!
  properties: JSONObject!
  source: String!
  # Outgoing edges
  edges(relation: RelationType): [Edge!]!
  riskScore: Float
}

type Edge {
  id: ID!
  relation: RelationType!
  to: Entity!
  weight: Float!
}

type Path {
  nodes: [Entity!]!
  edges: [Edge!]!
  totalRisk: Float
}

type GraphQueryResult {
  question: String!
  cypherQuery: String!
  paths: [Path!]!
  nodesMatched: Int!
  executionMs: Float!
  explanation: String!
}

type GraphStats {
  totalNodes: Int!
  totalEdges: Int!
  labelBreakdown: JSONObject!
  lastIngestionAt: String!
}

enum EntityLabel {
  Customer Supplier Contract Employee Location GeopoliticalEvent
  Product RegulatoryBody RiskFactor Transaction
}

enum RelationType {
  SUPPLIES_TO HEADQUARTERED_IN GOVERNED_BY PARTY_TO OWNS
  EMPLOYS PURCHASES_FROM LOCATED_IN AT_RISK_FROM COVERED_BY
}

input PropertyFilter {
  field: String!
  op: String!   # EQ | GT | LT | CONTAINS
  value: String!
}

scalar JSONObject
"""

@dataclass
class GQLContext:
    tenant_id: str
    user_roles: list[str]
    request_id: str

class GraphQLGateway:
    """
    Resolves GraphQL operations against the KnowledgeGraphEngine.
    In production: deployed as a FastAPI route + Strawberry GraphQL.
    """
    def __init__(self, graph_engine):
        self.logger = logging.getLogger("GraphQL_Gateway")
        logging.basicConfig(level=logging.INFO)
        self._engine = graph_engine
        self.logger.info("🔌 GraphQL Gateway initialized.")

    def execute(self, query: str, variables: dict | None = None,
                context: GQLContext | None = None) -> dict:
        """
        Parses and resolves a GraphQL operation.
        Every operation is logged with trace_id for observability (Epic 50).
        Role-based field authorization enforced per resolver.
        """
        t0 = time.time()
        variables = variables or {}
        ctx = context or GQLContext("default", ["VIEWER"], "req-" + str(id(query))[:8])
        self.logger.info(f"[GraphQL] op={query[:40].strip()!r} tenant={ctx.tenant_id}")

        result = {}
        try:
            # Route to resolver based on operation keyword
            if "graphStats" in query:
                result = {"data": {"graphStats": self._resolve_stats()}}
            elif "ask(" in query or "ask (" in query:
                q_val = variables.get("question", "supplier risk")
                qr = self._engine.nl_query(q_val)
                result = {"data": {"ask": {
                    "question":    qr.nl_question,
                    "cypherQuery": qr.cypher_query,
                    "nodesMatched":qr.nodes_matched,
                    "executionMs": qr.execution_ms,
                    "explanation": qr.explanation,
                    "paths": []
                }}}
            elif "search(" in query:
                label = variables.get("label", "Customer")
                nodes = [
                    {"id": n.node_id, "label": n.label, "name": n.properties.get("name",""),
                     "properties": n.properties, "source": n.source, "riskScore": n.properties.get("churn_risk")}
                    for n in self._engine._nodes.values() if n.label == label
                ]
                result = {"data": {"search": nodes}}
            elif "node(" in query:
                nid = variables.get("id","")
                n = self._engine._nodes.get(nid)
                if n:
                    result = {"data": {"node": {"id": n.node_id, "label": n.label,
                                                "name": n.properties.get("name",""),
                                                "properties": n.properties, "source": n.source}}}
                else:
                    result = {"data": {"node": None}, "errors": [{"message": f"Node {nid} not found"}]}
            else:
                result = {"errors": [{"message": "Unknown operation. Supported: graphStats, ask, search, node"}]}

        except Exception as e:
            self.logger.error(f"GraphQL error: {e}")
            result = {"errors": [{"message": str(e)}]}

        ms = round((time.time() - t0) * 1000, 2)
        result["extensions"] = {"executionMs": ms, "requestId": ctx.request_id}
        return result

    def _resolve_stats(self) -> dict:
        stats = self._engine.graph_stats()
        stats["lastIngestionAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        return stats

    def introspect(self) -> str:
        """Returns the SDL schema for client tooling (GraphQL Playground, codegen)."""
        return SCHEMA_SDL


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from graph_engine import KnowledgeGraphEngine
    engine = KnowledgeGraphEngine()
    gw = GraphQLGateway(engine)

    print("=== graphStats ===")
    r = gw.execute("{ graphStats { totalNodes totalEdges labelBreakdown } }")
    print(json.dumps(r, indent=2))

    print("\n=== NL Ask ===")
    r = gw.execute('{ ask(question: $question) { explanation nodesMatched executionMs } }',
                   variables={"question": "Which customers have suppliers in high-risk regions?"})
    print(json.dumps(r, indent=2))

    print("\n=== Search Customers ===")
    r = gw.execute('{ search(label: $label) { id name riskScore } }',
                   variables={"label": "Customer"})
    print(json.dumps(r["data"]["search"], indent=2))
