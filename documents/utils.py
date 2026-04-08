import os
import re

PATTERNS = [
    # 1. High Priority Domain Specific (Must be checked before general terms)
    (r"\b(partnership|jv|clms).*agreement", "Partnership/JV Agreement"),
    (r"\b(contract|award)\b", "Project Contract/Award Letter"),
    (r"\b(guarantee|bond)\b", "Financial Guarantee/Bond"),
    
    # 2. Vehicle Specific (Must check 'vehicle' keyword to avoid capturing general registration)
    (r"\b(vehicle).*(registration|reg\b)", "Vehicle Registration Certificate"),
    (r"\b(insurance)\b", "Insurance Certificate"),
    (r"\b(inspection|safety)\b", "Safety Inspection Certificate"),
    (r"\b(ownership|title)\b", "Proof of Ownership"),

    # 3. General Registration and Tax (Should catch 'registration' if NOT preceded by 'vehicle')
    (r"\b(company).*?(registration|reg\b)", "Company Registration"),
    (r"\b(tax|tin|vat)\b", "Tax Certificate"),
    (r"\bregistration\b", "Registration Certificate"),

    # 4. Professional/Contractor Documents
    (r"(national\s*id|nid|kebele)", "National ID Copy"),
    (r"(experience).*(letter)?", "Experience Letter"),
    (r"(transcript)", "Transcripts"),
    (r"(previous).*(license)", "Previous License"),
    (r"(customs)", "Customs License"),
    (r"\b(specs?|specification|specifications)\b", "Item Specifications"),
    (r"(pro\s*forma|proforma).*invoice", "Proforma Invoice"),
    (r"(invoice)", "Invoice"),
    
    # Generic matches at the bottom
    (r"(degree|diploma|graduat|university|college|educational).*certificate", "Degree Certificate"),
    (r"(degree|diploma)", "Degree Certificate"),
    (r"(license)", "License"),
    (r"(logo|photo|image|picture|profile)", "Company Logo/Photo"),
    (r"(certificate)", "Certificate"),
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

