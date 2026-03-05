import os
import io
import json
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.generative_models import GenerativeModel

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
LOCATION = os.getenv("GCP_REGION", "us-central1")
PROCESSOR_ID = os.getenv("DOC_AI_PROCESSOR_ID", "mock-processor-123")
OUTPUT_BUCKET = os.getenv("GCS_VECTOR_STAGING", "alti-analytics-dev-vector-staging")

def process_document(bucket_name: str, object_name: str):
    """
    Triggered by a GCS event. Reads a PDF, extracts text via Document AI,
    summarizes it with Gemini, and generates an embedding vector.
    """
    print(f"Processing new document: gs://{bucket_name}/{object_name}")
    
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    image_content = blob.download_as_bytes()

    # 1. Google Document AI Extraction
    docai_client = documentai.DocumentProcessorServiceClient()
    name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
    
    raw_document = documentai.RawDocument(content=image_content, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    
    try:
        # In a real deployed environment with a trained processor
        # result = docai_client.process_document(request=request)
        # document_text = result.document.text
        
        # Scaffolded Mock Result
        document_text = "Scouting Report snippet: Player 10 consistently makes blind-side runs behind the left-back when the holding midfielder is drawn out of position."
    except Exception as e:
        print(f"Document AI Failed (using mock data): {e}")
        document_text = "Detailed medical evaluation: Player exhibits grade 1 hamstring tightness. Expected recovery: 4 days."

    # 2. Gemini Summarization & Context Enrichment
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    gemini = GenerativeModel("gemini-1.5-pro")
    
    prompt = f"Summarize the following unstructured document into a dense tactical or medical insight paragraph suitable for vector search retrieval:\n\n{document_text}"
    # summary_response = gemini.generate_content(prompt)
    # clean_summary = summary_response.text
    clean_summary = f"Synthesized Document Insight: {document_text}"
    
    # 3. Text Embedding Generation
    embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    # embeddings = embedding_model.get_embeddings([clean_summary])
    # vector_data = embeddings[0].values
    vector_data = [0.12, -0.45, 0.88, 0.01] # Mock 768-dim vector

    # 4. Sink to Vector Staging (to be picked up by Vertex Vector Search Index)
    output_payload = {
        "id": object_name.replace("/", "_").replace(".pdf", ""),
        "embedding": vector_data,
        "restricts": [{"namespace": "doc_type", "allow": ["scouting_report"]}],
        "metadata": {
            "source_uri": f"gs://{bucket_name}/{object_name}",
            "summary": clean_summary
        }
    }
    
    output_blob_name = f"embeddings/{object_name}.json"
    out_blob = storage_client.bucket(OUTPUT_BUCKET).blob(output_blob_name)
    out_blob.upload_from_string(json.dumps(output_payload))
    
    print(f"Document embedded and staged: gs://{OUTPUT_BUCKET}/{output_blob_name}")

if __name__ == "__main__":
    # Local Test Execution
    process_document("alti-analytics-dev-raw-docs", "scouting/opponent_q3_report.pdf")
