from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    COURT_NEW_CASES = "court_new_cases"
    COURT_CASE_SEARCH = "court_case_search"
    UCC_REGISTRY = "ucc_registry"
    BUSINESS_REGISTRY = "business_registry"
    FEDERAL_BANKRUPTCY = "federal_bankruptcy"
    MANUAL_UPLOAD = "manual_upload"


class AccessMethod(StrEnum):
    MOCK = "mock"
    MANUAL_IMPORT = "manual_import"
    LIVE_IF_ALLOWED = "live_if_allowed"
    LICENSED_BULK = "licensed_bulk"


class ArtifactType(StrEnum):
    HTML = "html"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    TXT = "txt"
    SCREENSHOT = "screenshot"
    MANUAL = "manual"


class SignalType(StrEnum):
    LITIGATION_NEW_CASE = "litigation_new_case"
    LITIGATION_UPDATE = "litigation_update"
    UCC_INITIAL = "ucc_initial"
    UCC_AMENDMENT = "ucc_amendment"
    UCC_ASSIGNMENT = "ucc_assignment"
    UCC_CONTINUATION = "ucc_continuation"
    UCC_TERMINATION = "ucc_termination"
    BANKRUPTCY_MCA_CREDITOR = "bankruptcy_mca_creditor"
    MANUAL = "manual"


class LeadSignalGrade(StrEnum):
    A_PLUS = "A_PLUS"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    EXCLUDE = "EXCLUDE"


class LeadSignalStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    DELIVERED = "delivered"
    SUPPRESSED = "suppressed"
    EXCLUDED = "excluded"


class DeliveryMethod(StrEnum):
    DASHBOARD = "dashboard"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CSV = "csv"


class SuppressionType(StrEnum):
    BUSINESS_NAME = "business_name"
    PERSON_NAME = "person_name"
    PHONE = "phone"
    EMAIL = "email"
    CASE_NUMBER = "case_number"
    DOMAIN = "domain"


class SequenceType(StrEnum):
    BATCH = "batch"
    LEAD_REFERENCE = "lead_reference"
    FORM_LEAD = "form_lead"
    DELIVERY = "delivery"


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class LeadContactType(StrEnum):
    BUSINESS_PHONE = "business_phone"
    BUSINESS_EMAIL = "business_email"
    WEBSITE = "website"
    OWNER_PRINCIPAL = "owner_principal"
    REGISTERED_AGENT = "registered_agent"
    MAILING_ADDRESS = "mailing_address"
    PHYSICAL_ADDRESS = "physical_address"


class ContactVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    INVALID = "invalid"
    RISKY = "risky"
    UNKNOWN = "unknown"
