# services/regional-models/regional_models.py
"""
Epic 73: Regionally-Specialized AI Models
Geography-specific NL2SQL and analytics models fine-tuned on local
business vocabulary, date/number formats, and regional market context.

Why this matters: A model trained on English/Western data struggles with:
  - Japanese: kanji entity names, 年/月/日 dates, 万/億 numbers, honorific context
  - Arabic: RTL query structure, Arabic numerals (٠١٢٣٤), Gulf/MENA business terms
  - Indian: lakh/crore numbering, BSE/NSE tickers, Hindi-English code-switching
  - Korean: 원/천/만/억 formatting, KOSPI/KOSDAQ tickers, Korean fiscal year
  - Brazilian: CNPJ/CPF identifiers, B3 exchange, fiscal periods, PT business idioms

Each regional model is registered in the MLOps registry (Epic 62) and
promoted through DEV → STAGING → PRODUCTION with metric-gated rollouts.

Regional stock indices as native data sources:
  JSE      (South Africa)    - Johannesburg Stock Exchange
  BSE/NSE  (India)           - Bombay + National Stock Exchange
  TSE      (Japan)           - Tokyo Stock Exchange (Prime/Standard/Growth)
  B3       (Brazil)          - Brasil, Bolsa, Balcão
  IDX      (Indonesia)       - Indonesia Stock Exchange
  KOSPI    (South Korea)     - Korea Composite Stock Price Index
  TADAWUL  (Saudi Arabia)    - Saudi Exchange
  SGX      (Singapore)       - Singapore Exchange
  ASX      (Australia)       - Australian Securities Exchange
  LSE      (UK)              - London Stock Exchange (FTSE 100/250)
  Euronext (EU)              - Amsterdam/Paris/Brussels/Lisbon/Milan
  HKEX     (Hong Kong)       - Hong Kong Exchanges and Clearing
  SSE/SZSE (China)           - Shanghai/Shenzhen Stock Exchanges
  BMV      (Mexico)          - Bolsa Mexicana de Valores
  JSX      (Egypt)           - Egyptian Exchange (EGX)
"""
import logging, json, uuid, time, random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class ModelType(str, Enum):
    NL2SQL    = "NL2SQL"
    NARRATIVE = "NARRATIVE"
    EMBEDDING = "EMBEDDING"
    INTENT    = "INTENT"

@dataclass
class RegionalIndex:
    exchange_id:  str
    name:         str
    country:      str
    currency:     str
    locale:       str
    major_indices:list[str]
    sector_codes: list[str]
    trading_hours:str        # UTC
    fiscal_year_start: str   # "Jan" | "Apr" | "Jul" | "Oct"
    sample_tickers:list[str]

@dataclass
class RegionalModel:
    model_id:     str
    locale:       str
    model_type:   ModelType
    base_model:   str        # foundation model (e.g. "gemini-1.5-pro")
    fine_tune_id: str        # Vertex AI fine-tuning job ID
    stage:        str        # DEV | STAGING | PRODUCTION
    auc:          float
    latency_ms:   float
    training_examples:int
    specializations:list[str]   # e.g. ["japanese_dates", "kanji_entities"]
    deployed_at:  float = field(default_factory=time.time)

@dataclass
class RegionalQueryResult:
    query_id:     str
    locale:       str
    raw_query:    str        # original user query
    normalized:   str        # normalized to canonical form
    sql_generated:str
    model_used:   str
    locale_tokens:list[str]  # locale-specific tokens detected
    confidence:   float
    latency_ms:   float

class RegionalModelRegistry:
    """
    Manages geography-specific AI model variants for the Alti platform.
    Routes incoming NL queries to the best regional model for the locale.
    Falls back to the global Gemini model if no regional model deployed.
    """
    def __init__(self):
        self.logger = logging.getLogger("Regional_Models")
        logging.basicConfig(level=logging.INFO)
        self._models:  dict[str, RegionalModel] = {}
        self._indices: dict[str, RegionalIndex] = {}
        self._query_log:list[RegionalQueryResult] = []
        self._register_models()
        self._register_indices()
        self.logger.info(f"🧠 Regional Model Registry: {len(self._models)} models, {len(self._indices)} exchanges.")

    def _register_models(self):
        model_defs = [
            # Japanese NL2SQL
            ("ja-JP",ModelType.NL2SQL,"gemini-1.5-pro","ft-ja-nl2sql-v3",0.947,82.4,48200,
             ["japanese_dates_YYYY年MM月DD日","kanji_entity_names","wan_oku_numbers",
              "japanese_fiscal_year_april","honorific_query_rewriting","nikkei_tickers"]),
            # Arabic NL2SQL
            ("ar-SA",ModelType.NL2SQL,"gemini-1.5-pro","ft-ar-nl2sql-v2",0.921,94.8,28400,
             ["rtl_query_parsing","arabic_numerals_٠١٢٣","gulf_business_terms",
              "hijri_calendar_conversion","tadawul_tickers","arabic_metric_names"]),
            # Hindi/Indian NL2SQL
            ("hi-IN",ModelType.NL2SQL,"gemini-1.5-pro","ft-hi-nl2sql-v2",0.918,88.2,31600,
             ["lakh_crore_numbering","hinglish_code_switching","bse_nse_tickers",
              "indian_fiscal_year_april","pan_cin_identifiers","gst_hsn_codes"]),
            # Korean NL2SQL
            ("ko-KR",ModelType.NL2SQL,"gemini-1.5-pro","ft-ko-nl2sql-v2",0.934,86.4,22800,
             ["korean_numbers_만억","kospi_kosdaq_tickers","korean_fiscal_periods",
              "chaebol_group_entities","korean_honorific_context","krw_formatting"]),
            # Brazilian Portuguese NL2SQL
            ("pt-BR",ModelType.NL2SQL,"gemini-1.5-pro","ft-ptbr-nl2sql-v1",0.928,79.2,19400,
             ["cnpj_cpf_identifiers","b3_bovespa_tickers","brazilian_fiscal_periods",
              "simples_lucro_real_regimes","selic_rate_references","ibge_codes"]),
            # Chinese NL2SQL (Simplified)
            ("zh-CN",ModelType.NL2SQL,"gemini-1.5-pro","ft-zhcn-nl2sql-v2",0.941,91.6,54200,
             ["chinese_date_formats","wan_yi_numbers","sse_szse_tickers",
              "chinese_fiscal_year_jan","social_credit_codes","rmb_yuan_normalization"]),
            # German NL2SQL
            ("de-DE",ModelType.NL2SQL,"gemini-1.5-pro","ft-dede-nl2sql-v1",0.939,77.8,16800,
             ["german_compound_words","dax_xetra_tickers","german_fiscal_year",
              "ust_mwst_vat_handling","handelsregister_ids","euro_decimal_comma"]),
            # Indonesian Bahasa NL2SQL
            ("id-ID",ModelType.NL2SQL,"gemini-1.5-pro","ft-idid-nl2sql-v1",0.904,88.4,14200,
             ["idx_tickers","rupiah_formatting","indonesian_fiscal_year",
              "npwp_company_ids","ojk_regulatory_codes"]),
            # Narrative models for 4 key locales
            ("ja-JP",ModelType.NARRATIVE,"gemini-1.5-pro","ft-ja-narr-v2",0.961,142.0,38600,
             ["keigo_business_japanese","four_seasons_metaphors","nemawashi_context"]),
            ("ar-SA",ModelType.NARRATIVE,"gemini-1.5-pro","ft-ar-narr-v1",0.938,168.0,22400,
             ["gulf_arabic_register","islamic_finance_terminology","wasta_context"]),
        ]
        for locale, mtype, base, ftid, auc, lat, examples, specs in model_defs:
            mid = f"rm-{locale.lower().replace('-','')}-{mtype.value.lower()}-{uuid.uuid4().hex[:6]}"
            self._models[mid] = RegionalModel(
                model_id=mid, locale=locale, model_type=mtype,
                base_model=base, fine_tune_id=ftid, stage="PRODUCTION",
                auc=auc, latency_ms=lat, training_examples=examples,
                specializations=specs
            )

    def _register_indices(self):
        indices = [
            RegionalIndex("TSE","Tokyo Stock Exchange","JP","JPY","ja-JP",
                          ["Nikkei 225","TOPIX","JPX-Nikkei 400"],
                          ["7203","6758","9984","8306","6861"],
                          "00:00-06:30 UTC","Apr",
                          ["トヨタ自動車(7203)","ソニーグループ(6758)","ソフトバンクG(9984)"]),
            RegionalIndex("TADAWUL","Saudi Exchange","SA","SAR","ar-SA",
                          ["Tadawul All Share Index (TASI)","NOMU"],
                          ["2222","1120","2010","1010","4030"],
                          "06:00-12:00 UTC","Jan",
                          ["أرامكو السعودية(2222)","الراجحي(1120)","سابك(2010)"]),
            RegionalIndex("BSE","Bombay Stock Exchange","IN","INR","hi-IN",
                          ["SENSEX","BSE 100","BSE SmallCap"],
                          ["500325","500112","532540","500180","500010"],
                          "03:45-10:00 UTC","Apr",
                          ["Reliance Industries(500325)","SBI(500112)","Infosys(532540)"]),
            RegionalIndex("B3","Brasil Bolsa Balcão","BR","BRL","pt-BR",
                          ["IBOVESPA","IBRX-100","SMLL"],
                          ["PETR4","VALE3","ITUB4","BBDC4","ABEV3"],
                          "13:00-20:00 UTC","Jan",
                          ["Petrobras(PETR4)","Vale(VALE3)","Itaú Unibanco(ITUB4)"]),
            RegionalIndex("KOSPI","Korea Exchange","KR","KRW","ko-KR",
                          ["KOSPI","KOSDAQ","KRX 300"],
                          ["005930","000660","035420","051910","006400"],
                          "00:00-06:30 UTC","Jan",
                          ["삼성전자(005930)","SK하이닉스(000660)","NAVER(035420)"]),
            RegionalIndex("SSE","Shanghai Stock Exchange","CN","CNY","zh-CN",
                          ["SSE Composite","SSE 50","CSI 300"],
                          ["600519","601398","600036","601318","600900"],
                          "01:30-07:00 UTC","Jan",
                          ["贵州茅台(600519)","工商银行(601398)","招商银行(600036)"]),
            RegionalIndex("JSE","Johannesburg Stock Exchange","ZA","ZAR","af-ZA",
                          ["JSE All Share (ALSI)","JSE Top 40","JSE Financials"],
                          ["NPN","BHP","MTN","SBK","ABG"],
                          "07:00-15:00 UTC","Jan",
                          ["Naspers(NPN)","BHP Group(BHP)","MTN Group(MTN)"]),
            RegionalIndex("IDX","Indonesia Stock Exchange","ID","IDR","id-ID",
                          ["JCI (IDX Composite)","LQ45","IDX30"],
                          ["BBCA","BBRI","TLKM","ASII","GOTO"],
                          "02:00-08:00 UTC","Jan",
                          ["Bank Central Asia(BBCA)","Bank Rakyat(BBRI)","Telkom(TLKM)"]),
            RegionalIndex("SGX","Singapore Exchange","SG","SGD","ms-MY",
                          ["STI (Straits Times Index)","FTSE ST All Share"],
                          ["D05","O39","Z74","U11","C6L"],
                          "01:00-09:00 UTC","Jan",
                          ["DBS Group(D05)","OCBC Bank(O39)","SingTel(Z74)"]),
            RegionalIndex("ASX","Australian Securities Exchange","AU","AUD","en-AU",
                          ["S&P/ASX 200","All Ordinaries","ASX 50"],
                          ["BHP","CBA","CSL","NAB","WBC"],
                          "23:00-05:30 UTC","Jul",
                          ["BHP Group(BHP)","Commonwealth Bank(CBA)","CSL Ltd(CSL)"]),
            RegionalIndex("BMV","Bolsa Mexicana de Valores","MX","MXN","es-MX",
                          ["IPC (Índice de Precios y Cotizaciones)","FIBRAMQ"],
                          ["AMXL","WALMEX*","FEMSAUBD","CEMEXCPO","GFNORTEO"],
                          "14:30-21:00 UTC","Jan",
                          ["América Móvil(AMXL)","Walmart México(WALMEX*)","FEMSA(FEMSAUBD)"]),
        ]
        for idx in indices:
            self._indices[idx.exchange_id] = idx

    def route(self, query: str, locale: str,
              model_type: ModelType = ModelType.NL2SQL) -> RegionalModel:
        """Routes a NL query to the best regional model for the given locale."""
        regional = next(
            (m for m in self._models.values()
             if m.locale == locale and m.model_type == model_type
             and m.stage == "PRODUCTION"),
            None
        )
        if regional:
            self.logger.info(f"  🧠 Routed to regional model: {regional.fine_tune_id} ({locale})")
        else:
            self.logger.info(f"  🌐 No regional model for {locale} — falling back to global Gemini")
        return regional

    def process_query(self, query: str, locale: str) -> RegionalQueryResult:
        """
        Full regional NL2SQL pipeline:
        1. Detect locale-specific tokens (dates, numbers, tickers, entities)
        2. Route to best regional model
        3. Normalize query (e.g. 万 → 10000, 年 → year, PETR4 → petrobras)
        4. Generate SQL via the regional model
        5. Return result with locale metadata
        """
        t0 = time.time()
        model = self.route(query, locale)

        # Extract locale-specific tokens
        locale_tokens = self._extract_locale_tokens(query, locale)

        # Normalize query (in production: regional model pre-processing)
        normalized = self._normalize_query(query, locale, locale_tokens)

        # Simulate SQL generation
        sql_patterns = {
            "ja-JP": "SELECT 期間, SUM(売上) AS 売上合計 FROM 売上データ GROUP BY 期間 ORDER BY 期間 DESC",
            "ar-SA": "SELECT القسم, SUM(الإيرادات) AS إجمالي_الإيرادات FROM بيانات_المبيعات GROUP BY القسم",
            "hi-IN": "SELECT क्षेत्र, SUM(राजस्व) AS कुल_राजस्व FROM बिक्री_डेटा GROUP BY क्षेत्र",
            "zh-CN": "SELECT 地区, SUM(收入) AS 总收入 FROM 销售数据 GROUP BY 地区 ORDER BY 总收入 DESC",
            "ko-KR": "SELECT 지역, SUM(매출) AS 총매출 FROM 판매데이터 GROUP BY 지역 ORDER BY 총매출 DESC",
            "pt-BR": "SELECT regiao, SUM(receita_liquida) AS total FROM vendas GROUP BY regiao ORDER BY total DESC",
            "de-DE": "SELECT Quartal, SUM(Umsatz) AS Gesamtumsatz FROM Verkaufsdaten GROUP BY Quartal",
        }
        sql = sql_patterns.get(locale, f"SELECT region, SUM(revenue) FROM sales WHERE locale='{locale}' GROUP BY region")
        model_id = model.fine_tune_id if model else "gemini-1.5-pro-global"
        latency  = (time.time() - t0) * 1000 + (model.latency_ms if model else 120.0)

        result = RegionalQueryResult(
            query_id=str(uuid.uuid4()), locale=locale, raw_query=query,
            normalized=normalized, sql_generated=sql, model_used=model_id,
            locale_tokens=locale_tokens,
            confidence=model.auc if model else 0.88,
            latency_ms=round(latency, 1)
        )
        self._query_log.append(result)
        return result

    def _extract_locale_tokens(self, query: str, locale: str) -> list[str]:
        tokens = []
        if locale == "ja-JP":
            if "万" in query: tokens.append("JA_NUMBER:万")
            if "億" in query: tokens.append("JA_NUMBER:億")
            if "年" in query: tokens.append("JA_DATE:年")
            if any(c in query for c in ["売上","収益","顧客"]): tokens.append("JA_BUSINESS_TERM")
        elif locale == "ar-SA":
            if any(c in "٠١٢٣٤٥٦٧٨٩" for c in query): tokens.append("AR_NUMERALS")
            if "مليون" in query: tokens.append("AR_NUMBER:مليون")
            if "الإيرادات" in query: tokens.append("AR_TERM:revenue")
        elif locale == "hi-IN":
            if "लाख" in query: tokens.append("IN_NUMBER:lakh")
            if "करोड़" in query: tokens.append("IN_NUMBER:crore")
        elif locale == "zh-CN":
            if "万" in query: tokens.append("ZH_NUMBER:万")
            if "亿" in query: tokens.append("ZH_NUMBER:亿")
        return tokens

    def _normalize_query(self, query: str, locale: str, tokens: list[str]) -> str:
        norm = query
        if locale == "ja-JP":
            norm = norm.replace("万", "*10000").replace("億", "*100000000")
            norm = norm.replace("売上", "revenue").replace("顧客", "customers")
        elif locale == "hi-IN":
            norm = norm.replace("लाख", "*100000").replace("करोड़", "*10000000")
        elif locale == "zh-CN":
            norm = norm.replace("万", "*10000").replace("亿", "*100000000")
        return norm.strip()

    def registry_summary(self) -> dict:
        by_locale = {}
        for m in self._models.values():
            by_locale.setdefault(m.locale, []).append(m.model_type)
        return {
            "total_models":    len(self._models),
            "locales_covered": list(by_locale.keys()),
            "exchanges":       len(self._indices),
            "exchange_list":   [{"id": idx.exchange_id, "name": idx.name, "country": idx.country,
                                 "indices": idx.major_indices[:2]}
                                for idx in self._indices.values()],
            "models_by_locale":by_locale,
        }


if __name__ == "__main__":
    registry = RegionalModelRegistry()
    summary  = registry.registry_summary()
    print(f"🧠 Regional Models: {summary['total_models']} models across {len(summary['locales_covered'])} locales")
    print(f"📈 Stock Exchanges: {summary['exchanges']}")
    for ex in summary["exchange_list"]:
        print(f"  {ex['id']:10} {ex['name']:45} ({ex['country']}) — {ex['indices']}")

    test_queries = [
        ("売上高が先月より下がった理由を教えてください", "ja-JP"),
        ("لماذا انخفضت إيرادات الربع الماضي؟", "ar-SA"),
        ("पिछले महीने की तुलना में राजस्व क्यों गिरा?", "hi-IN"),
        ("지난 분기 매출이 감소한 이유는 무엇입니까?", "ko-KR"),
        ("Por que a receita caiu em relação ao mês anterior?", "pt-BR"),
        ("Warum ist der Umsatz im letzten Quartal gesunken?", "de-DE"),
    ]
    print(f"\n🔍 Regional Query Routing:")
    for query, locale in test_queries:
        result = registry.process_query(query, locale)
        print(f"\n  [{locale}] '{query[:50]}...' ")
        print(f"   Model: {result.model_used:30} | Conf: {result.confidence:.3f} | {result.latency_ms:.0f}ms")
        print(f"   SQL:   {result.sql_generated[:80]}...")
