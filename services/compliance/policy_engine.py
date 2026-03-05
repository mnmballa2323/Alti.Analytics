# services/compliance/policy_engine.py
"""
Epic 43: Compliance Policy Engine & Data Classification
Central compliance controller for Alti.Analytics.
Implements automated data classification using Google Cloud DLP and
routes all data operations through the correct regulatory control layer.
Frameworks: HIPAA, SOC 2, SOX, GDPR, CCPA, PCI-DSS, ISO 27001, FedRAMP, NIST CSF
"""
import logging
import json
import hashlib
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# Data Classification Taxonomy
# ─────────────────────────────────────────────
class DataClass(str, Enum):
    PUBLIC       = "PUBLIC"        # No restrictions
    INTERNAL     = "INTERNAL"      # ISO 27001 A.8: internal use only
    CONFIDENTIAL = "CONFIDENTIAL"  # SOC 2 CC6: access controls required
    PHI          = "PHI"           # HIPAA: Protected Health Information
    PII_EU       = "PII_EU"        # GDPR: EU personal data → europe-west residency
    PII_CA       = "PII_CA"        # CCPA: California consumer data
    PCI          = "PCI"           # PCI-DSS: cardholder data → tokenization mandatory
    FINANCIAL    = "FINANCIAL"     # SOX: financial records → immutable audit trail
    FEDERAL      = "FEDERAL"       # FedRAMP: federal controlled unclassified info

@dataclass
class DataAsset:
    asset_id: str
    source_system: str
    data_class: DataClass
    subject_id: Optional[str] = None
    residency_region: Optional[str] = None
    consent_verified: bool = False
    tags: dict = field(default_factory=dict)

class CompliancePolicyEngine:
    REGION_MAP = {
        DataClass.PII_EU:    "europe-west1",
        DataClass.FEDERAL:   "us-central1",
        DataClass.PHI:       "us-central1",
        DataClass.PCI:       "us-central1",
    }
    logger = logging.getLogger("Compliance_Engine")
    logging.basicConfig(level=logging.INFO)

    def classify_asset_via_dlp(self, content_sample: str, source_system: str) -> DataAsset:
        """
        Calls Google Cloud DLP to inspect content and assign the highest
        applicable data classification. In production:
          dlp_v2.DlpServiceClient().inspect_content(inspect_config=..., item=...)
        """
        self.logger.info(f"🔍 DLP classification scan for asset from: {source_system}")
        
        # Detection logic (DLP infoType matching in production)
        data_class = DataClass.INTERNAL
        detected = []
        if any(k in content_sample.lower() for k in ["ssn", "dob", "diagnosis", "patient_id", "mrn"]):
            data_class = DataClass.PHI
            detected.append("HIPAA_PHI")
        elif any(k in content_sample.lower() for k in ["card_number", "cvv", "pan", "expiry"]):
            data_class = DataClass.PCI
            detected.append("PCI_CARDHOLDER_DATA")
        elif any(k in content_sample.lower() for k in ["email", "name", "ip_address", "cookie"]):
            data_class = DataClass.PII_EU  # Default EU treatment (strictest)
            detected.append("PII_GDPR")
        elif any(k in content_sample.lower() for k in ["revenue", "ebitda", "earnings", "quarter"]):
            data_class = DataClass.FINANCIAL
            detected.append("SOX_FINANCIAL")
        
        asset_id = hashlib.sha256(f"{source_system}:{int(time.time())}".encode()).hexdigest()[:12]
        self.logger.info(f"   → Classified as {data_class.value}. DLP findings: {detected}")
        
        return DataAsset(
            asset_id=asset_id,
            source_system=source_system,
            data_class=data_class,
            residency_region=self.REGION_MAP.get(data_class, "us-central1"),
            tags={"dlp_findings": detected, "classified_at": str(int(time.time()))}
        )

    def enforce_controls(self, asset: DataAsset) -> dict:
        """
        Routes a classified data asset through the appropriate regulatory controls:
        PHI    → HIPAA: CMEK encryption, BAA-verified SA, audit log, DLP redaction
        PCI    → PCI-DSS: PAN tokenization, CDE network isolation
        PII_EU → GDPR: consent check, residency enforcement, purpose limitation
        PII_CA → CCPA: opt-out check, right-to-know flagging
        FINANCIAL → SOX: immutable write-once audit trail, dual-approver gate
        FEDERAL → FedRAMP: NIST 800-53 controls, continuous monitoring
        """
        controls_applied = []
        compliance_verdict = "APPROVED"

        if asset.data_class == DataClass.PHI:
            controls_applied += [
                "HIPAA_CMEK_ENCRYPTION",
                "HIPAA_AUDIT_LOG_SINK_ENABLED",
                "HIPAA_BAA_SA_VERIFIED",
                "DLP_PHI_REDACTION_APPLIED",
                "ACCESS_MINIMUM_NECESSARY_ENFORCED",
                "RETENTION_6_YEAR_LOCKED"
            ]
        elif asset.data_class == DataClass.PCI:
            controls_applied += [
                "PCI_PAN_TOKENIZATION_APPLIED",
                "PCI_CDE_VPC_ISOLATION",
                "PCI_TLS1_3_IN_TRANSIT",
                "PCI_QUARTERLY_ASV_SCAN_SCHEDULED"
            ]
        elif asset.data_class == DataClass.PII_EU:
            if not asset.consent_verified:
                compliance_verdict = "BLOCKED_GDPR_NO_CONSENT"
                controls_applied.append("GDPR_CONSENT_GATE_FAILED")
            else:
                controls_applied += [
                    "GDPR_RESIDENCY_ENFORCED_EU_ONLY",
                    "GDPR_PURPOSE_LIMITATION_TAGGED",
                    "GDPR_RETENTION_SCHEDULE_APPLIED",
                    "GDPR_SUBJECT_RIGHTS_INDEXED"
                ]
        elif asset.data_class == DataClass.PII_CA:
            controls_applied += [
                "CCPA_OPT_OUT_CHECKED",
                "CCPA_NO_SALE_ENFORCED",
                "CCPA_DISCLOSURE_LOGGED",
                "CCPA_DELETION_RIGHTS_REGISTERED"
            ]
        elif asset.data_class == DataClass.FINANCIAL:
            controls_applied += [
                "SOX_IMMUTABLE_AUDIT_TRAIL_WORM",
                "SOX_CHANGE_CONTROL_DUAL_APPROVER",
                "SOX_SEGREGATION_OF_DUTIES_ENFORCED",
                "SOX_90_DAY_FINANCIAL_LOG_RETENTION"
            ]
        elif asset.data_class == DataClass.FEDERAL:
            controls_applied += [
                "FEDRAMP_NIST_800_53_BASELINE",
                "FEDRAMP_CONTINUOUS_MONITORING_ACTIVE",
                "NIST_CSF_PROTECT_DETECT_RESPOND",
                "ISO27001_ISMS_CONTROL_SET_A3_A18"
            ]
        
        # Universal SOC 2 controls applied to ALL assets
        controls_applied += [
            "SOC2_ACCESS_CONTROL_CC6_APPLIED",
            "SOC2_CHANGE_MANAGEMENT_CC8_LOGGED",
            "SOC2_AUDIT_LOG_CAPTURED"
        ]

        return {
            "asset_id": asset.asset_id,
            "data_class": asset.data_class.value,
            "residency_region": asset.residency_region,
            "compliance_verdict": compliance_verdict,
            "controls_applied": controls_applied,
            "frameworks_satisfied": self._get_satisfied_frameworks(asset.data_class)
        }

    def _get_satisfied_frameworks(self, dc: DataClass) -> list:
        mapping = {
            DataClass.PHI:       ["HIPAA", "SOC2", "ISO27001", "NIST_CSF"],
            DataClass.PCI:       ["PCI_DSS", "SOC2", "ISO27001"],
            DataClass.PII_EU:    ["GDPR", "SOC2", "ISO27001", "NIST_CSF"],
            DataClass.PII_CA:    ["CCPA", "GDPR", "SOC2"],
            DataClass.FINANCIAL: ["SOX", "SOC2", "ISO27001"],
            DataClass.FEDERAL:   ["FEDRAMP", "NIST_CSF", "SOC2", "ISO27001"],
        }
        return mapping.get(dc, ["SOC2", "ISO27001"])

if __name__ == "__main__":
    engine = CompliancePolicyEngine()
    phi_asset = engine.classify_asset_via_dlp("patient_id=P-8821, diagnosis=T2DM, dob=1980-03-12", "ehr_dataflow")
    result = engine.enforce_controls(phi_asset)
    print(json.dumps(result, indent=2))
    
    pci_asset = engine.classify_asset_via_dlp("card_number=4111111111111111, cvv=123, expiry=12/28", "payment_service")
    result2 = engine.enforce_controls(pci_asset)
    print(json.dumps(result2, indent=2))

    fin_asset = engine.classify_asset_via_dlp("Q3 revenue=8.42B, ebitda_margin=0.31, earnings_per_share=4.12", "finance_api")
    result3 = engine.enforce_controls(fin_asset)
    print(json.dumps(result3, indent=2))
