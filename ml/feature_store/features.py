from datetime import timedelta
from feast import Entity, FeatureView, Field, ValueType
from feast.infra.offline_stores.bigquery import BigQuerySource
from feast.types import Float32, Int64, String

# Entity defining the primary key for the features
user = Entity(
    name="user_id",
    join_keys=["user_id"],
    description="User identifier",
)

# BigQuery Offline Source
user_stats_source = BigQuerySource(
    table="alti-analytics-prod.alti_analytics_prod.user_stats",
    event_timestamp_column="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# Feature View defining the features available
user_stats_fv = FeatureView(
    name="user_transaction_stats",
    entities=[user],
    ttl=timedelta(days=30),
    schema=[
        Field(name="total_transactions_30d", dtype=Int64),
        Field(name="total_spend_30d", dtype=Float32),
        Field(name="churn_risk_score", dtype=Float32),
    ],
    online=True,
    source=user_stats_source,
    tags={"team": "analytics"},
)
