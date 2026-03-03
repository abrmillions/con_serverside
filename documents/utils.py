import os
import re

PATTERNS = [
    (r"(national\s*id|nid|kebele)", "National ID Copy"),
    (r"(company).*?(registration|reg\b)", "Company Registration"),
    (r"\b(tax|tin|vat)\b", "Tax Certificate"),
    (r"(experience).*(letter)?", "Experience Letter"),
    (r"(degree|diploma|certificate)", "Degree Certificate"),
    (r"(transcript)", "Transcripts"),
    (r"(previous).*(license)", "Previous License"),
    (r"(customs)", "Customs License"),
    (r"(specs?|specification|specifications)", "Item Specifications"),
    (r"(pro\s*forma|proforma).*invoice", "Proforma Invoice"),
    (r"(invoice)", "Invoice"),
    (r"(insurance)", "Insurance Certificate"),
    (r"(vehicle).*(registration)|\bregistration\b", "Vehicle Registration Certificate"),
    (r"(inspection|safety)", "Safety Inspection Certificate"),
    (r"(ownership|title)", "Proof of Ownership"),
    (r"(partnership|jv).*agreement", "Partnership/JV Agreement"),
    (r"(license)", "License"),
    (r"(contract|award)", "Project Contract/Award Letter"),
    (r"(guarantee|bond)", "Financial Guarantee/Bond"),
    (r"(photo|image|picture)", "Photo"),
]

def infer_document_name(name_or_path: str) -> str:
    base = name_or_path or ""
    base = os.path.basename(base)
    stem = os.path.splitext(base)[0]
    s = stem.replace("_", " ").replace("-", " ").strip().lower()
    for pat, label in PATTERNS:
        if re.search(pat, s):
            return label
    parts = [p for p in re.split(r"\s+", s) if p]
    return " ".join(w.capitalize() for w in parts[:6]) or "Document"

