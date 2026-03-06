# services/voice-multimodal/voice_analytics.py
"""
Epic 67: Voice & Multimodal Analytics
Alti becomes truly conversational — speak to your data, show it images,
drop in PDFs — and get narrated intelligent answers back.

Pipeline:
  Voice → Cloud Speech-to-Text v2 → NL2SQL (Epic 47) → Query → Result
  Result → Gemini narration → Cloud TTS → Spoken response + Chart URL

Multimodal inputs:
  PDF/XLSX  → Document AI extraction → virtual table → queryable
  Image     → Gemini Vision → structured description → query context
  Whiteboard photo → Gemini Vision → extract KPIs → compare to live data
  Competitor ad    → Vision + NLP  → campaign signal → enrich analytics
"""
import logging, json, uuid, time, base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class InputModality(str, Enum):
    VOICE    = "VOICE"
    TEXT     = "TEXT"
    PDF      = "PDF"
    IMAGE    = "IMAGE"
    SPREADSHEET = "SPREADSHEET"
    URL      = "URL"

class ResponseFormat(str, Enum):
    SPOKEN   = "SPOKEN"    # TTS audio + chart URL
    CARD     = "CARD"      # structured card with metric + chart
    TABLE    = "TABLE"     # tabular data
    NARRATIVE= "NARRATIVE" # prose paragraph

@dataclass
class MultimodalInput:
    input_id:   str
    modality:   InputModality
    raw:        bytes | str          # audio bytes / text / base64 image / file bytes
    metadata:   dict = field(default_factory=dict)
    received_at:float = field(default_factory=time.time)

@dataclass
class ExtractedContext:
    """What Gemini extracted from a non-text input before querying."""
    input_id:   str
    text_repr:  str              # text representation of the input
    entities:   list[dict]       # extracted entities (metrics, dates, names)
    intent:     str              # detected user intent
    confidence: float
    modality:   InputModality

@dataclass
class VoiceQueryResult:
    query_id:      str
    original_input:str           # transcribed or raw text
    sql_generated: str
    answer_text:   str           # plain-English answer
    spoken_audio_uri: str        # GCS URI of TTS audio
    chart_url:     str           # URL to auto-generated chart
    data_rows:     list[dict]    # raw query results
    latency_ms:    float
    modality:      InputModality

class SpeechProcessor:
    """
    Wraps Cloud Speech-to-Text v2.
    Supports: en-US, es-ES, fr-FR, de-DE, ja-JP, zh-Hans, pt-BR, ar-SA,
              hi-IN, ko-KR — 10 languages for global reach.
    """
    SUPPORTED_LANGS = ["en-US","es-ES","fr-FR","de-DE","ja-JP",
                       "zh-Hans","pt-BR","ar-SA","hi-IN","ko-KR"]

    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> dict:
        """
        In production: POST to Cloud Speech-to-Text v2 Streaming Recognition.
        Simulated here — returns realistic transcript with word-level confidence.
        """
        # Simulated transcripts for demo
        demo_transcripts = [
            "Why is my churn rate up this month",
            "Show me revenue by region for the last quarter",
            "What is the readmission rate for cardiac patients",
            "Which customers are at highest risk of churning",
            "Compare this quarter's sales to last year",
            "What happened to fraud detection rate yesterday",
        ]
        transcript = demo_transcripts[hash(str(audio_bytes)) % len(demo_transcripts)]
        return {
            "transcript":  transcript,
            "confidence":  round(0.92 + (hash(transcript) % 8) * 0.01, 3),
            "language":    language,
            "duration_ms": len(audio_bytes) // 160 if audio_bytes else 1200,
            "words": [{"word": w, "confidence": 0.93} for w in transcript.split()]
        }


class DocumentIntelligence:
    """
    Extracts structured data from uploaded documents.
    PDF  → Document AI form parser + layout parser
    XLSX → pandas read_excel (simulated)
    Image → Gemini Vision
    """
    def extract_pdf(self, pdf_bytes: bytes, filename: str = "document.pdf") -> dict:
        """
        Cloud Document AI: extracts tables, key-value pairs, and text blocks.
        Returns a virtual schema that can be queried via NL2SQL.
        """
        # Simulated extraction
        tables = [
            {"table_id": f"pdf_table_{i}", "headers": ["Month","Revenue","Churn"], "rows": 12}
            for i in range(2)
        ]
        entities = [
            {"type": "FINANCIAL_METRIC", "name": "Total Revenue", "value": "$48.2M"},
            {"type": "DATE_RANGE",       "name": "Period",        "value": "FY 2025"},
            {"type": "ORGANIZATION",     "name": "Company",       "value": "Acme Corp"},
        ]
        return {
            "document_id":   str(uuid.uuid4()),
            "filename":      filename,
            "page_count":    max(1, len(pdf_bytes) // 2000),
            "tables_found":  len(tables),
            "tables":        tables,
            "entities":      entities,
            "virtual_table": f"alti_doc_{uuid.uuid4().hex[:8]}",
            "queryable":     True,
            "summary":       f"Document '{filename}' contains {len(tables)} tables and {len(entities)} key entities. Virtual table registered for NL2SQL querying."
        }

    def extract_image(self, image_bytes: bytes, context: str = "") -> dict:
        """
        Gemini Vision: analyzes charts, whiteboards, competitor ads, screenshots.
        Returns structured description usable as query context.
        """
        # Simulated Gemini Vision response
        image_hash = hash(image_bytes) % 5
        analyses = [
            {
                "type": "BAR_CHART",
                "description": "Bar chart showing monthly sales by region. Q3 North America shows the highest bar at approximately $12M. There is a visible decline in EMEA in September.",
                "extracted_metrics": [
                    {"name": "North America Q3 Revenue", "value": 12_000_000, "unit": "USD"},
                    {"name": "EMEA Q3 Revenue",          "value":  7_200_000, "unit": "USD"},
                ],
                "query_context": "Compare these extracted figures to live salesforce.revenue data for the same period."
            },
            {
                "type": "WHITEBOARD",
                "description": "Whiteboard shows a KPI tree: Gross Margin (top) → Cost of Revenue, Revenue. Revenue branch shows 3 sub-drivers: Pricing, Volume, Mix.",
                "extracted_metrics": [],
                "query_context": "Map whiteboard KPI tree to platform metrics and show current actuals for each node."
            },
            {
                "type": "COMPETITOR_AD",
                "description": "Digital ad from CompetitorX featuring '30% off annual plans'. Target audience appears to be SMB segment based on imagery and copy.",
                "extracted_metrics": [{"name": "Discount Offered", "value": 30, "unit": "%"}],
                "query_context": "Analyze whether our SMB segment shows unusual churn in the last 7 days that could correlate with this competitor promotion."
            },
            {
                "type": "SCREENSHOT",
                "description": "Dashboard screenshot showing NPS of 42 and churn_rate of 8.4% for APAC region.",
                "extracted_metrics": [
                    {"name": "NPS",        "value": 42,  "unit": "#"},
                    {"name": "Churn Rate", "value": 8.4, "unit": "%"},
                ],
                "query_context": "Compare these values to current live APAC metrics and identify the delta."
            },
            {
                "type": "TABLE_PHOTO",
                "description": "Photograph of a printed table showing quarterly financials with 4 columns and 8 rows.",
                "extracted_metrics": [],
                "query_context": "OCR and parse this financial table and join it against current quarter actuals."
            }
        ]
        return analyses[image_hash]


class TTSEngine:
    """
    Cloud Text-to-Speech: converts Gemini-narrated answers to audio.
    Voice profiles: EXECUTIVE (neutral, clear), ANALYST (data-dense, precise),
                    CLINICAL (calm, measured), SPORTS (energetic, punchy).
    """
    VOICE_PROFILES = {
        "EXECUTIVE": {"name": "en-US-Journey-F", "speaking_rate": 1.0, "pitch": 0.0},
        "ANALYST":   {"name": "en-US-Neural2-D", "speaking_rate": 0.95,"pitch": -1.0},
        "CLINICAL":  {"name": "en-US-Journey-O", "speaking_rate": 0.90,"pitch": -2.0},
        "SPORTS":    {"name": "en-US-Neural2-J", "speaking_rate": 1.15,"pitch": 2.0},
    }
    def synthesize(self, text: str, profile: str = "EXECUTIVE") -> dict:
        vp = self.VOICE_PROFILES.get(profile, self.VOICE_PROFILES["EXECUTIVE"])
        char_count = len(text)
        duration_ms = int(char_count * 55 / vp["speaking_rate"])   # ~55ms per char
        audio_uri = f"gs://alti-tts/{uuid.uuid4().hex[:12]}.mp3"
        return {"audio_uri": audio_uri, "duration_ms": duration_ms,
                "voice": vp["name"], "char_count": char_count}


class VoiceAnalyticsEngine:
    """
    Orchestrates the full voice + multimodal analytics pipeline.
    """
    def __init__(self):
        self.logger  = logging.getLogger("Voice_Analytics")
        logging.basicConfig(level=logging.INFO)
        self._speech = SpeechProcessor()
        self._doc    = DocumentIntelligence()
        self._tts    = TTSEngine()
        self._history: list[VoiceQueryResult] = []
        self.logger.info("🎤 Voice & Multimodal Analytics Engine initialized.")

    def _nl2sql_simulate(self, question: str) -> tuple[str, list[dict]]:
        """Simulated NL2SQL — in production routes to Epic 47 ConversationalAnalyticsEngine."""
        sql_map = {
            "churn":     ("SELECT month, churn_rate, prior_churn FROM analytics.churn_monthly ORDER BY month DESC LIMIT 3",
                          [{"month":"2026-03","churn_rate":4.8,"prior_churn":3.9},{"month":"2026-02","churn_rate":3.9,"prior_churn":4.1}]),
            "revenue":   ("SELECT region, SUM(revenue_usd) AS revenue FROM salesforce.revenue GROUP BY region ORDER BY revenue DESC",
                          [{"region":"North America","revenue":28_400_000},{"region":"EMEA","revenue":12_100_000},{"region":"APAC","revenue":8_200_000}]),
            "readmission":("SELECT diagnosis_group, AVG(readmission_30d_rate) AS rate FROM clinical.outcomes GROUP BY 1 ORDER BY rate DESC",
                          [{"diagnosis_group":"Cardiac","rate":0.182},{"diagnosis_group":"Pneumonia","rate":0.156}]),
            "fraud":     ("SELECT DATE(created_at) AS day, fraud_detection_rate FROM streaming.fraud_windows ORDER BY day DESC LIMIT 7",
                          [{"day":"2026-03-05","fraud_detection_rate":0.0031},{"day":"2026-03-04","fraud_detection_rate":0.0028}]),
        }
        q = question.lower()
        for key, (sql, rows) in sql_map.items():
            if key in q:
                return sql, rows
        return "SELECT * FROM analytics.summary LIMIT 5", [{"metric":"No specific match","value":"See dashboard"}]

    def _narrate(self, question: str, rows: list[dict]) -> str:
        """Produces a spoken-friendly answer. In production: Gemini API."""
        if not rows: return "No data was found for that query."
        first = rows[0]
        keys  = list(first.keys())
        if "churn_rate" in keys:
            delta = first.get("churn_rate",0) - first.get("prior_churn",0)
            return (f"Your churn rate is currently {first['churn_rate']:.1f}%, "
                    f"which is {abs(delta):.1f} percentage points {'higher' if delta>0 else 'lower'} than last month. "
                    f"The Swarm's churn rescue workflow has been active and is flagging high-risk accounts.")
        elif "revenue" in keys:
            top = first; total = sum(r.get("revenue",0) for r in rows)
            return (f"Your top revenue region is {top.get('region','N/A')} at "
                    f"${top.get('revenue',0)/1e6:.1f}M. Total across all regions is ${total/1e6:.1f}M this quarter.")
        elif "rate" in keys:
            return (f"The {rows[0].get('diagnosis_group','') } group has the highest rate at "
                    f"{rows[0]['rate']*100:.1f}%. This is above the 14.2% industry benchmark.")
        else:
            return f"Here are the top results: {json.dumps(rows[:2])}."

    def query(self, audio_bytes: bytes | None = None,
              text: str | None = None,
              language: str = "en-US",
              voice_profile: str = "EXECUTIVE",
              modality: InputModality = InputModality.VOICE) -> VoiceQueryResult:
        """
        Main entry point. Accepts voice audio OR text, routes through full pipeline.
        """
        t0 = time.time()
        if audio_bytes and not text:
            transcript = self._speech.transcribe(audio_bytes, language)
            question   = transcript["transcript"]
            self.logger.info(f"🎤 Transcribed: '{question}' (conf={transcript['confidence']})")
        else:
            question = text or ""
            self.logger.info(f"💬 Text query: '{question}'")

        sql, rows  = self._nl2sql_simulate(question)
        answer     = self._narrate(question, rows)
        audio      = self._tts.synthesize(answer, voice_profile)
        chart_url  = f"https://alti.ai/charts/{uuid.uuid4().hex[:8]}"
        latency_ms = round((time.time() - t0) * 1000 + 180, 1)   # +180ms simulated API latency

        result = VoiceQueryResult(
            query_id=str(uuid.uuid4()), original_input=question,
            sql_generated=sql, answer_text=answer,
            spoken_audio_uri=audio["audio_uri"], chart_url=chart_url,
            data_rows=rows, latency_ms=latency_ms, modality=modality
        )
        self._history.append(result)
        self.logger.info(f"✅ Voice query complete in {latency_ms:.0f}ms | audio={audio['duration_ms']}ms")
        return result

    def analyze_image(self, image_bytes: bytes, follow_up: str = "") -> dict:
        """Gemini Vision analysis with optional follow-up NL2SQL query."""
        analysis = self._doc.extract_image(image_bytes)
        result   = {"analysis": analysis}
        if follow_up:
            qr = self.query(text=follow_up + ". Context: " + analysis["query_context"],
                           modality=InputModality.IMAGE)
            result["query_result"] = {"answer": qr.answer_text, "chart": qr.chart_url}
        return result

    def ingest_document(self, file_bytes: bytes, filename: str,
                        follow_up: str = "") -> dict:
        """Upload a PDF or spreadsheet, make it queryable, optionally ask a question."""
        extracted = self._doc.extract_pdf(file_bytes, filename)
        self.logger.info(f"📄 Document ingested: '{filename}' → {extracted['tables_found']} tables → {extracted['virtual_table']}")
        result = {"extraction": extracted}
        if follow_up:
            qr = self.query(text=follow_up + f". Use virtual table {extracted['virtual_table']}.",
                           modality=InputModality.PDF)
            result["query_result"] = {"answer": qr.answer_text, "chart": qr.chart_url}
        return result

    def conversation_history(self) -> list[dict]:
        return [{"query_id": r.query_id[:12], "question": r.original_input,
                 "modality": r.modality, "latency_ms": r.latency_ms} for r in self._history]


if __name__ == "__main__":
    engine = VoiceAnalyticsEngine()

    # Voice query (simulated audio bytes)
    print("=== Voice Query: Churn ===")
    result = engine.query(audio_bytes=b"\x00" * 19200, language="en-US")
    print(f"  Transcribed: '{result.original_input}'")
    print(f"  SQL: {result.sql_generated}")
    print(f"  Answer: {result.answer_text}")
    print(f"  Audio: {result.spoken_audio_uri}")
    print(f"  Chart: {result.chart_url}")
    print(f"  Latency: {result.latency_ms}ms")

    # Text query  
    print("\n=== Text Query: Revenue ===")
    r2 = engine.query(text="Show me revenue by region for last quarter")
    print(f"  Answer: {r2.answer_text}")

    # Image analysis: competitor ad
    print("\n=== Image Analysis: Competitor Ad ===")
    result_img = engine.analyze_image(b"\xFF\xD8\xFF" * 100,
                                      follow_up="Does our EMEA churn correlate with this promotion?")
    print(f"  Type: {result_img['analysis']['type']}")
    print(f"  Vision: {result_img['analysis']['description']}")
    if "query_result" in result_img:
        print(f"  Answer: {result_img['query_result']['answer']}")

    # Document ingestion
    print("\n=== Document Ingestion: Annual Report PDF ===")
    doc_result = engine.ingest_document(b"%PDF-1.4" + b"\x00"*5000,
                                        "annual_report_2025.pdf",
                                        follow_up="What revenue figures are in this document?")
    print(f"  Tables found: {doc_result['extraction']['tables_found']}")
    print(f"  Virtual table: {doc_result['extraction']['virtual_table']}")
    if "query_result" in doc_result:
        print(f"  Answer: {doc_result['query_result']['answer']}")
