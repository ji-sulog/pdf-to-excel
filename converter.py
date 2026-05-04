import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import re


def is_scanned_page(page) -> bool:
    text = page.extract_text() or ""
    return len(text.strip()) < 20


def ocr_page(image, lang="kor+eng") -> str:
    return pytesseract.image_to_string(image, lang=lang)


def extract_page_content(page, ocr_image=None, lang="kor+eng"):
    """Returns list of (type, data) tuples: ('text', str) or ('table', list[list])"""
    items = []

    tables = page.extract_tables()
    table_bboxes = []
    for table_obj in page.find_tables():
        table_bboxes.append(table_obj.bbox)

    if is_scanned_page(page):
        if ocr_image:
            text = ocr_page(ocr_image, lang)
            if text.strip():
                items.append(("text", text.strip()))
    else:
        # Extract text excluding table regions
        words = page.extract_words()
        non_table_lines = []
        current_line = []
        current_y = None

        for word in words:
            in_table = any(
                bbox[0] <= word["x0"] and word["x1"] <= bbox[2]
                and bbox[1] <= word["top"] and word["bottom"] <= bbox[3]
                for bbox in table_bboxes
            )
            if in_table:
                continue

            y = round(word["top"], 0)
            if current_y is None or abs(y - current_y) > 3:
                if current_line:
                    non_table_lines.append(" ".join(w["text"] for w in current_line))
                current_line = [word]
                current_y = y
            else:
                current_line.append(word)

        if current_line:
            non_table_lines.append(" ".join(w["text"] for w in current_line))

        if non_table_lines:
            items.append(("text", "\n".join(non_table_lines)))

    for table in tables:
        if table:
            items.append(("table", table))

    return items


def style_header_row(ws, row_idx, num_cols):
    fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    font = Font(color="FFFFFF", bold=True)
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_data_row(ws, row_idx, num_cols, is_even):
    fill_color = "DDEEFF" if is_even else "FFFFFF"
    fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = fill
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def write_to_excel(all_pages_content, lang="kor+eng") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "변환 결과"

    current_row = 1

    for page_num, items in enumerate(all_pages_content, start=1):
        # Page header
        ws.cell(row=current_row, column=1, value=f"[ {page_num} 페이지 ]")
        cell = ws.cell(row=current_row, column=1)
        cell.font = Font(bold=True, size=12, color="FFFFFF")
        cell.fill = PatternFill(start_color="2E4057", end_color="2E4057", fill_type="solid")
        ws.row_dimensions[current_row].height = 20
        current_row += 1

        for item_type, data in items:
            if item_type == "text":
                lines = data.split("\n")
                for line in lines:
                    if line.strip():
                        ws.cell(row=current_row, column=1, value=line.strip())
                        ws.row_dimensions[current_row].height = 15
                        current_row += 1
                current_row += 1  # blank row after text block

            elif item_type == "table":
                num_cols = max(len(row) for row in data if row)
                for row_i, row in enumerate(data):
                    if not row:
                        current_row += 1
                        continue
                    # Pad row to num_cols
                    padded = list(row) + [None] * (num_cols - len(row))
                    for col_i, value in enumerate(padded, start=1):
                        cell = ws.cell(row=current_row, column=col_i, value=value)

                    if row_i == 0:
                        style_header_row(ws, current_row, num_cols)
                        ws.row_dimensions[current_row].height = 22
                    else:
                        style_data_row(ws, current_row, num_cols, row_i % 2 == 0)
                        ws.row_dimensions[current_row].height = 18

                    current_row += 1
                current_row += 1  # blank row after table

        current_row += 1  # blank row between pages

    # Auto-fit column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, min(len(str(cell.value)), 50))
        ws.column_dimensions[col_letter].width = max(10, max_len + 2)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def convert_pdf_to_excel(pdf_path: str, lang: str = "kor+eng") -> bytes:
    all_pages_content = []

    with pdfplumber.open(pdf_path) as pdf:
        scanned_indices = []
        for i, page in enumerate(pdf.pages):
            if is_scanned_page(page):
                scanned_indices.append(i)

        ocr_images = {}
        if scanned_indices:
            images = convert_from_path(pdf_path, dpi=200)
            for i in scanned_indices:
                if i < len(images):
                    ocr_images[i] = images[i]

        for i, page in enumerate(pdf.pages):
            items = extract_page_content(page, ocr_image=ocr_images.get(i), lang=lang)
            all_pages_content.append(items)

    return write_to_excel(all_pages_content, lang)
