import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, Preformatted
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

# ── Configuration ─────────────────────────────────────────────────────────────
REPO_DIR   = r"e:\AntiGravity\project_2swathi\AlliedEdge"
OUTPUT_PDF = r"e:\AntiGravity\project_2swathi\AlliedEdge_Code.pdf"
REPO_NAME  = "AlliedEdge"
REPO_URL   = "https://github.com/Rayan-Mohammed-Rafeeq/AlliedEdge"

# File extensions to include
INCLUDE_EXTENSIONS = {
    ".java", ".xml", ".properties", ".yaml", ".yml",
    ".ts", ".tsx", ".js", ".jsx", ".css", ".html",
    ".json", ".md", ".txt", ".gitignore", ".prettierrc",
    ".npmrc", ".env", ".toml", ".sh", ".cmd",
    ".dockerfile", ".dockerignore",
}
# Specific filenames (no extension) to include
INCLUDE_FILENAMES = {"Dockerfile", "LICENSE", "Makefile", "README"}

# Directories / files to skip
SKIP_DIRS  = {".git", "node_modules", ".mvn", "target", "dist", "build"}
SKIP_FILES = {"pnpm-lock.yaml", "package-lock.json", "mvnw", "mvnw.cmd"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def should_include(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    # skip hidden / build dirs
    for part in parts[:-1]:
        if part in SKIP_DIRS or part.startswith("."):
            return False
    filename = parts[-1]
    if filename in SKIP_FILES:
        return False
    _, ext = os.path.splitext(filename)
    return (ext.lower() in INCLUDE_EXTENSIONS) or (filename in INCLUDE_FILENAMES)


def collect_files(root: str):
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs in-place so os.walk doesn't descend
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel  = os.path.relpath(full, root)
            if should_include(rel):
                results.append((rel, full))
    results.sort(key=lambda x: x[0].lower())
    return results


def read_file(path: str) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, PermissionError):
            continue
    return "<< binary or unreadable file >>"


# ── Page numbering canvas ─────────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_page_number(self, page_count):
        self.setFont("Courier", 8)
        self.setFillColor(colors.HexColor("#888888"))
        self.drawRightString(
            A4[0] - 20 * mm, 12 * mm,
            f"Page {self._pageNumber} of {page_count}"
        )
        self.drawString(
            20 * mm, 12 * mm,
            f"{REPO_NAME}  ·  {REPO_URL}"
        )


# ── Build PDF ─────────────────────────────────────────────────────────────────
def build_pdf(files):
    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"{REPO_NAME} – Full Source Code",
        author="AlliedEdge Repository",
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "RepoTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "RepoSubtitle",
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#4a5568"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    url_style = ParagraphStyle(
        "RepoURL",
        fontName="Courier",
        fontSize=9,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    toc_header_style = ParagraphStyle(
        "TOCHeader",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=10,
        spaceAfter=6,
    )
    toc_entry_style = ParagraphStyle(
        "TOCEntry",
        fontName="Courier",
        fontSize=8,
        textColor=colors.HexColor("#374151"),
        spaceAfter=1,
        leading=11,
    )
    file_header_style = ParagraphStyle(
        "FileHeader",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#ffffff"),
        backColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=4,
        leftIndent=6,
        rightIndent=6,
        borderPadding=(4, 6, 4, 6),
    )
    code_style = ParagraphStyle(
        "CodeBlock",
        fontName="Courier",
        fontSize=7.5,
        textColor=colors.HexColor("#1e293b"),
        backColor=colors.HexColor("#f8fafc"),
        spaceAfter=2,
        leading=10,
        leftIndent=4,
        rightIndent=4,
        borderPadding=(4, 4, 4, 4),
    )

    story = []

    # ── Cover page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 50 * mm))
    story.append(Paragraph(f"📦 {REPO_NAME}", title_style))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="60%", thickness=2, color=colors.HexColor("#2563eb"), hAlign="CENTER"))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Full Source Code Export", subtitle_style))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(REPO_URL, url_style))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Total files included: <b>{len(files)}</b>", subtitle_style))
    story.append(PageBreak())

    # ── Table of Contents ─────────────────────────────────────────────────────
    story.append(Paragraph("Table of Contents", toc_header_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 3 * mm))
    for i, (rel, _) in enumerate(files, 1):
        story.append(Paragraph(f"{i:>3}.  {rel.replace(chr(92), '/')}", toc_entry_style))
    story.append(PageBreak())

    # ── File contents ─────────────────────────────────────────────────────────
    for rel, full in files:
        content = read_file(full)
        display_path = rel.replace("\\", "/")

        # File header bar
        story.append(Paragraph(f"📄  {display_path}", file_header_style))

        # Code block — use Preformatted for monospace verbatim text
        # Escape XML special chars
        safe = (content
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

        # Limit very large files to avoid memory issues (show first 1500 lines)
        lines = safe.split("\n")
        truncated = False
        if len(lines) > 1500:
            lines = lines[:1500]
            truncated = True

        code_text = "\n".join(lines)
        if truncated:
            code_text += f"\n\n... [truncated — file has more lines] ..."

        story.append(Preformatted(code_text, code_style))
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
        story.append(Spacer(1, 3 * mm))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"\n✅  PDF generated: {OUTPUT_PDF}")
    print(f"   Files included : {len(files)}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Scanning repository: {REPO_DIR}")
    files = collect_files(REPO_DIR)
    print(f"Found {len(files)} files to include.")
    for rel, _ in files:
        print(f"  + {rel}")
    print("\nGenerating PDF …")
    build_pdf(files)
