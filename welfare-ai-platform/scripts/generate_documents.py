"""Generate redistributable fictional citizens' documents, never real identifiers."""
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data" / "synthetic_documents"


def make_pdf(path: Path, document_type: str, fields: dict):
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=True)
    pdf.setTitle("Synthetic welfare project demonstration document")
    pdf.setAuthor("Welfare Scheme Assistant academic prototype")
    pdf.setFillColor(colors.HexColor("#123A48"))
    pdf.rect(0, 720, A4[0], 122, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(40, 787, "SYNTHETIC DEMONSTRATION DOCUMENT")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(40, 758, document_type.replace("_", " ").title())
    pdf.setFillColor(colors.HexColor("#172E35"))
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, 685, f"Document Type: {document_type}")
    y = 645
    for key, value in fields.items():
        pdf.drawString(40, y, f"{key}: {value}")
        y -= 32
    pdf.setStrokeColor(colors.HexColor("#CDDDE1"))
    pdf.line(40, 260, 555, 260)
    pdf.setFont("Helvetica", 10)
    for offset, text in enumerate([
        "Invented citizen and data. For academic testing only.",
        "No government seal, signature or identity number is represented.",
        "Extraction checks consistency; it does not authenticate this document.",
    ]):
        pdf.drawString(40, 235 - offset * 20, text)
    pdf.showPage()
    pdf.save()


def generate(destination: Path = DESTINATION):
    destination.mkdir(parents=True, exist_ok=True)
    for slug, name, dob, income in [
        ("asha", "Asha Rao", "1988-04-12", "120000"),
        ("meera", "Meera Shah", "1985-03-15", "120000"),
    ]:
        make_pdf(destination / f"{slug}-identity.pdf", "identity_proof", {"Full Name": name, "Date of Birth": dob})
        make_pdf(destination / f"{slug}-income{'-mismatch' if slug == 'meera' else ''}.pdf", "income_certificate", {"Full Name": name, "Annual Family Income": f"INR {income}"})
        make_pdf(destination / f"{slug}-residence.pdf", "residence_proof", {"Full Name": name, "State": "Telangana"})
    image = Image.new("RGB", (800, 400), "white")
    ImageDraw.Draw(image).text((40, 100), "SYNTHETIC IMAGE - OCR DISABLED\nNo real personal data", fill="black")
    image.save(destination / "synthetic-image.png")
    scanned = canvas.Canvas(str(destination / "scanned-image.pdf"), pagesize=A4, invariant=True)
    scanned.drawImage(str(destination / "synthetic-image.png"), 40, 400, width=500, height=250)
    scanned.save()
    writer = PdfWriter()
    writer.append(PdfReader(str(destination / "asha-identity.pdf")))
    writer.encrypt("synthetic-test-password")
    with (destination / "encrypted.pdf").open("wb") as handle:
        writer.write(handle)
    (destination / "corrupt.pdf").write_bytes(b"%PDF-1.7\nintentionally corrupt synthetic fixture")
    (destination / "spoofed.pdf").write_bytes(b"This text is not a PDF.")
    (destination / "README.md").write_text(
        "# Synthetic document fixtures\n\nAll names and data are fictional. No official document is reproduced.\n\n"
        "Asha Rao: DOB 1988-04-12, income INR120000, Telangana.\n"
        "Meera Shah: DOB 1985-03-15, profile income INR150000, Telangana. The income fixture intentionally states INR120000.\n"
        "A user-confirmed correction to INR150000 resolves the fixture mismatch but is never independent verification.\n\n"
        "Valid PNG and scanned image PDF require OCR (disabled). Encrypted, corrupt and spoofed files fail processing.\n"
        "Regenerate from the project root: `python scripts/generate_documents.py`.\n", encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(generate())
