# Alti.Analytics

Enterprise Data, Analytics, and Intelligence Architecture.
Decision engine transforming raw operational and behavioral data into measurable business advantage.

## Architecture Highlights
- **Event-Driven Microservices**: Multi-AZ, Multi-Region deployment handling 500k+ events/sec
- **Data Lake (Medallion)**: GCS + Apache Iceberg with Bronze/Silver/Gold tiers
- **ML Platform**: Feature Store (Feast), Model Registry (MLflow), Model serving (NVIDIA Triton)
- **Generative AI**: Serverless RAG pipeline with cost tracking and guardrails

## Monorepo Layout
- `infra/`: Terraform, Helm charts, and GitOps configs
- `services/`: Microservices (Auth, User, Query Engine, API Gateway)
- `data/`: Batch ETL (Spark/Airflow), Data Warehouse (BigQuery) configurations
- `ml/`: Model training pipelines, Feature Store
- `docs/`: Architecture Decision Records (ADRs), runbooks, guidelines
- `.github/`: CI/CD definitions
