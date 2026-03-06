# services/time-travel/iceberg_time_travel.py
"""
Epic 60: Data Versioning & Time Travel
Apache Iceberg table format on Cloud Storage provides:
- ACID transactions: concurrent reads/writes never see partial state
- Snapshot isolation: every write creates an immutable, addressable snapshot
- Time travel queries: AS OF any timestamp up to 90 days back
- Data branching: isolated experiment branches diverging from production
- Snapshot diffs: row-level change summaries with Gemini narrative

Eliminates the "which data was the dashboard showing on Tuesday?" problem
that causes hours of incident investigation today.
"""
import logging, json, uuid, time, copy, random
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class IcebergSnapshot:
    snapshot_id:  str
    table_name:   str
    created_at:   float
    operation:    str         # APPEND | OVERWRITE | DELETE | REPLACE
    added_rows:   int
    deleted_rows: int
    manifest_list: str        # GCS URI of manifest list file
    schema_version: int
    parent_id:    Optional[str] = None
    branch:       str = "main"
    committed_by: str = "system"
    summary:      dict = field(default_factory=dict)

@dataclass
class DataBranch:
    branch_id:   str
    name:        str
    base_snapshot_id: str
    table_name:  str
    created_at:  float
    created_by:  str
    description: str
    snapshots:   list[str] = field(default_factory=list)  # snapshot IDs on this branch

@dataclass
class SnapshotDiff:
    from_snapshot: str
    to_snapshot:   str
    table_name:    str
    added_rows:    int
    deleted_rows:  int
    changed_rows:  int
    schema_changes: list[dict]
    sample_changes: list[dict]   # row-level sample
    gemini_narrative: str
    computed_at:   float = field(default_factory=time.time)

@dataclass
class TimeTravelQuery:
    query_id:       str
    table_name:     str
    as_of_ts:       float
    resolved_snapshot_id: str
    row_count:      int
    execution_ms:   float
    columns:        list[str]
    sample_rows:    list[dict]

class IcebergTimeTravelEngine:
    """
    Manages Iceberg table metadata server-side.
    In production:
    - Snapshot metadata in Cloud Spanner (globally consistent reads)
    - Data files (Parquet) on Cloud Storage in Iceberg format
    - BigQuery Iceberg external tables for SQL access
    - Catalog service: Apache REST Catalog API
    """
    MAX_SNAPSHOT_AGE_DAYS = 90
    MAX_BRANCHES = 20

    def __init__(self):
        self.logger = logging.getLogger("Iceberg_TimeTravel")
        logging.basicConfig(level=logging.INFO)
        self._snapshots: dict[str, list[IcebergSnapshot]] = {}   # table → [snapshots]
        self._branches:  dict[str, list[DataBranch]]      = {}   # table → [branches]
        self.logger.info("🧊 Apache Iceberg Time Travel Engine initialized.")
        self._seed_history()

    def _seed_history(self):
        """Seed realistic snapshot history for key tables."""
        tables = [
            ("salesforce.customers",          12_480, 340),
            ("stripe.charges",                4_820_000, 82000),
            ("analytics.monthly_revenue_summary", 48, 4),
        ]
        for table, rows, daily_new in tables:
            snaps = []
            parent = None
            # 30 days of history, ~3 snapshots/day
            for day in range(30, -1, -1):
                for _ in range(random.randint(2, 4)):
                    ts = time.time() - day * 86400 - random.randint(0, 82800)
                    snap = IcebergSnapshot(
                        snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
                        table_name=table, created_at=ts,
                        operation=random.choice(["APPEND", "APPEND", "APPEND", "OVERWRITE"]),
                        added_rows=random.randint(10, daily_new),
                        deleted_rows=random.randint(0, max(1, daily_new // 20)),
                        manifest_list=f"gs://alti-iceberg/{table.replace('.','/')}/metadata/snap-{uuid.uuid4().hex[:8]}.json",
                        schema_version=1, parent_id=parent, branch="main"
                    )
                    snaps.append(snap)
                    parent = snap.snapshot_id
            self._snapshots[table] = sorted(snaps, key=lambda s: s.created_at)
            # Main branch
            self._branches[table] = [DataBranch(
                branch_id="br-main", name="main",
                base_snapshot_id=snaps[0].snapshot_id,
                table_name=table, created_at=snaps[0].created_at,
                created_by="system", description="Production main branch",
                snapshots=[s.snapshot_id for s in snaps]
            )]
        self.logger.info(f"✅ Seeded {sum(len(v) for v in self._snapshots.values())} snapshots across {len(self._snapshots)} tables.")

    def query_as_of(self, table_name: str, as_of_ts: float) -> TimeTravelQuery:
        """
        Returns a query result from the table as it existed at `as_of_ts`.
        Resolves the latest snapshot committed at or before the given timestamp.
        In production: BigQuery syntax — SELECT * FROM table FOR SYSTEM_TIME AS OF TIMESTAMP(...)
        """
        snaps = self._snapshots.get(table_name, [])
        resolved = next((s for s in reversed(snaps) if s.created_at <= as_of_ts), None)
        if not resolved:
            raise ValueError(f"No snapshot found for '{table_name}' at {as_of_ts}")

        # Simulate row count at that point in time
        snap_idx = next(i for i, s in enumerate(snaps) if s.snapshot_id == resolved.snapshot_id)
        historical_rows = max(0, sum(s.added_rows - s.deleted_rows for s in snaps[:snap_idx+1]))
        time_label = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(as_of_ts))
        self.logger.info(f"⏪ Time travel: '{table_name}' AS OF {time_label} → {historical_rows:,} rows")

        # Synthetic sample rows
        sample = [{"customer_id": f"CUST-{1000+i}", "name": f"Company {chr(65+i)}", "churn_risk": round(random.uniform(0.1, 0.9), 2)}
                  for i in range(3)]
        return TimeTravelQuery(
            query_id=str(uuid.uuid4()), table_name=table_name,
            as_of_ts=as_of_ts, resolved_snapshot_id=resolved.snapshot_id,
            row_count=historical_rows, execution_ms=round(random.uniform(120, 480), 1),
            columns=["customer_id", "name", "churn_risk"], sample_rows=sample
        )

    def create_branch(self, table_name: str, branch_name: str,
                      based_on: Optional[str] = None, created_by: str = "user",
                      description: str = "") -> DataBranch:
        """
        Creates an isolated data branch from the latest (or specified) snapshot.
        The branch shares all existing data files (zero-copy — just metadata pointers).
        Writes to the branch never touch main until an explicit merge.
        """
        snaps = self._snapshots.get(table_name, [])
        if not snaps:
            raise ValueError(f"Table '{table_name}' not found in catalog")
        base = based_on or snaps[-1].snapshot_id
        branch = DataBranch(
            branch_id=f"br-{uuid.uuid4().hex[:8]}", name=branch_name,
            base_snapshot_id=base, table_name=table_name,
            created_at=time.time(), created_by=created_by,
            description=description or f"Experiment branch from snapshot {base[:8]}"
        )
        self._branches.setdefault(table_name, []).append(branch)
        self.logger.info(f"🌿 Branch '{branch_name}' created on '{table_name}' (zero-copy, base={base[:12]})")
        return branch

    def diff(self, table_name: str, from_ts: float, to_ts: float) -> SnapshotDiff:
        """
        Computes the difference between two table snapshots.
        Returns row-level change summary and a Gemini narrative.
        """
        snaps = self._snapshots.get(table_name, [])
        from_snap = next((s for s in reversed(snaps) if s.created_at <= from_ts), snaps[0])
        to_snap   = next((s for s in reversed(snaps) if s.created_at <= to_ts),   snaps[-1])

        # Aggregate changes between the two snapshots
        in_range = [s for s in snaps if from_snap.created_at <= s.created_at <= to_snap.created_at]
        added    = sum(s.added_rows   for s in in_range)
        deleted  = sum(s.deleted_rows for s in in_range)
        changed  = len(in_range)
        schema_changes: list[dict] = []   # In production: parse manifest schema evolution

        sample_changes = [
            {"row_id": f"CUST-{random.randint(1000,9999)}", "change": "UPDATE",
             "before": {"churn_risk": round(random.uniform(0.3, 0.5), 2)},
             "after":  {"churn_risk": round(random.uniform(0.6, 0.9), 2)}},
            {"row_id": f"CUST-{random.randint(1000,9999)}", "change": "INSERT",
             "before": None, "after": {"name": "NewCo Inc", "churn_risk": 0.15}},
        ]

        # Gemini narrative of what changed
        from_label = time.strftime("%b %d %H:%M", time.gmtime(from_ts))
        to_label   = time.strftime("%b %d %H:%M", time.gmtime(to_ts))
        narrative  = (
            f"Between {from_label} and {to_label}, the table '{table_name}' received "
            f"{added:,} new rows and {deleted:,} deletions across {changed} write operations. "
        )
        if added > deleted:
            narrative += f"Net growth was +{added - deleted:,} rows. "
        if any(s.operation == "OVERWRITE" for s in in_range):
            narrative += "⚠️ One or more OVERWRITE operations were detected — full table replacement occurred during this window. "
        narrative += (
            f"Sample changes include churn_risk score updates for existing accounts "
            f"and {sum(1 for c in sample_changes if c['change'] == 'INSERT')} new customer additions."
        )

        return SnapshotDiff(
            from_snapshot=from_snap.snapshot_id, to_snapshot=to_snap.snapshot_id,
            table_name=table_name, added_rows=added, deleted_rows=deleted,
            changed_rows=changed, schema_changes=schema_changes,
            sample_changes=sample_changes, gemini_narrative=narrative
        )

    def list_snapshots(self, table_name: str, limit: int = 10) -> list[dict]:
        snaps = self._snapshots.get(table_name, [])[-limit:]
        return [{
            "snapshot_id": s.snapshot_id[:16] + "…",
            "created_at":  time.strftime("%Y-%m-%d %H:%M", time.gmtime(s.created_at)),
            "operation":   s.operation,
            "added":       s.added_rows,
            "deleted":     s.deleted_rows,
            "branch":      s.branch
        } for s in reversed(snaps)]


if __name__ == "__main__":
    engine = IcebergTimeTravelEngine()

    # Time travel query — as of 7 days ago
    as_of = time.time() - 7 * 86400
    result = engine.query_as_of("salesforce.customers", as_of)
    print(f"⏪ AS OF 7 days ago: {result.row_count:,} rows | snapshot: {result.resolved_snapshot_id[:16]}")
    print(f"   Execution: {result.execution_ms}ms")

    # Create experiment branch
    branch = engine.create_branch(
        "salesforce.customers", "experiment/new-churn-model",
        created_by="data-scientist@alti.ai",
        description="Testing new XGBoost v4 feature set without impacting production"
    )
    print(f"\n🌿 Branch: {branch.name} (id={branch.branch_id})")

    # Diff last 24h
    diff = engine.diff("salesforce.customers", time.time() - 86400, time.time())
    print(f"\n📊 24h diff: +{diff.added_rows} rows, -{diff.deleted_rows} rows")
    print(f"💬 {diff.gemini_narrative}")

    # Recent snapshots
    print("\nRecent snapshots:")
    for s in engine.list_snapshots("salesforce.customers", 5):
        print(f"  {s['created_at']}  {s['operation']:10}  +{s['added']:5} -{s['deleted']:4}  [{s['branch']}]")
