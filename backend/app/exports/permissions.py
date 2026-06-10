from __future__ import annotations

from app.models import FormLead
from app.services.presentation import redact_sensitive

NO_CONSENT_REDACTED = "NO_CONSENT_REDACTED"


def public_export_value(value: object) -> object:
    return redact_sensitive(value)


def consented_form_value(form_lead: FormLead, value: object) -> object:
    if form_lead.consent_to_contact:
        return redact_sensitive(value)
    return NO_CONSENT_REDACTED


def consented_at_value(form_lead: FormLead, consented_at: object) -> object:
    if form_lead.consent_to_contact:
        return consented_at
    return ""
