import os
import base64
import json
from typing import Any, Literal
import re

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

# ==========================
# Конфигурация OpenAI клиента
# ==========================

load_dotenv()

# ВАЖНО: убери ключ из кода и вынеси в переменную окружения!
# client = OpenAI()  # если OPENAI_API_KEY задан в окружении
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ==========================
# Pydantic-модели
# ==========================


class SignInfo(BaseModel):
    sign_name: str
    meaning: str


class ImageAnalysis(BaseModel):
    is_valid: bool
    signs_found: list[SignInfo]
    description: str


class AuditIssue(BaseModel):
    source: Literal["BOL", "PLACARD", "CARGO", "CROSS"]
    severity: Literal["info", "warning", "error"]
    message: str


class AuditResult(BaseModel):
    is_passed: bool
    issues: list[AuditIssue]
    summary: str


class AnalyzeImageResponse(BaseModel):
    bolPhoto: ImageAnalysis
    markerPhoto: ImageAnalysis
    cargoPhoto: ImageAnalysis
    audit: AuditResult


ImageType = Literal["bolPhoto", "markerPhoto", "cargoPhoto"]


# ==========================
# Вспомогательные функции
# ==========================


def encode_image_to_data_url(image_bytes: bytes, content_type: str) -> str:
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{image_base64}"


def build_system_prompt(image_type: ImageType) -> str:
    """
    Формируем системный промпт в зависимости от типа изображения.
    """
    base_intro = (
        "You are a computer vision assistant for a Hazmat Load Audit System. "
        "You receive a single image and must analyze it according to US DOT / FMCSA hazmat rules. "
        "You MUST respond strictly in JSON with the structure:\n"
        "{\n"
        '  "is_valid": boolean,\n'
        '  "signs_found": [ {"sign_name": "string", "meaning": "string"} ],\n'
        '  "description": "general summary of the scene and compliance"\n'
        "}\n"
        'Use double quotes for all JSON keys and string values. '
        "Do not include any text outside of JSON."
    )

    if image_type == "bolPhoto":
        specific = (
            "\n\nThis image is: BOL / shipping paper.\n"
            "Evaluate compliance with 49 CFR 172.200–204 using ONLY what is visible on the document. "
            "Specifically check:\n"
            "- Proper Shipping Name: exact DOT-authorized name, no unauthorized abbreviations.\n"
            "- Hazard Class / Division: numeric class (e.g., '3', '8', '5.2') following shipping name.\n"
            "- UN/NA Identification Number: format like 'UN1170' or 'NA1993'.\n"
            "- Packing Group: Roman numerals I, II, or III where required.\n"
            "- Total Quantity: amount and unit of measure for each hazmat line item.\n"
            "- HM Column Marking: 'X' or 'RQ' clearly marked in hazardous material column.\n"
            "- Entry Sequence: shipping name, hazard class, UN number, packing group in required order.\n"
            "- 24-Hour Emergency Phone: monitored phone number (e.g., CHEMTREC 800-424-9300).\n"
            "- Shipper Certification: signed statement of proper classification/packaging/etc.\n"
            "- RQ Notation: 'RQ' present where reportable quantity applies.\n"
            "- Technical Name for N.O.S.: chemical name in parentheses for N.O.S. entries.\n"
            "- No Forbidden Combinations: obviously incompatible materials not listed for same vehicle.\n"
            "In 'signs_found', list each detected compliance-relevant element (e.g. 'UN1170', 'RQ', 'Packing Group II'). "
            "In 'description', summarize overall BOL compliance and any missing or unclear fields. "
            '"is_valid" should be true only if the BOL appears compliant based on what is visible.'
        )
    elif image_type == "markerPhoto":
        specific = (
            "\n\nThis image is: truck / trailer placard or marker on the vehicle exterior.\n"
            "Evaluate compliance with 49 CFR 172.500–560 (placards). Check:\n"
            "- Correct Placard Class: placard hazard class matches BOL hazard class.\n"
            "- UN Number Display: for bulk shipments, UN number on placard matches BOL.\n"
            "- Four-Sided Placement: placards visible on front, rear, and both sides (as far as the photo allows).\n"
            "- Placard Condition: readable, not faded/obscured, correct diamond orientation (point-up).\n"
            "- DANGEROUS Placard: used correctly if multiple hazard classes each exceed 1,000 lbs.\n"
            "- Subsidiary Hazard Placards: present where required by subsidiary hazards.\n"
            "In 'signs_found', list each visible placard or marking (e.g. 'Class 3 flammable placard with UN1203'). "
            "In 'description', summarize overall placard compliance and any visibility/condition issues. "
            '"is_valid" should be true only if placards appear compliant based on what is visible.'
        )
    else:  # cargoPhoto
        specific = (
            "\n\nThis image is: cargo / load inside or on the vehicle.\n"
            "Evaluate load verification and securement. Check:\n"
            "- Package Markings Match BOL: visible UN number and proper shipping name on packages.\n"
            "- Package Labels Match BOL: hazard class labels on packages.\n"
            "- Load Securement: cargo properly secured, no visible shifting hazards, meets FMCSA rules.\n"
            "- Material Compatibility: no incompatible materials loaded adjacent to each other.\n"
            "- Orientation Compliance: 'THIS SIDE UP' arrows and orientation markings respected.\n"
            "In 'signs_found', list important labels/markings/securement features (e.g. 'UN1993 label', 'Class 3 label', 'ratchet straps'). "
            "In 'description', summarize load securement quality and any obvious non-compliance. "
            '"is_valid" should be true only if the load appears compliant based on what is visible.'
        )

    return base_intro + specific


# ==========================
# Сервис для работы с OpenAI
# ==========================


async def analyze_image_with_openai(
    image_bytes: bytes,
    content_type: str,
    image_type: ImageType,
) -> ImageAnalysis:
    data_url = encode_image_to_data_url(image_bytes, content_type)
    system_prompt = build_system_prompt(image_type)

    try:
        response = client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image according to the provided hazmat checklist and respond ONLY with JSON.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                            },
                        },
                    ],
                },
            ],
            temperature=0.1,
        )
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")

    try:
        content = response.choices[0].message.content  # type: ignore[assignment]
    except (AttributeError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"Unexpected OpenAI response format: {str(e)}")

    if not content or not isinstance(content, str):
        raise HTTPException(status_code=502, detail="OpenAI returned empty content.")

    try:
        parsed: Any = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Failed to parse JSON from OpenAI response. "
                   "Make sure the model is instructed to return pure JSON.",
        )

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="OpenAI returned JSON as a string, but it is not valid JSON.")

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail="OpenAI JSON must be an object with fields: is_valid, signs_found, description.",
        )

    try:
        result = ImageAnalysis(**parsed)
    except ValidationError as ve:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI response does not match expected schema: {ve.errors()}",
        )

    return result


def run_audit(bol: ImageAnalysis, marker: ImageAnalysis, cargo: ImageAnalysis) -> AuditResult:
    issues: list[AuditIssue] = []

    # --- Вспомогательные парсеры для UN и класса опасности ---
    def extract_uns_and_classes(analysis: ImageAnalysis) -> tuple[set[str], set[str]]:
        un_numbers: set[str] = set()
        classes: set[str] = set()

        patterns = [
            r"\bUN(\d{3,4})\b",        # UN1993, UN3077
            r"\bUN\s*(\d{3,4})\b",
        ]
        class_patterns = [
            r"\bClass\s+(\d(?:\.\d)?)\b",  # Class 3, Class 9, Class 5.2
        ]

        def scan_text(text: str) -> None:
            for p in patterns:
                for m in re.finditer(p, text, flags=re.IGNORECASE):
                    un_numbers.add(f"UN{m.group(1)}")
            for p in class_patterns:
                for m in re.finditer(p, text, flags=re.IGNORECASE):
                    classes.add(m.group(1))

        for s in analysis.signs_found:
            scan_text(s.sign_name)
            scan_text(s.meaning)
        scan_text(analysis.description)

        return un_numbers, classes

    bol_uns, bol_classes = extract_uns_and_classes(bol)
    marker_uns, marker_classes = extract_uns_and_classes(marker)
    cargo_uns, cargo_classes = extract_uns_and_classes(cargo)

    # BOL-level
    if not bol.is_valid:
        issues.append(
            AuditIssue(
                source="BOL",
                severity="error",
                message="BOL (shipping paper) appears non-compliant based on visible information.",
            )
        )

    # Placard-level
    if not marker.is_valid:
        issues.append(
            AuditIssue(
                source="PLACARD",
                severity="error",
                message="Placards / vehicle markers appear non-compliant based on visible information.",
            )
        )

    # Cargo-level
    if not cargo.is_valid:
        issues.append(
            AuditIssue(
                source="CARGO",
                severity="error",
                message="Cargo / load securement or labeling appears non-compliant based on visible information.",
            )
        )

    # --- Кросс-проверки по UN и hazard class ---
    # Если в BOL есть хотя бы один UN, а в placard/cargo другие – это ошибка.
    if bol_uns and marker_uns and not (bol_uns & marker_uns):
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="error",
                message=f"UN numbers on BOL {sorted(bol_uns)} do not match UN numbers on placards {sorted(marker_uns)}.",
            )
        )
    if bol_uns and cargo_uns and not (bol_uns & cargo_uns):
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="error",
                message=f"UN numbers on BOL {sorted(bol_uns)} do not match UN numbers on cargo packages {sorted(cargo_uns)}.",
            )
        )

    # Классы опасности: если везде есть классы, но множества не пересекаются – это ошибка.
    if bol_classes and marker_classes and not (bol_classes & marker_classes):
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="error",
                message=f"Hazard classes on BOL {sorted(bol_classes)} do not match classes on placards {sorted(marker_classes)}.",
            )
        )
    if bol_classes and cargo_classes and not (bol_classes & cargo_classes):
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="error",
                message=f"Hazard classes on BOL {sorted(bol_classes)} do not match classes on cargo labels {sorted(cargo_classes)}.",
            )
        )

    # Простые кросс-проверки по общим флагам is_valid
    if bol.is_valid and not marker.is_valid:
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="warning",
                message="BOL looks compliant but placards do not – possible BOL-to-placard mismatch.",
            )
        )
    if bol.is_valid and not cargo.is_valid:
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="warning",
                message="BOL looks compliant but cargo/load does not – possible BOL-to-package mismatch.",
            )
        )
    if marker.is_valid and not bol.is_valid:
        issues.append(
            AuditIssue(
                source="CROSS",
                severity="warning",
                message="Placards look compliant but BOL does not – shipping paper may be incorrect for displayed placards.",
            )
        )

    has_errors = any(i.severity == "error" for i in issues)
    summary_parts = []
    if not has_errors:
        summary_parts.append("No critical compliance errors detected based on the three images.")
    else:
        summary_parts.append("Critical compliance issues detected in one or more images.")
    if issues:
        summary_parts.append(f"Total issues: {len(issues)}.")

    summary = " ".join(summary_parts) if summary_parts else "No issues detected."

    return AuditResult(
        is_passed=not has_errors,
        issues=issues,
        summary=summary,
    )


# ==========================
# FastAPI приложение и эндпоинт
# ==========================

app = FastAPI(title="Hazmat Image Analysis API", version="0.2.0")


@app.get("/health")
async def health_check():
    return JSONResponse({"status": "ok"})


@app.post("/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(
    bolPhoto: UploadFile = File(...),
    markerPhoto: UploadFile = File(...),
    cargoPhoto: UploadFile = File(...),
):
    for file in (bolPhoto, markerPhoto, cargoPhoto):
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file '{file.filename}' must be an image (content-type image/*).",
            )

    try:
        bol_bytes = await bolPhoto.read()
        marker_bytes = await markerPhoto.read()
        cargo_bytes = await cargoPhoto.read()
        if not bol_bytes or not marker_bytes or not cargo_bytes:
            raise HTTPException(status_code=400, detail="One or more uploaded files are empty.")
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded files.")

    bol_result = await analyze_image_with_openai(bol_bytes, bolPhoto.content_type, "bolPhoto")
    marker_result = await analyze_image_with_openai(marker_bytes, markerPhoto.content_type, "markerPhoto")
    cargo_result = await analyze_image_with_openai(cargo_bytes, cargoPhoto.content_type, "cargoPhoto")

    audit = run_audit(bol_result, marker_result, cargo_result)

    return AnalyzeImageResponse(
        bolPhoto=bol_result,
        markerPhoto=marker_result,
        cargoPhoto=cargo_result,
        audit=audit,
    )


@app.get("/")
async def root():
    return JSONResponse({"message": "Hazmat Image Analysis API. Use POST /analyze-image with bolPhoto, markerPhoto, cargoPhoto."})