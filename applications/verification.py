# applications/verification.py
import io
import os
import time
import json
import base64
import random
import socket
import requests
import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any, List

# Django imports
from django.utils import timezone
from django.conf import settings

# OCR imports
try:
    import pytesseract
    from PIL import Image
    PIL_AVAILABLE = True
    
    # Windows-specific Tesseract path configuration
    if os.name == 'nt':
        # Common Tesseract installation paths on Windows
        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.environ.get("USERPROFILE", ""), r"AppData\Local\Tesseract-OCR\tesseract.exe"),
            r"C:\Users\pc\AppData\Local\Tesseract-OCR\tesseract.exe", # Specific user path from previous logs
            r"C:\Users\pc\AppData\Local\Programs\Tesseract-OCR\tesseract.exe", # Another common user path
        ]
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"DEBUG: Found Tesseract at {path}")
                break
        else:
            print("DEBUG: Tesseract NOT found in common paths.")
except ImportError:
    pytesseract = None
    PIL_AVAILABLE = False

# Gemini import
try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    genai_new = None
    genai_types = None
    GEMINI_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False

# Import your document utilities
try:
    from documents.utils import infer_document_name
except ImportError:
    def infer_document_name(name):
        return name or "unknown"


# ============================================================================
# OCR EXTRACTION FUNCTIONS
# ============================================================================

def extract_text_from_image(image_bytes: bytes, lang: str = "amh+eng") -> str:
    """Extract text from image using Tesseract OCR"""
    if not pytesseract or not PIL_AVAILABLE:
        return ""
    
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Preprocess for better OCR
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extract text with specified language
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip()
    except Exception as e:
        print(f"DEBUG: OCR Error: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_bytes: bytes, lang: str = "amh+eng") -> Tuple[str, Optional[bytes]]:
    """Extract text from PDF first page using OCR and return the rendered image"""
    if not fitz or not pytesseract:
        return "", None
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count == 0:
            return "", None
        
        # Get first page as image
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        
        # Extract text from the image
        text = extract_text_from_image(img_bytes, lang)
        return text, img_bytes
    except Exception as e:
        print(f"DEBUG: PDF OCR Error: {str(e)}")
        return "", None

def extract_text_from_document(file_content: bytes, file_ext: str, lang: str = "amh+eng") -> Tuple[str, List[str], Optional[bytes]]:
    """Extract text from document (PDF or image) and return image for AI fallback"""
    notes = []
    text = ""
    processed_image = None
    
    if file_ext in ("jpg", "jpeg", "png", "gif", "webp", "tiff", "bmp"):
        notes.append("Processing image with OCR")
        text = extract_text_from_image(file_content, lang)
        processed_image = file_content
        if text and len(text) > 10:
            notes.append(f"OCR extracted {len(text)} characters")
        else:
            notes.append("OCR failed or produced limited text - falling back to AI vision analysis")
    
    elif file_ext == "pdf":
        notes.append("Converting PDF to image for OCR")
        text, processed_image = extract_text_from_pdf(file_content, lang)
        if text and len(text) > 10:
            notes.append(f"OCR extracted {len(text)} characters from PDF")
        else:
            notes.append("OCR failed or produced limited text from PDF - falling back to AI vision analysis")
    
    else:
        notes.append(f"Unsupported file type: {file_ext}")
        text = ""
    
    return text, notes, processed_image


# ============================================================================
# DOCUMENT SPECIFICATION FUNCTIONS
# ============================================================================

def contractor_spec(label: str) -> Tuple[Optional[str], Optional[str]]:
    """Contractor module document specifications"""
    ll = (label or "").lower()
    
    if "national id" in ll:
        rules = """## National ID Copy Rules (Ethiopia)
- Look for: Ethiopian Government seal, 'የኢትዮጵያ ፌዴራላዊ ዲሞክራሲያዊ ሪፐብሊክ'
- Extract: ID Number, Full Name (Amharic + English), Date of Birth, Issue Date, Expiry Date
- Validate: ID must NOT be expired (current date: 2026-03-17)
- Check: Photo presence, official stamps, consistent fonts
- Tamper Detection: Watch for inconsistent text or edited areas"""
        
        entities = """{
            "idNumber": {"type": "string", "required": true},
            "fullNameAmharic": {"type": "string"},
            "fullNameEnglish": {"type": "string", "required": true},
            "dateOfBirth": {"type": "date", "required": true},
            "issueDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "isExpired": {"type": "boolean", "required": true},
            "hasGovernmentSeal": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "tax" in ll:
        rules = """## Tax Registration Certificate Rules (Ethiopia)
- Title: 'የግብር ከፋይ መለያ ቁጥር የምስክር ወረቀት' (Taxpayer Registration Certificate)
- Issuer: 'Ministry of Revenues' (የኢትዮጵያ ገቢዎች ሚኒስቴር) with Federal Emblem
- TIN: Extract 10-digit TIN (must be exactly 10 numbers)
- Extract: Taxpayer Name (Amharic + English), Registration Date, Tax Office
- Security: Official stamp (usually blue) and QR code should be present
- Validation: Certificate must be valid (current date: 2026-03-17)"""
        
        entities = """{
            "tin": {"type": "string", "required": true, "pattern": "^[0-9]{10}$"},
            "taxpayerNameAmharic": {"type": "string"},
            "taxpayerNameEnglish": {"type": "string", "required": true},
            "registrationDate": {"type": "date", "required": true},
            "taxOffice": {"type": "string"},
            "hasStamp": {"type": "boolean"},
            "hasQRCode": {"type": "boolean"},
            "hasEmblem": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "experience" in ll:
        rules = """## Experience Certificate Rules
- Format: Official company letterhead with address and contact
- Content: Project Name, Project Value, Position held, Start/End dates
- Verification: Company must be registered construction firm
- Validation: Dates must be logical (not future, end > start)
- Security: Official stamp and signature must overlap text"""
        
        entities = """{
            "companyName": {"type": "string", "required": true},
            "projectName": {"type": "string", "required": true},
            "projectValue": {"type": "number"},
            "position": {"type": "string", "required": true},
            "startDate": {"type": "date", "required": true},
            "endDate": {"type": "date", "required": true},
            "hasStamp": {"type": "boolean"},
            "hasSignature": {"type": "boolean"},
            "contactPhone": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "financial" in ll or "statement" in ll:
        rules = """## Financial Statement Rules
- Authenticity: Must be audited by licensed Ethiopian auditor
- Content: Total Assets, Liabilities, Net Worth, Revenue
- Auditor: Name and license number must be visible
- Validation: Net Worth = Assets - Liabilities
- Fiscal Year: Must be clearly stated"""
        
        entities = """{
            "companyName": {"type": "string", "required": true},
            "fiscalYear": {"type": "string", "required": true},
            "totalAssets": {"type": "number", "required": true},
            "totalLiabilities": {"type": "number", "required": true},
            "netWorth": {"type": "number", "required": true},
            "annualRevenue": {"type": "number"},
            "auditorName": {"type": "string", "required": true},
            "auditorLicense": {"type": "string", "required": true},
            "auditOpinion": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities

    # Degree Certificate Check - Requires academic keywords
    if any(x in ll for x in ["degree", "diploma", "graduation", "university", "college", "academic", "educational"]):
        rules = """## Degree Certificate Rules (Contractor/Professional)
- Source: Recognized university/college
- Extract: Student Name, Degree Title, Field of Study, Institution, Graduation Date
- Security: Registrar's stamp and official seal
- For foreign degrees: Check for HERQA equivalence mention"""
        
        entities = """{
            "fullName": {"type": "string", "required": true},
            "degreeTitle": {"type": "string", "required": true},
            "fieldOfStudy": {"type": "string", "required": true},
            "institutionName": {"type": "string", "required": true},
            "graduationDate": {"type": "date", "required": true},
            "cgpa": {"type": "number"},
            "isForeign": {"type": "boolean"},
            "hasEquivalence": {"type": "boolean"},
            "registrationNumber": {"type": "string"},
            "hasStamp": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    return None, None


def import_export_spec(label: str) -> Tuple[Optional[str], Optional[str]]:
    """Import/Export module document specifications"""
    ll = (label or "").lower()
    
    if "registration" in ll or "trade license" in ll:
        rules = """## Import/Export Trade License Rules
- Title: Ethiopian Trade License (ንግድ ፈቃድ)
- Extract: Registration Number, Business Name, Business Category
- Validate: Category must include 'Import' or 'Export'
- Security: Ministry of Trade and Regional Integration (MOTRI) stamp
- Check: License must not be expired"""
        
        entities = """{
            "registrationNumber": {"type": "string", "required": true},
            "businessName": {"type": "string", "required": true},
            "businessCategory": {"type": "string", "required": true},
            "hasImportExport": {"type": "boolean", "required": true},
            "issueDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "hasStamp": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "customs" in ll or "permit" in ll:
        rules = """## Customs Import/Export Permit Rules
- Issuer: Ethiopian Customs Commission
- Extract: Permit Number, TIN, Expiry Date
- Validate: TIN must be 10 digits, permit must be active
- Security: Customs Commission hologram or digital signature
- Goods: Description of goods should be present"""
        
        entities = """{
            "permitNumber": {"type": "string", "required": true},
            "tin": {"type": "string", "required": true, "pattern": "^[0-9]{10}$"},
            "expiryDate": {"type": "date", "required": true},
            "issuingAuthority": {"type": "string", "required": true},
            "goodsDescription": {"type": "string"},
            "totalValue": {"type": "number"},
            "currency": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "invoice" in ll or "proforma" in ll:
        rules = """## Import/Export Invoice Rules
- Type: Commercial or Proforma Invoice for international trade
- Extract: Invoice Number, Date, Total Value, Currency
- Parties: Supplier/Vendor and Buyer details
- Items: Description of goods, quantities, unit prices
- Incoterms: Should be specified (e.g., CIF, FOB)"""
        
        entities = """{
            "invoiceNumber": {"type": "string", "required": true},
            "invoiceDate": {"type": "date", "required": true},
            "totalAmount": {"type": "number", "required": true},
            "currency": {"type": "string", "required": true},
            "vendorName": {"type": "string", "required": true},
            "vendorAddress": {"type": "string"},
            "buyerName": {"type": "string", "required": true},
            "incoterms": {"type": "string"},
            "items": {"type": "array"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "spec" in ll or "item" in ll:
        rules = """## Item Specifications Rules
- Document: Technical specifications or catalog for items being imported/exported
- Extract: Item Name, Model/Part Number, Manufacturer, Technical Parameters
- Validation: Specs must match the items listed in the invoice
- Check: Official manufacturer's documentation preferred"""
        
        entities = """{
            "itemName": {"type": "string", "required": true},
            "modelNumber": {"type": "string"},
            "manufacturer": {"type": "string"},
            "specifications": {"type": "array"},
            "originCountry": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "logo" in ll or "photo" in ll or "image" in ll or "picture" in ll:
        rules = """## Company Logo/Photo Verification Rules
- Document: Official company logo file or site/office photo
- Extract: Company Name (if in logo), Location details (if site photo)
- Validation: Logo must match company branding; Site photo must show physical presence
- Check: Image quality and consistency with company profile"""
        
        entities = """{
            "companyName": {"type": "string"},
            "imageType": {"type": "string", "required": true},
            "description": {"type": "string"},
            "isProfessionalLogo": {"type": "boolean"},
            "hasOfficeBranding": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    return None, None


def professional_spec(label: str) -> Tuple[Optional[str], Optional[str]]:
    """Professional module document specifications"""
    ll = (label or "").lower()
    
    if "national id" in ll:
        rules = """## Professional National ID Rules
- Type: Government ID (National ID, Kebele ID, or Passport)
- Extract: ID Number, Full Name (English), Date of Birth
- Validate: ID must not be expired
- Consistency: Name must match educational documents"""
        
        entities = """{
            "idNumber": {"type": "string", "required": true},
            "fullNameEnglish": {"type": "string", "required": true},
            "dateOfBirth": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "idType": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    # Degree Certificate Check - Requires academic keywords
    if any(x in ll for x in ["degree", "diploma", "graduation", "university", "college", "academic", "educational"]):
        rules = """## Degree Certificate Rules
- Source: Recognized university/college
- Extract: Student Name, Degree Title, Field of Study, Institution, Graduation Date
- Security: Registrar's stamp and official seal
- For foreign degrees: Check for HERQA equivalence mention"""
        
        entities = """{
            "fullName": {"type": "string", "required": true},
            "degreeTitle": {"type": "string", "required": true},
            "fieldOfStudy": {"type": "string", "required": true},
            "institutionName": {"type": "string", "required": true},
            "graduationDate": {"type": "date", "required": true},
            "cgpa": {"type": "number"},
            "isForeign": {"type": "boolean"},
            "hasEquivalence": {"type": "boolean"},
            "registrationNumber": {"type": "string"},
            "hasStamp": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "transcript" in ll:
        rules = """## Academic Transcript Rules
- Format: Official, stamped by institution
- Extract: Student Name, Institution, CGPA, Total Credits
- Validation: CGPA should be ≥ 2.0 for Ethiopian institutions
- Courses: List of courses with grades should be present"""
        
        entities = """{
            "studentName": {"type": "string", "required": true},
            "institutionName": {"type": "string", "required": true},
            "cgpa": {"type": "number", "required": true},
            "totalCredits": {"type": "number", "required": true},
            "graduationStatus": {"type": "string"},
            "hasStamp": {"type": "boolean", "required": true},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "license" in ll or "practicing" in ll:
        rules = """## Professional Practicing License Rules
- Issuer: Regulatory body (ECA, Ministry of Urban Development)
- Extract: License Number, Professional Title, Grade, Issue/Expiry Dates
- Security: Regulatory body's emblem and QR code
- Validate: License must be active (not expired)"""
        
        entities = """{
            "licenseNumber": {"type": "string", "required": true},
            "professionalTitle": {"type": "string", "required": true},
            "professionalGrade": {"type": "string"},
            "issueDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "issuingAuthority": {"type": "string", "required": true},
            "hasQRCode": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "experience" in ll or "employment" in ll:
        rules = """## Professional Experience Letter Rules
- Format: Company letterhead with stamp and signature
- Extract: Employee Name, Position, Employer, Dates
- Validation: Dates logical, total experience calculable
- Contact: Supervisor/HR contact information"""
        
        entities = """{
            "employeeName": {"type": "string", "required": true},
            "position": {"type": "string", "required": true},
            "employerName": {"type": "string", "required": true},
            "startDate": {"type": "date", "required": true},
            "endDate": {"type": "date"},
            "isCurrent": {"type": "boolean"},
            "totalExperienceYears": {"type": "number"},
            "hasStamp": {"type": "boolean", "required": true},
            "hasSignature": {"type": "boolean", "required": true},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    return None, None


def partnership_spec(label: str) -> Tuple[Optional[str], Optional[str]]:
    """Partnership/JV module document specifications"""
    ll = (label or "").lower()
    
    if "partnership" in ll or "jv" in ll or "agreement" in ll:
        rules = """
## Partnership/Joint Venture Agreement Verification Rules

### Document Type: Partnership/JV Agreement
### Category: Partnership Module

### CRITICAL: DOCUMENT TYPE VALIDATION
The document MUST be a Partnership Agreement or Joint Venture Agreement. If it is a Business License or Experience Certificate, it MUST be REJECTED.

### 1. Mandatory Elements to Verify:
- **Agreement Title**: Must clearly state "Partnership Agreement" or "Joint Venture Agreement"
- **Parties Identification**: All partners must be listed with full names, TIN numbers, and addresses
- **Agreement Date**: Must be valid (not future date, within reasonable past)
- **Capital Contribution**: Each partner's contribution amount clearly stated
- **Profit/Loss Sharing Ratio**: Must be specified and sum to 100%
- **Management Structure**: Clearly defined roles and responsibilities
- **Duration**: Start date and end date of partnership
- **Signatures**: All partners must sign with official stamps

### 2. Ethiopian-Specific Requirements:
- **Notarization**: Must be notarized by Ethiopian notary public
- **Language**: Should be in Amharic or English (bilingual preferred)
- **Government Registration**: Must reference registration with Ministry of Trade
- **Tax Compliance**: Partners' TIN numbers must be Ethiopian-issued (10 digits)
- **Business License**: Reference to partners' valid business licenses

### 3. Key Data Extraction:
- Agreement Number (if any)
- Date of Agreement
- Partner Names and TINs
- Each Partner's Share Percentage
- Total Capital Amount
- Duration (Start Date, End Date)
- Notary Details (Name, Date, Stamp)

### 4. Validation Rules:
- [ ] Profit Sharing Sum = 100% (if specified)
- [ ] Capital Contribution Sum = Total Capital
- [ ] All partners have valid TINs (10-digit)
- [ ] Agreement date <= current date (2026-03-24)
- [ ] Notarized with official stamp
- [ ] All signatures present
- [ ] Duration is logical (End Date > Start Date)
- [ ] If JV, foreign partner license mentioned

### 5. Authenticity Indicators:
- **Genuine**: Consistent fonts, clear text, overlapping stamps/signatures, notary seal
- **Suspicious**: Inconsistent fonts, missing stamps, digital manipulation marks, missing notary

### 6. Common Forgery Patterns:
- Fabricated notary stamps
- Missing partner signatures
- Inconsistent capital figures
- Mismatched dates
- Generic templates without specific details

### 7. Business Logic Checks:
- For JV: Foreign partner must have valid foreign business license
- For JV: Profit sharing must reflect capital contribution (reasonable)
- Partnership duration should not exceed license validity
- Total capital must meet minimum requirement (depends on project)
"""
        
        entities = """{
            "agreementNumber": {"type": "string", "required": false},
            "agreementDate": {"type": "date", "required": true},
            "partners": {
                "type": "array",
                "required": true,
                "minItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "required": true},
                        "tin": {"type": "string", "required": true, "pattern": "^[0-9]{10}$"},
                        "address": {"type": "string"},
                        "sharePercentage": {"type": "number", "required": true, "min": 0, "max": 100},
                        "capitalContribution": {"type": "number", "required": true, "min": 0},
                        "isForeign": {"type": "boolean", "required": true}
                    }
                }
            },
            "totalCapital": {"type": "number", "required": true},
            "profitSharingSum": {"type": "number", "required": true, "min": 100, "max": 100},
            "managementStructure": {"type": "string"},
            "startDate": {"type": "date", "required": true},
            "endDate": {"type": "date", "required": true},
            "durationYears": {"type": "number"},
            "isNotarized": {"type": "boolean", "required": true},
            "notaryName": {"type": "string"},
            "notaryDate": {"type": "date"},
            "notarySealNumber": {"type": "string"},
            "hasAllSignatures": {"type": "boolean", "required": true},
            "hasOfficialStamps": {"type": "boolean", "required": true},
            "confidence": {"type": "number", "min": 0, "max": 1}
        }"""
        return rules, entities
        
    if "license" in ll and "partner" in ll:
        rules = """
## Partner Business License Verification Rules

### Document Type: Partner Business/Trade License
### Category: Partnership Module

### CRITICAL: DOCUMENT TYPE VALIDATION
The document MUST be a Business/Trade License. If it is an Experience Certificate, Project Contract, or any other document type, it MUST be REJECTED.

### 1. Mandatory Elements:
- **License Number**: Unique registration number
- **Business Name**: Full registered name
- **Owner/Partner Name**: Name matching agreement
- **TIN Number**: 10-digit Ethiopian TIN
- **License Type**: Individual, PLC, Share Company, etc.
- **Issue Date**: Date license was issued
- **Expiry Date**: License expiration date
- **Business Category**: Type of business activity
- **Issuing Authority**: Ministry of Trade or Regional Trade Bureau

### 2. Ethiopian License Types:
- **Category 1-5**: For construction contractors
- **Import License**: For import/export activities
- **General Trade License**: For other businesses
- **Foreign Company License**: For foreign partners

### 3. Validation Rules:
- [ ] License must be ACTIVE (not expired)
- [ ] TIN must be valid (10 digits)
- [ ] Business name matches partnership agreement
- [ ] License type permits construction-related activities
- [ ] License category matches claimed grade
- [ ] Issuing authority is legitimate

### 4. Security Features:
- **Official Stamp**: Usually blue or red, embossed
- **QR Code**: Recent licenses have QR code for verification
- **Watermark**: Official Ministry watermark
- **Security Paper**: Special paper with security features
- **Signature**: Authorized official signature

### 5. Fraud Detection:
- **Check for**:
  - Tampered expiry dates
  - Fake stamps
  - Altered business names
  - Invalid license numbers
  - Mismatched TIN patterns

### 6. Business Logic:
- License expiry date must be >= partnership end date
- License category must match project requirements
- Foreign partner must have valid foreign business license + Ethiopian investment license
"""
        
        entities = """{
            "licenseNumber": {"type": "string", "required": true},
            "businessName": {"type": "string", "required": true},
            "ownerName": {"type": "string", "required": true},
            "tin": {"type": "string", "required": true, "pattern": "^[0-9]{10}$"},
            "licenseType": {"type": "string", "required": true},
            "licenseCategory": {"type": "string"},
            "issueDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "isExpired": {"type": "boolean", "required": true},
            "issuingAuthority": {"type": "string", "required": true},
            "businessCategory": {"type": "string", "required": true},
            "hasQRCode": {"type": "boolean"},
            "hasOfficialStamp": {"type": "boolean", "required": true},
            "isForeign": {"type": "boolean", "required": true},
            "foreignLicenseRef": {"type": "string"},
            "investmentLicense": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "contract" in ll or "project" in ll:
        rules = """
## Project Contract/Award Letter Verification Rules

### Document Type: Construction Project Contract/Award Letter (Experience)
### Category: Partnership Module

### CRITICAL: DOCUMENT TYPE VALIDATION
The document MUST be a Project Contract, Award Letter, or Experience Certificate. If it is a Business License or any other document type, it MUST be REJECTED.

### 1. Mandatory Elements:
- **Contract Number**: Unique reference number
- **Client/Owner**: Project owner/employer
- **Contractor**: Partner/JV company name
- **Project Name**: Full project title
- **Project Value**: Total contract amount (in ETB)
- **Contract Type**: Design-Build, Traditional, etc.
- **Start Date**: Project commencement
- **End Date**: Project completion
- **Scope of Work**: Detailed description
- **Signatures**: Both parties must sign

### 2. Ethiopian Public Procurement Compliance:
- **PPDA Reference**: For public projects
- **Tender Number**: Original tender reference
- **Bid Bond Reference**: For competitive bids
- **Performance Bond Requirement**: Mentioned in contract
- **Government Agency**: Must be authorized body

### 3. Validation Rules:
- [ ] Contract value matches partner capacity
- [ ] Project duration is realistic
- [ ] Contract type matches license category
- [ ] All signatures present and authorized
- [ ] For public projects: PPDA compliance verified
- [ ] For JV: Both partners sign or JV lead signs

### 4. Security Features:
- **Company Letterhead**: Official stationery
- **Corporate Seal**: Company stamp
- **Authorized Signatures**: Named authorized signatories
- **Witness Signatures**: Optional but recommended
- **Date Stamp**: Official date stamp

### 5. Business Logic:
- Contract value should be within partner's financial capacity
- Project duration should be within license validity
- For JV: Contract must reference JV agreement
- Progress payment schedule should be logical

### 6. Fraud Detection:
- **Check for**:
  - Fabricated government references
  - Altered contract values
  - Fake signatures
  - Invalid project names
  - Mismatched dates
"""
        
        entities = """{
            "contractNumber": {"type": "string", "required": true},
            "clientName": {"type": "string", "required": true},
            "clientTin": {"type": "string"},
            "contractorName": {"type": "string", "required": true},
            "contractorTin": {"type": "string", "required": true},
            "projectName": {"type": "string", "required": true},
            "projectLocation": {"type": "string"},
            "contractValue": {"type": "number", "required": true, "min": 0},
            "currency": {"type": "string", "required": true},
            "contractType": {"type": "string", "required": true},
            "scopeOfWork": {"type": "string", "required": true},
            "startDate": {"type": "date", "required": true},
            "endDate": {"type": "date", "required": true},
            "durationMonths": {"type": "number"},
            "isPublicProject": {"type": "boolean", "required": true},
            "ppdaReference": {"type": "string"},
            "tenderNumber": {"type": "string"},
            "hasClientSignature": {"type": "boolean", "required": true},
            "hasContractorSignature": {"type": "boolean", "required": true},
            "hasOfficialStamp": {"type": "boolean", "required": true},
            "performanceBondRequired": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "guarantee" in ll or "bond" in ll:
        rules = """
## Financial Guarantee/Bond Verification Rules

### Document Type: Financial Guarantee/Bid Bond/Performance Bond
### Category: Partnership Module

### 1. Mandatory Elements:
- **Guarantee Number**: Unique reference
- **Issuing Bank**: Ethiopian bank name (CBE, Dashen, Awash, etc.)
- **Beneficiary**: Client/Owner name
- **Applicant**: Contractor/JV name
- **Guarantee Amount**: In ETB or USD
- **Issue Date**: Date of issuance
- **Expiry Date**: Date guarantee expires
- **Guarantee Type**: Bid Bond, Performance Bond, Advance Payment

### 2. Ethiopian Banking Requirements:
- **Bank License**: Must be licensed by National Bank of Ethiopia
- **Authorized Signatory**: Bank manager or authorized officer
- **Bank Seal**: Official bank stamp
- **Letterhead**: Official bank letterhead
- **SWIFT Code**: For international guarantees

### 3. Validation Rules:
- [ ] Bank is licensed in Ethiopia
- [ ] Amount meets or exceeds requirement
- [ ] Not expired (expiry date >= current date)
- [ ] Beneficiary name matches contract
- [ ] Applicant name matches contractor
- [ ] Bank seal and signature present
- [ ] For performance bonds: Value = contract percentage (usually 10%)

### 4. Security Features:
- **Bank Seal**: Embossed or printed official seal
- **Authorized Signature**: Named bank official signature
- **Security Paper**: Bank-issued security paper
- **Hologram**: Some banks use holographic stickers
- **Serial Number**: Unique tracking number

### 5. Fraud Detection:
- **Check for**:
  - Fake bank letterheads
  - Invalid bank names
  - Forged signatures
  - Altered amounts
  - Expired guarantees with altered dates
  - Non-existent bank branches

### 6. Business Logic:
- Bid bond: Usually 1-2% of contract value
- Performance bond: Usually 5-10% of contract value
- Advance payment bond: Equal to advance payment
- All guarantees must be unconditional and irrevocable
"""
        
        entities = """{
            "guaranteeNumber": {"type": "string", "required": true},
            "issuingBank": {"type": "string", "required": true},
            "bankBranch": {"type": "string"},
            "beneficiary": {"type": "string", "required": true},
            "applicant": {"type": "string", "required": true},
            "applicantTin": {"type": "string"},
            "guaranteeType": {"type": "string", "required": true},
            "guaranteeAmount": {"type": "number", "required": true, "min": 0},
            "currency": {"type": "string", "required": true},
            "issueDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "daysValid": {"type": "number"},
            "isExpired": {"type": "boolean", "required": true},
            "isUnconditional": {"type": "boolean", "required": true},
            "isIrrevocable": {"type": "boolean", "required": true},
            "hasBankSeal": {"type": "boolean", "required": true},
            "hasAuthorizedSignature": {"type": "boolean", "required": true},
            "authorizedSignatory": {"type": "string"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    return None, None


def vehicle_spec(label: str) -> Tuple[Optional[str], Optional[str]]:
    """Vehicle/Fleet module document specifications"""
    ll = (label or "").lower()
    
    if "registration" in ll or "title" in ll:
        rules = """
## Vehicle Registration Certificate Verification Rules

### Document Type: Vehicle Registration Certificate (VRC)
### Category: Vehicle/Fleet Module

### 1. Mandatory Elements:
- **Plate Number**: Format: [Region Code][Space][Number]
- **Region Codes**: AA (Addis Ababa), OR (Oromia), AM (Amhara), SN (SNNP), etc.
- **Registration Number**: Unique registration ID
- **Chassis Number**: 17-character VIN (Vehicle Identification Number)
- **Engine Number**: Unique engine serial
- **Make**: Manufacturer (Toyota, Isuzu, Mitsubishi, etc.)
- **Model**: Vehicle model
- **Year**: Manufacturing year (YYYY)
- **Owner Name**: Registered owner
- **Owner TIN**: If company-owned

### 2. Ethiopian Format Validation:
- **Plate Pattern**:
  - Personal: "AA 1234" (Addis), "OR 1234" (Oromia)
  - Government: "GV 1234"
  - Diplomatic: "CD 1234"
  - Rental: "RE 1234"
- **Chassis Number**: 17 characters, no I, O, Q
- **Year**: Must be between 1900 and current year

### 3. Validation Rules:
- [ ] Plate number format is correct
- [ ] Region code is valid
- [ ] Chassis number is 17 characters
- [ ] Engine number is present
- [ ] Year is valid (>= 1900, <= current year)
- [ ] Owner name matches applicant
- [ ] Registration certificate is current
- [ ] No outstanding fines (if integrated system)

### 4. Security Features:
- **Security Paper**: Watermarked document paper
- **Holographic Stripe**: Official MoT hologram
- **Microprint**: Tiny text visible under magnification
- **QR Code**: Contains encrypted vehicle data
- **Barcode**: Machine-readable registration data
- **Official Stamp**: Ministry of Transport seal

### 5. Fraud Detection:
- **Check for**:
  - Fake plate numbers
  - Stolen vehicle (cross-check with database)
  - Cloned chassis numbers
  - Altered registration dates
  - Tampered ownership details
  - Fake security features

### 6. Business Logic:
- Registration must be in contractor's name
- For leased vehicles: Must show lease agreement
- Commercial vehicles: Additional transport license required
- Heavy vehicles: Axle load certification required
"""
        
        entities = """{
            "plateNumber": {"type": "string", "required": true},
            "regionCode": {"type": "string", "required": true},
            "registrationNumber": {"type": "string", "required": true},
            "chassisNumber": {"type": "string", "required": true, "pattern": "^[A-HJ-NPR-Z0-9]{17}$"},
            "engineNumber": {"type": "string", "required": true},
            "make": {"type": "string", "required": true},
            "model": {"type": "string", "required": true},
            "year": {"type": "integer", "required": true, "min": 1900, "max": 2026},
            "vehicleType": {"type": "string", "required": true},
            "color": {"type": "string"},
            "grossWeight": {"type": "number"},
            "ownerName": {"type": "string", "required": true},
            "ownerTin": {"type": "string", "pattern": "^[0-9]{10}$"},
            "ownerType": {"type": "string", "required": true},
            "registrationDate": {"type": "date", "required": true},
            "firstRegistrationDate": {"type": "date"},
            "isCommercial": {"type": "boolean", "required": true},
            "hasQRCode": {"type": "boolean"},
            "hasOfficialStamp": {"type": "boolean", "required": true},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "insurance" in ll:
        rules = """
## Vehicle Insurance Certificate Verification Rules

### Document Type: Motor Vehicle Insurance Certificate
### Category: Vehicle/Fleet Module

### 1. Mandatory Elements:
- **Policy Number**: Unique insurance policy number
- **Insurer**: Insurance company name
- **Insured**: Policyholder name (contractor)
- **Vehicle Plate**: Matches registration certificate
- **Coverage Type**: Third-party, Comprehensive
- **Coverage Amount**: Maximum liability
- **Start Date**: Policy effective date
- **Expiry Date**: Policy expiration date

### 2. Ethiopian Insurance Companies:
- **Major Insurers**:
  - Ethiopian Insurance Corporation (EIC)
  - Awash Insurance
  - Nyala Insurance
  - Global Insurance
  - Nile Insurance
  - United Insurance

### 3. Validation Rules:
- [ ] Policy is ACTIVE (not expired)
- [ ] Vehicle plate matches registration
- [ ] Insured name matches owner
- [ ] Coverage type meets minimum (at least third-party)
- [ ] Policy number format is valid
- [ ] Insurer is licensed in Ethiopia
- [ ] Start date <= current date
- [ ] Expiry date >= current date

### 4. Minimum Coverage Requirements:
- **Third-Party**: Minimum 500,000 ETB
- **Comprehensive**: Full coverage
- **Commercial Vehicles**: Higher limits required
- **Heavy Equipment**: Special coverage required

### 5. Security Features:
- **Insurer Stamp**: Official company stamp
- **Authorized Signature**: Insurance agent signature
- **Policy Number Format**: Company-specific pattern
- **Security Paper**: Usually colored paper with watermark
- **QR Code**: Some insurers include QR code

### 6. Fraud Detection:
- **Check for**:
  - Fake policy numbers
  - Expired policies with altered dates
  - Forged insurer stamps
  - Inconsistent vehicle details
  - Invalid coverage amounts
  - Non-existent insurance companies

### 7. Business Logic:
- All vehicles in fleet must have valid insurance
- Insurance must cover intended use (construction)
- Renewal date should be tracked
- Gap in coverage not allowed
"""
        
        entities = """{
            "policyNumber": {"type": "string", "required": true},
            "insurerName": {"type": "string", "required": true},
            "insuredName": {"type": "string", "required": true},
            "insuredTin": {"type": "string", "pattern": "^[0-9]{10}$"},
            "vehiclePlate": {"type": "string", "required": true},
            "coverageType": {"type": "string", "required": true},
            "coverageAmount": {"type": "number", "required": true},
            "currency": {"type": "string", "required": true},
            "startDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "daysRemaining": {"type": "number"},
            "isActive": {"type": "boolean", "required": true},
            "premiumAmount": {"type": "number"},
            "deductibleAmount": {"type": "number"},
            "hasInsurerStamp": {"type": "boolean", "required": true},
            "hasAuthorizedSignature": {"type": "boolean", "required": true},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    if "inspection" in ll or "safety" in ll:
        rules = """
## Vehicle Safety Inspection Certificate Verification Rules

### Document Type: Vehicle Safety Inspection Certificate
### Category: Vehicle/Fleet Module

### 1. Mandatory Elements:
- **Certificate Number**: Unique inspection certificate number
- **Inspection Center**: Authorized center name
- **Vehicle Plate**: Matches registration
- **Inspection Date**: Date of inspection
- **Expiry Date**: Certificate expiration (usually 6 months)
- **Result**: PASS or FAIL
- **Inspector Name**: Authorized inspector

### 2. Ethiopian Inspection Centers:
- **Enqualal (Main)**: Federal inspection center
- **Regional Garages**: Authorized regional centers
- **Private Centers**: Licensed private inspection centers

### 3. Inspection Checks:
- **Brake Efficiency**: >= 50%
- **Emissions**: Within acceptable limits
- **Lights**: All functional
- **Tires**: Tread depth >= 1.6mm
- **Suspension**: No excessive play
- **Steering**: Proper operation
- **Body Condition**: No major corrosion

### 4. Validation Rules:
- [ ] Certificate is VALID (not expired)
- [ ] Inspection date <= current date
- [ ] Expiry date >= current date
- [ ] Result = PASS
- [ ] Vehicle plate matches registration
- [ ] Inspection center is authorized
- [ ] Certificate number format valid

### 5. Heavy Vehicles (Trucks, Loaders):
- **Additional Checks**:
  - Axle load limits
  - Cargo securing
  - Air brake system
  - Engine compression
  - Hydraulic systems (for loaders)

### 6. Security Features:
- **Inspection Center Stamp**: Official stamp
- **Inspector Signature**: Licensed inspector
- **Hologram**: Security hologram on certificate
- **Barcode**: Tracking barcode
- **Security Paper**: Special tamper-proof paper

### 7. Fraud Detection:
- **Check for**:
  - Expired certificates with altered dates
  - Fake inspection centers
  - Forged inspector signatures
  - Pass results for clearly failed vehicles
  - Duplicate certificate numbers
  - Missing security features

### 8. Business Logic:
- Inspection valid for 6 months (passenger vehicles)
- Inspection valid for 3 months (commercial vehicles)
- Heavy equipment requires specialized inspection
- Renewal required before expiration
"""
        
        entities = """{
            "certificateNumber": {"type": "string", "required": true},
            "inspectionCenter": {"type": "string", "required": true},
            "centerType": {"type": "string", "required": true},
            "vehiclePlate": {"type": "string", "required": true},
            "inspectionDate": {"type": "date", "required": true},
            "expiryDate": {"type": "date", "required": true},
            "result": {"type": "string", "required": true},
            "inspectorName": {"type": "string", "required": true},
            "inspectorLicense": {"type": "string"},
            "brakeEfficiency": {"type": "number"},
            "emissionResult": {"type": "string"},
            "axleLoadFront": {"type": "number"},
            "axleLoadRear": {"type": "number"},
            "defectsFound": {"type": "array"},
            "recommendations": {"type": "array"},
            "hasInspectionStamp": {"type": "boolean", "required": true},
            "hasInspectorSignature": {"type": "boolean", "required": true},
            "daysValid": {"type": "number"},
            "isValid": {"type": "boolean", "required": true},
            "confidence": {"type": "number"}
        }"""
        return rules, entities

    if "ownership" in ll:
        rules = """
## Proof of Ownership Verification Rules

### Document Type: Proof of Vehicle Ownership
### Category: Vehicle/Fleet Module

### 1. Document Types Accepted:
- **Title Deed**: Original vehicle title document
- **Bill of Sale**: Notarized sale agreement
- **Transfer Certificate**: Official transfer document
- **Lease Agreement**: For leased vehicles
- **Import Documents**: For imported vehicles

### 2. Mandatory Elements:
- **Previous Owner**: Seller name and details
- **Current Owner**: Buyer name and details
- **Vehicle Details**: Make, Model, Chassis, Engine
- **Sale Price**: Transaction amount
- **Sale Date**: Date of transfer
- **Notarization**: For private sales
- **Stamp Duty**: Tax payment proof

### 3. Ethiopian Requirements:
- **Transfer Fee**: Paid to Transport Authority
- **Stamp Duty**: 3-5% of vehicle value
- **Notarization**: Required for private sales
- **Witness Signatures**: Two witnesses required
- **TIN Verification**: Both parties' TINs verified

### 4. Validation Rules:
- [ ] Current owner matches applicant
- [ ] Vehicle details match registration
- [ ] Sale date is logical
- [ ] Stamp duty paid
- [ ] Notarized (if private sale)
- [ ] No disputes or liens
- [ ] Transfer completed with Transport Authority

### 5. Fraud Detection:
- **Check for**:
  - Forged signatures
  - Altered chassis numbers
  - Stolen vehicles
  - Fake bills of sale
  - Inconsistent ownership chain
  - Missing notary stamps

### 6. Business Logic:
- Ownership must be traceable
- For company vehicles: Board resolution required
- For leased vehicles: Lease agreement and lessor consent
- For imported vehicles: Customs clearance required
"""
        
        entities = """{
            "documentType": {"type": "string", "required": true},
            "previousOwnerName": {"type": "string", "required": true},
            "previousOwnerTin": {"type": "string"},
            "currentOwnerName": {"type": "string", "required": true},
            "currentOwnerTin": {"type": "string", "required": true},
            "vehicleMake": {"type": "string", "required": true},
            "vehicleModel": {"type": "string", "required": true},
            "chassisNumber": {"type": "string", "required": true},
            "engineNumber": {"type": "string"},
            "salePrice": {"type": "number", "required": true},
            "currency": {"type": "string"},
            "saleDate": {"type": "date", "required": true},
            "isNotarized": {"type": "boolean", "required": true},
            "notaryName": {"type": "string"},
            "stampDutyPaid": {"type": "boolean", "required": true},
            "transferFeePaid": {"type": "boolean", "required": true},
            "hasWitnessSignatures": {"type": "boolean"},
            "hasTransferDocument": {"type": "boolean"},
            "confidence": {"type": "number"}
        }"""
        return rules, entities
        
    return None, None


# ============================================================================
# MAIN VERIFICATION ENGINE
# ============================================================================

def ai_score_and_details_structured(extracted_text: str, label: str, category_name: str, category_rules: str, extracted_schema: str, image_data: Optional[bytes] = None, file_ext: str = "") -> Tuple[str, str, Optional[str]]:
    """Send extracted text (and optional image) to AI provider for analysis"""
    from systemsettings.models import SystemSettings
    settings_obj = SystemSettings.get_solo()
    
    provider = getattr(settings_obj, 'preferred_ai_provider', 'deepseek')
    
    # If no text was extracted but we have image data, we can still proceed with vision-capable models
    if not extracted_text and not image_data:
        return provider, f"Error: No text extracted from document for {provider.capitalize()} AI analysis.", "No text extracted"

    prompt = f"""Analyze the following document and verify if it matches the expected type '{label}' in the '{category_name}' category.
    
    CRITICAL INSTRUCTION:
    If the document is NOT a '{label}' (e.g., if an experience certificate is uploaded instead of a business license), you MUST set 'finalRecommendation' to 'REJECTED' and explain the mismatch in the 'summary'.
    
    RULES:
    {category_rules}
    
    EXTRACTED TEXT (from OCR):
    ---
    {extracted_text or "(No text extracted by OCR - please use the provided image for analysis)"}
    ---
    
    EXPECTED JSON OUTPUT FORMAT:
    {{
      "summary": "A brief summary of the document and its verification result. Must explicitly state if the document type matches '{label}'.",
      "finalRecommendation": "APPROVED" (if matches type and rules) or "REJECTED" (if type mismatch or fails rules) or "INCONCLUSIVE",
      "confidenceScore": 0.0 to 1.0 (float),
      "extractedEntities": {{ "fieldName": "extractedValue", ... }},
      "domainValidation": {{
        "checks": [
          {{ "rule": "Document Type Matching", "message": "Verify if the document is a '{label}'" }},
          {{ "rule": "Rule name", "message": "Result of the check" }}
        ]
      }},
      "authenticityIndicators": {{
        "suspiciousPatterns": ["Any detected fake or edited patterns"],
        "overallAuthenticityScore": 0.0 to 1.0 (float)
      }},
      "qualityAssessment": {{
        "issues": ["Any OCR quality issues like garbled text"]
      }}
    }}
    
    IMPORTANT: 'extractedEntities' should be a FLAT object with field names as keys and extracted strings/values as values. Do NOT include nested type definitions in the output.
    
    SCHEMA for extractedEntities:
    {extracted_schema}
    
    Ensure the output is ONLY the JSON object. Do not include markdown code blocks.
    """
    
    if provider == "gemini":
        # ... (Gemini logic remains similar, but can be updated for vision if needed)
        try:
            from google import genai as genai_new
            from google.genai import types as genai_types
        except ImportError:
            return "gemini", "AI error: google-genai package not installed", "Package missing"
            
        api_key = settings_obj.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return "gemini", "AI error: GEMINI_API_KEY not configured", "No API Key"
            
        try:
            client = genai_new.Client(api_key=api_key)
            model = getattr(settings_obj, 'gemini_model', 'gemini-2.0-flash')
            
            # For Gemini, we can send text + image
            contents = [prompt]
            if image_data and file_ext.lower() in ["jpg", "jpeg", "png", "webp"]:
                contents.append(genai_types.Part.from_bytes(data=image_data, mime_type=f"image/{file_ext.lower()}"))
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            txt = response.text
            return "gemini", txt, None
        except Exception as e:
            err_str = str(e)
            return "gemini", f"Gemini request failed: {err_str}", err_str
            
    elif settings_obj.preferred_ai_provider == "openrouter":
        api_key = settings_obj.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            return "openrouter", "AI error: OPENROUTER_API_KEY not configured", "No API Key"
            
        model = getattr(settings_obj, 'openrouter_model', 'google/gemini-2.0-flash-001')
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-OpenRouter-Title": "CLMS Verification",
        }
        
        # Build multi-modal message if image is present
        user_content = [{"type": "text", "text": prompt}]
        
        if image_data and file_ext.lower() in ["jpg", "jpeg", "png", "webp"]:
            b64_img = base64.b64encode(image_data).decode('utf-8')
            mime = f"image/{'jpeg' if file_ext.lower() == 'jpg' else file_ext.lower()}"
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{b64_img}"
                }
            })
            
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            "response_format": { "type": "json_object" },
            "temperature": 0.1
        }
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=getattr(settings_obj, 'openrouter_timeout', 60)
            )
            response.raise_for_status()
            res_json = response.json()
            txt = res_json['choices'][0]['message']['content']
            return "openrouter", txt, None
        except Exception as e:
            err_str = str(e)
            return "openrouter", f"OpenRouter request failed: {err_str}", err_str
            
    else: # Default to DeepSeek
        api_key = settings_obj.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            return "deepseek", "AI error: DEEPSEEK_API_KEY not configured in System Settings or Environment", "No API Key"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": getattr(settings_obj, 'deepseek_model', "deepseek-chat"),
            "messages": [
                {"role": "system", "content": "You are a professional document auditor specializing in Ethiopian government documents."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            timeout = getattr(settings_obj, 'deepseek_timeout', 60)
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                txt = data["choices"][0]["message"]["content"]
                return "deepseek", txt, None
            else:
                error_msg = f"DeepSeek API error: {response.status_code} {response.text}"
                if response.status_code == 402 or "insufficient_balance" in response.text.lower():
                    error_msg = "DeepSeek Error: Insufficient Balance. Please add funds to your account."
                return "deepseek", error_msg, response.text
        except Exception as e:
            err_str = str(e)
            if "timeout" in err_str.lower():
                return "deepseek", f"DeepSeek Error: Request timed out after {timeout}s. Try again later.", err_str
            return "deepseek", f"DeepSeek request failed: {err_str}", err_str


def perform_verification(docs, category):
    from systemsettings.models import SystemSettings
    print(f"DEBUG: perform_verification started for category='{category}' with {len(docs)} documents.")
    try:
        settings_obj = SystemSettings.get_solo()
        print(f"DEBUG: SystemSettings solo object retrieved: {settings_obj}")
    except Exception as se:
        print(f"DEBUG: SystemSettings retrieval failed: {str(se)}")
        settings_obj = None
    
    results = []
    
    for d in docs:
        try:
            doc_id = str(getattr(d, 'id', 'unknown'))
            print(f"DEBUG: Processing document ID='{doc_id}' of type {type(d)}")
            
            f = getattr(d, "file", None)
            if not f or not getattr(f, "name", None):
                print(f"DEBUG: Document {doc_id} has no file or file name.")
                results.append({"document_id": doc_id, "status": "missing"})
                continue
            
            # Reset status
            print(f"DEBUG: Resetting document status for {doc_id}...")
            d.verification_status = "pending"
            d.verification_score = None
            d.verification_details = ""
            d.verified_at = timezone.now()
            try:
                d.save()
                print(f"DEBUG: Document {doc_id} status reset successfully.")
            except Exception as ds1:
                print(f"CRITICAL: Failed to save document {doc_id} during status reset: {str(ds1)}")
                raise ds1

            ext = os.path.splitext(f.name)[1].lower().strip(".")
            print(f"DEBUG: Document {doc_id} extension: '{ext}'")
            
            # Read file content
            content = None
            try:
                print(f"DEBUG: Reading file content for {doc_id}...")
                with f.storage.open(f.name, "rb") as fh:
                    content = fh.read()
                print(f"DEBUG: File content read successfully ({len(content) if content else 0} bytes).")
            except Exception as fe:
                print(f"CRITICAL: File read error for {doc_id}: {str(fe)}")
                results.append({"document_id": doc_id, "status": "error", "detail": f"File read error: {str(fe)}"})
                continue

            label = infer_document_name(getattr(d, "name", "") or getattr(d, "document_type", "") or f.name)
            print(f"DEBUG: Inferred document label: '{label}'")
            
            # 1. OCR Step
            lang = getattr(settings_obj, 'ocr_language', 'amh+eng')
            print(f"DEBUG: Starting OCR for {doc_id} (lang='{lang}')...")
            extracted_text, ocr_notes, processed_image = extract_text_from_document(content, ext, lang)
            print(f"DEBUG: OCR complete for {doc_id}. Extracted {len(extracted_text) if extracted_text else 0} chars. Notes: {ocr_notes}")
            
            # 2. AI Verification Step
            cat_rules = ""
            extracted_schema = "{}"
            
            # Smart spec selection: Check document association first
            is_vehicle_doc = getattr(d, 'vehicle_id', None) is not None
            is_partnership_doc = getattr(d, 'partnership_id', None) is not None
            
            print(f"DEBUG: Determining specs for doc_id={doc_id}, category='{category}', label='{label}'...")
            
            # First priority: Force specific domain specs if the document is linked to vehicle/partnership
            if is_vehicle_doc:
                print(f"DEBUG: Document {doc_id} is associated with a vehicle. Forcing vehicle_spec.")
                cat_rules, extracted_schema = vehicle_spec(label)
                if cat_rules:
                    # Update category name to ensure AI context is correct
                    category = "Vehicle/Fleet"
            
            if not cat_rules and is_partnership_doc:
                print(f"DEBUG: Document {doc_id} is associated with a partnership. Forcing partnership_spec.")
                cat_rules, extracted_schema = partnership_spec(label)
                if cat_rules:
                    category = "Partnership/JV"
            
            # Second priority: Use keywords in the label to find the right spec, regardless of the 'category' passed in
            if not cat_rules:
                ll = (label or "").lower()
                if any(x in ll for x in ["vehicle", "car", "truck", "insurance", "inspection", "safety", "registration", "chassis", "plate", "engine"]):
                    print(f"DEBUG: Vehicle keywords found in label '{label}'. Trying vehicle_spec.")
                    cat_rules, extracted_schema = vehicle_spec(label)
                    if cat_rules:
                        category = "Vehicle/Fleet"
                
                if not cat_rules and any(x in ll for x in ["partnership", "jv", "agreement", "partner"]):
                    print(f"DEBUG: Partnership keywords found in label '{label}'. Trying partnership_spec.")
                    cat_rules, extracted_schema = partnership_spec(label)
                    if cat_rules:
                        category = "Partnership/JV"

            # Third priority: Fall back to category-based selection if still no rules
            if not cat_rules:
                if "Contractor" in (category or ""):
                    cat_rules, extracted_schema = contractor_spec(label)
                elif "Import/Export" in (category or ""):
                    cat_rules, extracted_schema = import_export_spec(label)
                elif "Professional" in (category or ""):
                    cat_rules, extracted_schema = professional_spec(label)
                elif "Partnership" in (category or ""):
                    cat_rules, extracted_schema = partnership_spec(label)
                elif "Vehicle" in (category or ""):
                    cat_rules, extracted_schema = vehicle_spec(label)
            
            if not cat_rules:
                print(f"DEBUG: No specific rules found for category '{category}' and label '{label}', using default.")
                cat_rules = "- Validate core identifiers and official seals"
                extracted_schema = '{"identifier":""}'
            
            # For AI vision analysis, if we processed a PDF to an image, the format is now PNG
            vision_ext = "png" if (ext == "pdf" and processed_image) else ext
            
            print(f"DEBUG: Calling AI provider for {doc_id}...")
            provider_used, g_txt, last_ai_err = ai_score_and_details_structured(
                extracted_text, label, category, cat_rules, extracted_schema, processed_image, vision_ext
            )
            print(f"DEBUG: AI provider returned. Success: {bool(g_txt)}, Error: {last_ai_err}")

            detail_parts = []
            if ocr_notes:
                detail_parts.append("System: " + "; ".join(ocr_notes))
            
            if g_txt:
                prefix = f"{provider_used.capitalize()}: "
                # Always add prefix so frontend can identify AI response
                detail_parts.append(prefix + g_txt.strip())

            # 3. Process Result
            status_label = "inconclusive"
            final_score = 0.5
            
            if g_txt and "error" not in g_txt.lower():
                try:
                    print(f"DEBUG: Parsing AI JSON response for {doc_id}...")
                    # Clean potential markdown
                    cleaned_json = g_txt.replace("```json", "").replace("```", "").strip()
                    json_match = re.search(r'\{[\s\S]*\}', cleaned_json)
                    if json_match:
                        cleaned_json = json_match.group(0)
                    
                    ai_data = json.loads(cleaned_json)
                    recommendation = str(ai_data.get("finalRecommendation", "")).upper()
                    confidence = float(ai_data.get("confidenceScore", 0))
                    authenticity = float(ai_data.get("authenticityIndicators", {}).get("overallAuthenticityScore", 1.0))

                    print(f"DEBUG: AI parsed recommendation='{recommendation}', confidence={confidence}, authenticity={authenticity}")
                    if "APPROVED" in recommendation and confidence >= 0.7 and authenticity >= 0.7:
                        status_label = "verified_true"
                        final_score = max(final_score, confidence)
                    elif "REJECTED" in recommendation or (confidence >= 0.7 and authenticity < 0.5):
                        status_label = "verified_fake"
                        final_score = min(final_score, 0.2)
                    
                    g_txt = cleaned_json
                except Exception as parse_err:
                    print(f"DEBUG: AI JSON parsing failed for {doc_id}: {str(parse_err)}")
                    if "APPROVED" in g_txt.upper():
                        status_label = "verified_true"
                        final_score = 0.85
                    elif "REJECTED" in g_txt.upper():
                        status_label = "verified_fake"
                        final_score = 0.2
            
            # If AI failed due to quota/network
            if last_ai_err:
                print(f"DEBUG: Handling AI error for {doc_id}: {last_ai_err}")
                err_str = str(last_ai_err).upper()
                # Set to pending to allow retry once balance/quota is restored
                if any(x in err_str for x in ["429", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "TIMEOUT", "CONNECTION", "INSUFFICIENT BALANCE", "BALANCE"]):
                    status_label = "pending"
                    if "BALANCE" in err_str:
                        detail_parts.append("DeepSeek Alert: API Account balance is exhausted. Please add funds to your DeepSeek dashboard to resume verification.")
                else:
                    status_label = "error"
            
            print(f"DEBUG: Final status for {doc_id}: {status_label}")
            d.verification_status = status_label
            d.verification_score = final_score
            d.verification_details = "\n".join(detail_parts)
            d.verified_at = timezone.now()
            try:
                d.save()
                print(f"DEBUG: Document {doc_id} saved successfully with final results.")
            except Exception as ds2:
                print(f"CRITICAL: Failed to save document {doc_id} during final update: {str(ds2)}")
                raise ds2
                
            results.append({"document_id": doc_id, "status": status_label, "score": final_score})
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"CRITICAL: Exception in document loop for {getattr(d, 'id', 'unknown')}: {str(e)}\n{tb}")
            results.append({"document_id": str(getattr(d, "id", "unknown")), "status": "error", "detail": str(e)})

    summary = {"verified_true": 0, "verified_fake": 0, "inconclusive": 0, "pending": 0, "missing": 0, "error": 0}
    for r in results:
        st = r.get("status")
        if st in summary:
            summary[st] += 1
            
    print(f"DEBUG: perform_verification completed. Summary: {summary}")
    return {"results": results, "summary": summary}
