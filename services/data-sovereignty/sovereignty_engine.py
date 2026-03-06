# services/data-sovereignty/sovereignty_engine.py
"""
Epic 71: Data Sovereignty & Cross-Border Governance
Ensures every byte of data lives in the legally correct GCP region
and can only cross borders via validated transfer mechanisms.

Data residency = WHERE data physically lives (GCP region).
Data sovereignty = WHO has legal authority over that data.
Cross-border transfer = the legal mechanism permitting data to move.

Architecture:
  - Every table tagged with: jurisdiction, PII level, transfer eligibility
  - Before any cross-border operation: TransferValidator checks legal basis
  - Sovereignty Map: live visualization of all assets vs their legal homes
  - Region pinning: BigQuery dataset pinned to exact GCP region
  - PIPL (China) & data localization laws: strictly enforced as PROHIBITED
"""
import logging, json, uuid, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class PIILevel(str, Enum):
    NONE       = "NONE"        # no personal data
    PSEUDONYMOUS = "PSEUDONYMOUS"  # indirectly identifiable
    PERSONAL   = "PERSONAL"   # directly identifiable
    SENSITIVE  = "SENSITIVE"   # special category (health, biometric, financial, religious)

class TransferStatus(str, Enum):
    PERMITTED   = "PERMITTED"
    CONDITIONAL = "CONDITIONAL"
    PROHIBITED  = "PROHIBITED"

@dataclass
class GCPRegion:
    region_id:   str     # e.g. "europe-west1"
    location:    str     # e.g. "Belgium"
    jurisdiction:str     # ISO 3166-1 or bloc: "EU", "US", "CN", "IN", etc.
    country:     str     # two-letter country code
    data_center: str     # city
    gdpr_compliant: bool
    laws:        list[str]  # applicable privacy laws

@dataclass
class DataAsset:
    asset_id:       str
    name:           str
    asset_type:     str    # "TABLE" | "BUCKET" | "TOPIC" | "MODEL"
    gcp_region:     str    # pinned region
    jurisdiction:   str    # e.g. "EU", "US", "CN"
    pii_level:      PIILevel
    data_subjects_locations: list[str]  # country codes of data subjects
    transfer_eligible: bool
    transfer_mechanism: str
    row_count:      int
    tags:           dict = field(default_factory=dict)
    classified_at:  float = field(default_factory=time.time)

@dataclass
class TransferRequest:
    request_id:   str
    asset_id:     str
    source_region:str
    dest_region:  str
    source_jurisdiction:str
    dest_jurisdiction:  str
    requestor:    str
    purpose:      str
    status:       TransferStatus
    mechanism:    Optional[str]
    conditions:   list[str]
    risk_level:   str   # "LOW" | "MEDIUM" | "HIGH" | "BLOCKED"
    requested_at: float = field(default_factory=time.time)

class SovereigntyEngine:
    """
    Enforces data residency and cross-border transfer governance.
    Every data asset is registered with its jurisdiction and PII level.
    Transfer requests are validated before any data movement.
    """
    # GCP regions mapped to their legal jurisdictions
    GCP_REGIONS: dict[str, GCPRegion] = {
        "us-central1":    GCPRegion("us-central1",    "Iowa, USA",          "US","US","Council Bluffs",   False,["CCPA"]),
        "us-east1":       GCPRegion("us-east1",       "South Carolina, USA","US","US","Moncks Corner",    False,["CCPA"]),
        "us-west1":       GCPRegion("us-west1",       "Oregon, USA",        "US","US","The Dalles",       False,["CCPA"]),
        "europe-west1":   GCPRegion("europe-west1",   "Belgium",            "EU","BE","Saint-Ghislain",   True, ["GDPR"]),
        "europe-west2":   GCPRegion("europe-west2",   "United Kingdom",     "GB","GB","London",           False,["UK_GDPR"]),
        "europe-west3":   GCPRegion("europe-west3",   "Germany",            "EU","DE","Frankfurt",        True, ["GDPR"]),
        "europe-west4":   GCPRegion("europe-west4",   "Netherlands",        "EU","NL","Eemshaven",        True, ["GDPR"]),
        "europe-north1":  GCPRegion("europe-north1",  "Finland",            "EU","FI","Hamina",           True, ["GDPR"]),
        "asia-northeast1":GCPRegion("asia-northeast1","Japan",              "JP","JP","Tokyo",            False,["APPI"]),
        "asia-northeast3":GCPRegion("asia-northeast3","South Korea",        "KR","KR","Seoul",            False,["PIPA"]),
        "asia-east1":     GCPRegion("asia-east1",     "Taiwan",             "TW","TW","Changhua",         False,[]),
        "asia-east2":     GCPRegion("asia-east2",     "Hong Kong",          "HK","HK","Hong Kong",        False,[]),
        "asia-southeast1":GCPRegion("asia-southeast1","Singapore",          "SG","SG","Jurong West",      False,["PDPA_SG"]),
        "asia-southeast2":GCPRegion("asia-southeast2","Indonesia",          "ID","ID","Jakarta",          False,[]),
        "asia-south1":    GCPRegion("asia-south1",    "India",              "IN","IN","Mumbai",           False,["DPDP"]),
        "australia-southeast1":GCPRegion("australia-southeast1","Australia","AU","AU","Sydney",           False,[]),
        "southamerica-east1":GCPRegion("southamerica-east1","Brazil",       "BR","BR","Osasco",           False,["LGPD"]),
        "me-central1":    GCPRegion("me-central1",    "Qatar",              "QA","QA","Doha",             False,["PDPL"]),
        "me-west1":       GCPRegion("me-west1",       "Israel",             "IL","IL","Tel Aviv",         False,[]),
        "africa-south1":  GCPRegion("africa-south1",  "South Africa",       "ZA","ZA","Johannesburg",     False,["POPIA"]),
    }

    # Cross-border transfer rules: (source_jurisdiction, dest_jurisdiction) → mechanism
    # "PROHIBITED" means the law explicitly bans this transfer (e.g. PIPL China → anywhere)
    _TRANSFER_MATRIX = {
        ("EU", "US"):  ("CONDITIONAL", "Standard Contractual Clauses (SCCs) required", "MEDIUM"),
        ("EU", "GB"):  ("PERMITTED",   "UK-EU adequacy decision in force",             "LOW"),
        ("EU", "CN"):  ("PROHIBITED",  "No EU-China adequacy decision; PIPL restricts inbound transfer", "BLOCKED"),
        ("EU", "IN"):  ("CONDITIONAL", "SCCs required; DPDP adequacy pending",         "MEDIUM"),
        ("EU", "JP"):  ("PERMITTED",   "EU-Japan adequacy decision (2019) in force",   "LOW"),
        ("EU", "KR"):  ("PERMITTED",   "EU-Korea adequacy decision (2021) in force",   "LOW"),
        ("EU", "SG"):  ("CONDITIONAL", "SCCs required",                                "MEDIUM"),
        ("EU", "BR"):  ("CONDITIONAL", "SCCs required under LGPD",                    "MEDIUM"),
        ("EU", "AU"):  ("CONDITIONAL", "SCCs required",                                "MEDIUM"),
        ("CN", "US"):  ("PROHIBITED",  "PIPL: cross-border transfer requires PAISS + CAC approval, effectively prohibited for analytics", "BLOCKED"),
        ("CN", "EU"):  ("PROHIBITED",  "PIPL: same restriction applies",              "BLOCKED"),
        ("CN", "HK"):  ("CONDITIONAL", "PIPL allows transfer to HK under specific conditions","HIGH"),
        ("US", "EU"):  ("PERMITTED",   "EU-US Data Privacy Framework (2023) in force", "LOW"),
        ("US", "CN"):  ("CONDITIONAL", "PIPL governs the inbound side; SCCs + CAC approval required","HIGH"),
        ("IN", "EU"):  ("CONDITIONAL", "DPDP: government may restrict transfers; SCCs recommended","MEDIUM"),
        ("IN", "US"):  ("CONDITIONAL", "No adequacy decision; SCCs recommended",      "MEDIUM"),
        ("GB", "EU"):  ("PERMITTED",   "UK-EU adequacy decision in force",             "LOW"),
        ("GB", "US"):  ("CONDITIONAL", "International Data Transfer Agreements required","MEDIUM"),
        ("JP", "EU"):  ("PERMITTED",   "EU-Japan adequacy decision in force",          "LOW"),
        ("JP", "US"):  ("CONDITIONAL", "APEC CBPR or contractual safeguards required","MEDIUM"),
        ("BR", "EU"):  ("CONDITIONAL", "LGPD: adequacy or equivalent protection required","MEDIUM"),
        ("SG", "US"):  ("PERMITTED",   "APEC CBPR in force",                          "LOW"),
    }

    def __init__(self):
        self.logger = logging.getLogger("Sovereignty_Engine")
        logging.basicConfig(level=logging.INFO)
        self._assets:   dict[str, DataAsset]      = {}
        self._requests: list[TransferRequest]     = []
        self._seed_assets()
        self.logger.info(f"🗺️  Data Sovereignty Engine: {len(self._assets)} assets registered across {len(self.GCP_REGIONS)} GCP regions.")

    def _seed_assets(self):
        seed = [
            ("salesforce.customers",    "TABLE",  "europe-west3", "EU",  PIILevel.PERSONAL,  ["DE","FR","GB","US"],  True),
            ("stripe.charges",          "TABLE",  "us-central1",  "US",  PIILevel.SENSITIVE,  ["US","CA","MX"],       True),
            ("analytics.monthly_revenue","TABLE", "europe-west1", "EU",  PIILevel.NONE,       [],                     True),
            ("clinical.patient_outcomes","TABLE", "us-east1",     "US",  PIILevel.SENSITIVE,  ["US"],                 False),
            ("alti_raw.events",          "TABLE", "us-central1",  "US",  PIILevel.PSEUDONYMOUS,["US","GB","JP","AU"],  True),
            ("jp_customers",             "TABLE", "asia-northeast1","JP", PIILevel.PERSONAL,  ["JP"],                 False),
            ("cn_users",                 "TABLE", "asia-east1",   "CN",  PIILevel.PERSONAL,   ["CN"],                 False),
            ("br_transactions",          "TABLE", "southamerica-east1","BR",PIILevel.SENSITIVE,["BR"],                False),
            ("apac_analytics",           "TABLE", "asia-southeast1","SG", PIILevel.NONE,      ["SG","AU","ID","TH"],  True),
            ("models_bucket",            "BUCKET","us-central1",  "US",  PIILevel.NONE,       [],                     True),
        ]
        for name, atype, region, jurisdiction, pii, subjects, transferable in seed:
            mech = "SCCs" if transferable else "LOCALIZED"
            asset = DataAsset(asset_id=f"ast-{uuid.uuid4().hex[:8]}", name=name,
                              asset_type=atype, gcp_region=region, jurisdiction=jurisdiction,
                              pii_level=pii, data_subjects_locations=subjects,
                              transfer_eligible=transferable, transfer_mechanism=mech,
                              row_count=1000 + hash(name) % 900_000)
            self._assets[asset.asset_id] = asset

    def classify_asset(self, asset_id: str, pii_level: PIILevel,
                       data_subjects_locations: list[str]) -> DataAsset:
        """Auto-classification result applied to an asset."""
        asset = self._assets.get(asset_id)
        if not asset: raise ValueError(f"Asset {asset_id} not found")
        asset.pii_level = pii_level
        asset.data_subjects_locations = data_subjects_locations
        asset.transfer_eligible = pii_level in [PIILevel.NONE, PIILevel.PSEUDONYMOUS]
        asset.classified_at = time.time()
        self.logger.info(f"🏷️  Classified: {asset.name} → PII={pii_level} | subjects: {data_subjects_locations}")
        return asset

    def validate_transfer(self, asset_id: str, dest_region: str,
                          requestor: str, purpose: str) -> TransferRequest:
        """
        Validates whether an asset can legally move from its current region
        to the requested destination. Checks the transfer matrix for all
        applicable jurisdiction pairs.
        """
        asset = next((a for a in self._assets.values() if a.asset_id == asset_id or a.name == asset_id), None)
        if not asset: raise ValueError(f"Asset {asset_id} not found")
        dest  = self.GCP_REGIONS.get(dest_region)
        if not dest: raise ValueError(f"Region {dest_region} not registered")

        src_jurisdiction  = asset.jurisdiction
        dest_jurisdiction = dest.jurisdiction
        key = (src_jurisdiction, dest_jurisdiction)
        rev = (dest_jurisdiction, src_jurisdiction)

        if src_jurisdiction == dest_jurisdiction:
            status, mechanism, conditions, risk = (TransferStatus.PERMITTED, "Intra-jurisdiction", [], "LOW")
        elif key in self._TRANSFER_MATRIX:
            raw_status, mechanism, risk = self._TRANSFER_MATRIX[key]
            status = TransferStatus(raw_status)
            conditions = [mechanism] if raw_status != "PERMITTED" else []
            mechanism  = mechanism
        elif rev in self._TRANSFER_MATRIX:
            raw_status, mechanism, risk = self._TRANSFER_MATRIX[rev]
            status = TransferStatus("CONDITIONAL" if raw_status == "PERMITTED" else raw_status)
            conditions = [mechanism]
        else:
            status, mechanism, conditions, risk = (TransferStatus.CONDITIONAL, "SCCs required (no specific adequacy decision)", ["Consult legal team"], "MEDIUM")

        # Extra: if data is localized (e.g. CN, IN patient data), block regardless
        if not asset.transfer_eligible and status != TransferStatus.PROHIBITED:
            status = TransferStatus.PROHIBITED
            conditions = [f"Asset '{asset.name}' is flagged as non-transferable due to data localization requirements"]
            risk = "BLOCKED"

        req = TransferRequest(request_id=str(uuid.uuid4()), asset_id=asset.asset_id,
                              source_region=asset.gcp_region, dest_region=dest_region,
                              source_jurisdiction=src_jurisdiction, dest_jurisdiction=dest_jurisdiction,
                              requestor=requestor, purpose=purpose,
                              status=status, mechanism=mechanism,
                              conditions=conditions, risk_level=risk)
        self._requests.append(req)
        icon = "✅" if status == TransferStatus.PERMITTED else ("⚠️" if status == TransferStatus.CONDITIONAL else "❌")
        self.logger.info(f"{icon} Transfer: {asset.name} ({src_jurisdiction}) → {dest_region} ({dest_jurisdiction}): {status} [{risk}]")
        return req

    def sovereignty_map(self) -> dict:
        """Powers the live sovereignty map dashboard."""
        by_region: dict[str, list] = {}
        for asset in self._assets.values():
            by_region.setdefault(asset.gcp_region, []).append({
                "name": asset.name, "pii_level": asset.pii_level,
                "transfer_eligible": asset.transfer_eligible,
                "subjects": asset.data_subjects_locations,
                "row_count": asset.row_count
            })
        recent_transfers = [{"request_id": r.request_id[:12], "asset": r.asset_id[:12],
                             "from": r.source_jurisdiction, "to": r.dest_jurisdiction,
                             "status": r.status, "risk": r.risk_level}
                            for r in self._requests[-10:]]
        return {
            "total_assets":  len(self._assets),
            "regions_used":  len(by_region),
            "by_region":     {r: {"assets": len(v), "sensitive_count": sum(1 for a in v if a["pii_level"] == "SENSITIVE")} for r, v in by_region.items()},
            "pii_breakdown": {level: sum(1 for a in self._assets.values() if a.pii_level == level) for level in PIILevel},
            "non_transferable": sum(1 for a in self._assets.values() if not a.transfer_eligible),
            "recent_transfers": recent_transfers,
        }


if __name__ == "__main__":
    engine = SovereigntyEngine()
    map_data = engine.sovereignty_map()
    print(f"🗺️  Sovereignty Map: {map_data['total_assets']} assets in {map_data['regions_used']} GCP regions")
    print(f"   PII breakdown: {map_data['pii_breakdown']}")
    print(f"   Non-transferable assets: {map_data['non_transferable']}")

    print("\n=== Transfer Validation Matrix ===")
    scenarios = [
        ("salesforce.customers", "us-central1",       "data-team@alti.ai",  "US expansion analytics"),
        ("salesforce.customers", "asia-northeast1",   "data-team@alti.ai",  "APAC reporting"),
        ("stripe.charges",       "europe-west1",      "cfo@alti.ai",        "EU revenue reporting"),
        ("jp_customers",         "us-central1",       "eng@alti.ai",        "global ML training"),
        ("cn_users",             "us-central1",       "eng@alti.ai",        "global ML training"),
        ("clinical.patient_outcomes","europe-west1",  "research@alti.ai",   "EU clinical trial"),
        ("br_transactions",      "europe-west3",      "legal@alti.ai",      "GDPR joint controller"),
    ]
    for asset, dest, req, purpose in scenarios:
        try:
            result = engine.validate_transfer(asset, dest, req, purpose)
            icon = "✅" if result.status == TransferStatus.PERMITTED else ("⚠️" if result.status == TransferStatus.CONDITIONAL else "❌")
            print(f"  {icon} {asset:30} → {dest:25} [{result.risk_level}]")
            for c in result.conditions:
                print(f"      ↳ {c}")
        except Exception as e:
            print(f"  ❌ {asset} → {dest}: {e}")
