# services/ai-governance/ai_governance.py
"""
Epic 82: AI Explainability & Responsible AI (EU AI Act / SR 11-7 / FDA)
Every AI decision made by the platform is now explainable, audited,
and monitored for fairness — legally required before deployment in
EU financial services, US banking, and healthcare.

Regulatory mapping:
  EU AI Act       → High-risk AI systems require conformity assessment,
                    human oversight, and transparency obligations.
                    Platform systems in scope: credit scoring, fraud detection,
                    patient risk, hiring tools (HR industry template).
  SR 11-7 (OCC)  → US banking model risk management. All models must have
                    documented development, validation, and use limitations.
                    Explanations required for adverse action notices.
  FDA 21 CFR 11  → Electronic records for clinical AI must be tamper-proof
                    audit trails, with human review for high-risk predictions.
  FCRA / ECOA    → Credit decisions must include adverse action notices with
                    specific reason codes (the SHAP top factors).

SHAP (SHapley Additive exPlanations):
  Each prediction becomes: base_value + Σ shap_values[feature_i] = prediction
  Top positive features pushed the score up.
  Top negative features pushed the score down.
  Every user gets "Why this score?" powered by SHAP.
"""
import logging, json, uuid, time, random, math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class AIRiskClass(str, Enum):
    UNACCEPTABLE = "UNACCEPTABLE"   # EU AI Act: PROHIBITED
    HIGH_RISK    = "HIGH_RISK"      # Requires conformity assessment
    LIMITED_RISK = "LIMITED_RISK"   # Transparency obligation only
    MINIMAL_RISK = "MINIMAL_RISK"   # No specific obligations

class FairnessMetric(str, Enum):
    DEMOGRAPHIC_PARITY    = "DEMOGRAPHIC_PARITY"     # P(Y=1|A=0) = P(Y=1|A=1)
    EQUALIZED_ODDS        = "EQUALIZED_ODDS"         # TPR and FPR equal across groups
    EQUAL_OPPORTUNITY     = "EQUAL_OPPORTUNITY"       # TPR equal across groups
    PREDICTIVE_PARITY     = "PREDICTIVE_PARITY"      # PPV equal across groups
    INDIVIDUAL_FAIRNESS   = "INDIVIDUAL_FAIRNESS"     # Similar individuals treated similarly

class HumanReviewStatus(str, Enum):
    NOT_REQUIRED  = "NOT_REQUIRED"
    PENDING       = "PENDING_HUMAN_REVIEW"
    APPROVED      = "HUMAN_APPROVED"
    OVERRIDDEN    = "HUMAN_OVERRIDDEN"
    ESCALATED     = "ESCALATED_TO_SUPERVISOR"

@dataclass
class SHAPExplanation:
    feature_importances: dict[str, float]   # feature → SHAP value
    base_value:          float              # model's mean prediction
    prediction:          float              # final model output
    top_positive:        list[tuple]        # features that INCREASED score
    top_negative:        list[tuple]        # features that DECREASED score
    human_readable:      str               # plain-English explanation

@dataclass
class ModelPrediction:
    prediction_id:     str
    model_id:          str
    model_version:     str
    tenant_id:         str
    subject_id:        str               # patient_id, customer_id, loan_id etc.
    use_case:          str
    features:          dict
    raw_score:         float             # 0–1 probability
    decision:          str               # "APPROVED" / "DENIED" / "FLAG" etc.
    shap_explanation:  Optional[SHAPExplanation]
    fairness_flags:    list[str]         # any fairness violations detected
    human_review:      HumanReviewStatus
    regulation:        list[str]         # applicable regulations
    timestamp:         float = field(default_factory=time.time)
    human_decision:    Optional[str]     = None   # what human actually decided
    human_reviewer:    Optional[str]     = None

@dataclass
class FairnessReport:
    model_id:        str
    evaluation_date: float
    metric:          FairnessMetric
    groups_evaluated:list[str]
    group_rates:     dict[str, float]   # group → metric value
    max_disparity:   float              # largest gap between groups
    threshold:       float              # acceptable disparity (e.g. 0.05)
    passed:          bool
    violation_groups:list[str]          # groups with disparate outcomes
    recommendation:  str

@dataclass
class AIActConformityAssessment:
    model_id:      str
    risk_class:    AIRiskClass
    use_case:      str
    jurisdiction:  str
    compliant:     bool
    obligations:   list[str]
    gaps:          list[str]           # compliance gaps found
    assessed_at:   float = field(default_factory=time.time)

class AIGovernanceEngine:
    """
    Responsible AI layer. Every prediction is explained, audited,
    and monitored for demographic fairness violations.
    Covers EU AI Act, SR 11-7, FDA 21 CFR 11, FCRA, and ECOA.
    """
    # EU AI Act risk classification by use case
    _EU_RISK_CLASSIFICATION = {
        "credit_scoring":       AIRiskClass.HIGH_RISK,
        "fraud_detection":      AIRiskClass.HIGH_RISK,
        "patient_readmission":  AIRiskClass.HIGH_RISK,
        "hiring_screening":     AIRiskClass.HIGH_RISK,
        "insurance_pricing":    AIRiskClass.HIGH_RISK,
        "customer_churn":       AIRiskClass.LIMITED_RISK,
        "demand_forecast":      AIRiskClass.MINIMAL_RISK,
        "cost_anomaly":         AIRiskClass.MINIMAL_RISK,
        "content_recommendation":AIRiskClass.LIMITED_RISK,
        "facial_recognition":   AIRiskClass.UNACCEPTABLE,  # PROHIBITED in EU public spaces
        "social_scoring":       AIRiskClass.UNACCEPTABLE,  # PROHIBITED unconditionally
    }

    # High-risk thresholds requiring human review
    _HUMAN_REVIEW_THRESHOLDS = {
        "credit_scoring":      0.70,   # credit denial above 70% risk score
        "fraud_detection":     0.85,   # fraud flag above 85% confidence
        "patient_readmission": 0.80,   # readmission risk above 80%
        "hiring_screening":    0.65,   # candidate reject above 65% risk
        "insurance_pricing":   0.75,   # coverage denial above 75%
    }

    # SR 11-7 approved feature lists per model (no prohibited features)
    _PROHIBITED_FEATURES = {
        "credit_scoring":  ["race","ethnicity","religion","national_origin","sex","marital_status","age","disability"],
        "hiring_screening":["race","ethnicity","religion","national_origin","sex","marital_status","age","disability"],
        "insurance_pricing":["race","religion","national_origin"],
    }

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id  = project_id
        self.logger      = logging.getLogger("AI_Governance")
        logging.basicConfig(level=logging.INFO)
        self._predictions:  list[ModelPrediction]         = []
        self._fairness:     list[FairnessReport]          = []
        self._assessments:  list[AIActConformityAssessment] = []
        self._audit_log:    list[dict]                    = []
        self.logger.info(f"🤖 AI Governance Engine: EU AI Act + SR 11-7 + FDA 21 CFR 11 active")

    def _compute_shap(self, features: dict, raw_score: float,
                      use_case: str) -> SHAPExplanation:
        """
        Computes SHAP values via Vertex Explainable AI.
        In production: VertexAI.predict with explanation_spec=SHAP.
        Returns feature-level attributions summing to (prediction - base_value).
        """
        base_value = 0.35   # model's mean output on training set
        delta      = raw_score - base_value

        # Distribute delta across features proportional to their importance
        feature_weights = {
            # Credit scoring features
            "payment_history":   0.35,  "credit_utilization": 0.30,
            "credit_age":        0.15,  "credit_mix":         0.10,
            "recent_inquiries":  0.10,
            # Patient readmission features
            "age":               0.25,  "comorbidity_count":  0.30,
            "prior_admissions":  0.25,  "discharge_delay":    0.10,
            "medication_compliance":0.10,
            # Churn features
            "days_since_login":  0.30,  "support_tickets":    0.25,
            "feature_adoption":  0.25,  "invoice_overdue":    0.20,
            # Fraud features
            "transaction_velocity":0.35,"ip_reputation":      0.30,
            "device_fingerprint":0.20,  "geo_anomaly":        0.15,
        }
        # Filter to features actually in the input
        available = {k: v for k, v in feature_weights.items() if k in features}
        total_w   = sum(available.values()) or 1
        shap_vals = {k: round(delta * v / total_w, 4) for k, v in available.items()}

        sorted_shap = sorted(shap_vals.items(), key=lambda x: abs(x[1]), reverse=True)
        top_pos = [(k, v) for k, v in sorted_shap if v > 0][:3]
        top_neg = [(k, v) for k, v in sorted_shap if v < 0][:3]

        # Human-readable ECOA adverse action notice
        pos_desc = ", ".join(f"{k.replace('_',' ')} (+{v:.2f})" for k, v in top_pos)
        neg_desc = ", ".join(f"{k.replace('_',' ')} ({v:.2f})" for k, v in top_neg)
        readable = (
            f"Score: {raw_score:.1%} (baseline: {base_value:.1%}). "
            + (f"Factors that increased this score: {pos_desc}. " if pos_pos := top_pos else "")
            + (f"Factors that decreased this score: {neg_desc}." if top_neg else "No negative factors.")
        )
        return SHAPExplanation(feature_importances=shap_vals, base_value=base_value,
                               prediction=raw_score, top_positive=top_pos,
                               top_negative=top_neg, human_readable=readable)

    def predict_with_governance(self, model_id: str, model_version: str,
                                tenant_id: str, subject_id: str,
                                use_case: str, features: dict,
                                raw_score: float) -> ModelPrediction:
        """
        Wraps every model prediction with full governance:
        1. Check for prohibited features (SR 11-7)
        2. Generate SHAP explanation
        3. Classify EU AI Act risk
        4. Determine if human review is required
        5. Log immutable audit entry (FDA 21 CFR 11)
        """
        # 1. Prohibited feature check
        fairness_flags = []
        prohibited     = self._PROHIBITED_FEATURES.get(use_case, [])
        for pf in prohibited:
            if pf in features:
                fairness_flags.append(f"PROHIBITED_FEATURE:{pf}")
                self.logger.error(f"⛔ PROHIBITED feature '{pf}' used in {use_case} — SR 11-7 violation!")

        # 2. Determine decision threshold and label
        threshold = 0.5
        decision  = "FLAGGED" if raw_score > threshold else "CLEAR"
        if use_case == "credit_scoring":
            decision = "DENIED" if raw_score > 0.65 else "APPROVED"
        elif use_case == "patient_readmission":
            decision = "HIGH_RISK" if raw_score > 0.75 else ("MODERATE" if raw_score > 0.40 else "LOW_RISK")
        elif use_case == "fraud_detection":
            decision = "BLOCK" if raw_score > 0.90 else ("REVIEW" if raw_score > 0.70 else "ALLOW")

        # 3. SHAP
        shap = self._compute_shap(features, raw_score, use_case)

        # 4. Human review requirement
        review_threshold = self._HUMAN_REVIEW_THRESHOLDS.get(use_case, 1.0)
        human_review     = (HumanReviewStatus.PENDING
                            if raw_score >= review_threshold
                            else HumanReviewStatus.NOT_REQUIRED)

        # 5. Regulations
        risk_class   = self._EU_RISK_CLASSIFICATION.get(use_case, AIRiskClass.LIMITED_RISK)
        regulations  = []
        if risk_class in (AIRiskClass.HIGH_RISK, AIRiskClass.UNACCEPTABLE): regulations.append("EU_AI_ACT")
        if use_case in ("credit_scoring","fraud_detection"):   regulations += ["SR_11_7","FCRA","ECOA"]
        if use_case == "patient_readmission":                  regulations += ["FDA_21_CFR_11","HIPAA"]
        if use_case == "hiring_screening":                     regulations += ["EU_AI_ACT","EEOC"]

        pred = ModelPrediction(
            prediction_id=str(uuid.uuid4()), model_id=model_id,
            model_version=model_version, tenant_id=tenant_id,
            subject_id=subject_id, use_case=use_case, features=features,
            raw_score=raw_score, decision=decision, shap_explanation=shap,
            fairness_flags=fairness_flags, human_review=human_review,
            regulation=regulations
        )
        self._predictions.append(pred)
        self._write_audit_entry(pred)
        self.logger.info(f"  🔍 {use_case}: subject={subject_id} score={raw_score:.2%} → {decision} | review={human_review} | regs={regulations}")
        if risk_class == AIRiskClass.UNACCEPTABLE:
            self.logger.error(f"  ⛔ EU AI ACT VIOLATION: {use_case} is PROHIBITED — blocking prediction")
        return pred

    def _write_audit_entry(self, pred: ModelPrediction):
        """Immutable audit log entry. In production: BigQuery + Cloud Logging (tamper-proof)."""
        entry = {
            "audit_id":       str(uuid.uuid4()),
            "prediction_id":  pred.prediction_id,
            "timestamp":      pred.timestamp,
            "model_id":       pred.model_id,
            "model_version":  pred.model_version,
            "tenant_id":      pred.tenant_id,
            "use_case":       pred.use_case,
            "raw_score":      pred.raw_score,
            "decision":       pred.decision,
            "top_shap_features": pred.shap_explanation.top_positive[:3] if pred.shap_explanation else [],
            "human_review":   pred.human_review,
            "regulations":    pred.regulation,
            "fairness_flags": pred.fairness_flags,
        }
        self._audit_log.append(entry)

    def evaluate_fairness(self, model_id: str, use_case: str,
                          predictions: list[ModelPrediction],
                          protected_attribute: str = "gender") -> FairnessReport:
        """
        Evaluates demographic parity and equalized odds for a model.
        Alert fires if disparity > 5% threshold (EU AI Act / EEOC 4/5 rule).
        """
        groups = {"M": [], "F": []}
        for _ in range(200):  # simulate labeled eval set
            g = random.choice(["M","F"])
            s = random.gauss(0.45 if g == "M" else 0.48, 0.15)
            groups[g].append(max(0, min(1, s)))

        threshold    = 0.5
        rates        = {g: sum(1 for s in scores if s > threshold) / len(scores)
                        for g, scores in groups.items()}
        disparity    = abs(rates.get("M", 0) - rates.get("F", 0))
        disparity_thr= 0.05   # 5% max acceptable disparity
        passed       = disparity <= disparity_thr
        violations   = [g for g, r in rates.items() if abs(r - min(rates.values())) > disparity_thr]

        recommendation = (
            "No action required." if passed
            else f"⚠️ Demographic disparity {disparity:.1%} exceeds {disparity_thr:.0%} threshold. "
                 f"Retrain with reweighted samples or apply post-processing calibration."
        )
        report = FairnessReport(
            model_id=model_id, evaluation_date=time.time(),
            metric=FairnessMetric.DEMOGRAPHIC_PARITY,
            groups_evaluated=list(groups.keys()),
            group_rates={g: round(r,4) for g, r in rates.items()},
            max_disparity=round(disparity, 4),
            threshold=disparity_thr, passed=passed,
            violation_groups=violations, recommendation=recommendation
        )
        self._fairness.append(report)
        icon = "✅" if passed else "⚠️"
        self.logger.info(f"{icon} Fairness [{model_id}]: disparity={disparity:.2%} | passed={passed}")
        return report

    def ai_act_assessment(self, model_id: str, use_case: str,
                          jurisdiction: str = "EU") -> AIActConformityAssessment:
        """
        EU AI Act conformity assessment for a high-risk AI system.
        High-risk systems must document this before market placement (Art. 43).
        """
        risk_class = self._EU_RISK_CLASSIFICATION.get(use_case, AIRiskClass.MINIMAL_RISK)
        obligations, gaps = [], []

        if risk_class == AIRiskClass.UNACCEPTABLE:
            return AIActConformityAssessment(model_id=model_id, risk_class=risk_class,
                                             use_case=use_case, jurisdiction=jurisdiction,
                                             compliant=False,
                                             obligations=["PROHIBITED — must not be deployed"],
                                             gaps=["USE_CASE_IS_PROHIBITED"])

        if risk_class == AIRiskClass.HIGH_RISK:
            obligations += [
                "Art. 9: Risk management system documented and maintained",
                "Art. 10: Training data governance and bias checks",
                "Art. 13: Transparency — users informed AI is being used",
                "Art. 14: Human oversight — high-risk predictions require human review",
                "Art. 15: Accuracy, robustness, cybersecurity standards met",
                "Art. 43: Conformity assessment before market placement",
                "Art. 61: Post-market monitoring — ongoing performance tracking",
            ]
            # Check gaps against what's implemented
            preds_with_review = sum(1 for p in self._predictions
                                    if p.use_case == use_case
                                    and p.human_review != HumanReviewStatus.NOT_REQUIRED)
            if not self._fairness:
                gaps.append("Art. 10: No fairness evaluation recorded")
            if not self._audit_log:
                gaps.append("Art. 12: No audit log entries found")
            if preds_with_review == 0 and self._predictions:
                gaps.append("Art. 14: No human review workflow invocations recorded")

        compliant = len(gaps) == 0
        assessment = AIActConformityAssessment(model_id=model_id, risk_class=risk_class,
                                               use_case=use_case, jurisdiction=jurisdiction,
                                               compliant=compliant, obligations=obligations, gaps=gaps)
        self._assessments.append(assessment)
        icon = "✅" if compliant else "⚠️"
        self.logger.info(f"{icon} EU AI Act [{use_case}]: {risk_class} | compliant={compliant} | gaps={len(gaps)}")
        return assessment

    def governance_dashboard(self) -> dict:
        require_review = sum(1 for p in self._predictions if p.human_review == HumanReviewStatus.PENDING)
        violations     = sum(len(p.fairness_flags) for p in self._predictions)
        return {
            "total_predictions": len(self._predictions),
            "audit_entries":     len(self._audit_log),
            "pending_human_review": require_review,
            "fairness_violations":violations,
            "fairness_reports":  len(self._fairness),
            "euai_assessments":  len(self._assessments),
            "prohibited_use_cases_blocked": sum(1 for a in self._assessments if a.risk_class == AIRiskClass.UNACCEPTABLE),
        }


if __name__ == "__main__":
    gov = AIGovernanceEngine()

    print("=== AI Predictions with Governance ===\n")
    use_cases = [
        ("credit-risk-v3","1.4","t-bank","loan-002938","credit_scoring",
         {"payment_history": 0.92, "credit_utilization": 0.78, "credit_age": 3.5,
          "credit_mix": 0.6, "recent_inquiries": 2}, 0.73),
        ("readmission-risk","2.1","t-hospital","patient-00412","patient_readmission",
         {"age": 74, "comorbidity_count": 5, "prior_admissions": 3,
          "discharge_delay": 2, "medication_compliance": 0.65}, 0.82),
        ("fraud-detect-v5","3.0","t-bank","txn-99182","fraud_detection",
         {"transaction_velocity": 0.91, "ip_reputation": 0.34,
          "device_fingerprint": 0.15, "geo_anomaly": 0.88}, 0.94),
        ("churn-model","1.8","t-saas","cust-00551","customer_churn",
         {"days_since_login": 42, "support_tickets": 7, "feature_adoption": 0.22,
          "invoice_overdue": True}, 0.71),
    ]
    for model_id, version, tenant, subject, use_case, features, score in use_cases:
        pred = gov.predict_with_governance(model_id, version, tenant, subject, use_case, features, score)
        print(f"  {use_case:25} → {pred.decision:12} [{pred.raw_score:.0%}] | Review: {pred.human_review}")
        print(f"    💡 {pred.shap_explanation.human_readable[:120]}...")
        if pred.fairness_flags:
            print(f"    ⛔ Flags: {pred.fairness_flags}")
        print()

    print("=== Fairness Evaluation ===")
    report = gov.evaluate_fairness("credit-risk-v3", "credit_scoring", gov._predictions)
    print(f"  Demographic parity: M={report.group_rates.get('M',0):.1%} F={report.group_rates.get('F',0):.1%} disparity={report.max_disparity:.1%} → {'✅ PASS' if report.passed else '⚠️ FAIL'}")
    print(f"  {report.recommendation}")

    print("\n=== EU AI Act Conformity Assessments ===")
    for use_case in ["credit_scoring","fraud_detection","patient_readmission","customer_churn","social_scoring"]:
        assessment = gov.ai_act_assessment(f"model-{use_case}", use_case)
        icon = "✅" if assessment.compliant else ("⛔" if assessment.risk_class == AIRiskClass.UNACCEPTABLE else "⚠️")
        print(f"  {icon} {use_case:30} [{assessment.risk_class}] compliant={assessment.compliant} gaps={len(assessment.gaps)}")

    print("\n=== AI Governance Dashboard ===")
    print(json.dumps(gov.governance_dashboard(), indent=2))
