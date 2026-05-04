import os
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from converter import convert_pdf_to_excel

app = FastAPI(title="PDF to Excel Converter")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("static/index.html")


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    lang: str = Form(default="kor+eng"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    job_id = uuid.uuid4().hex
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
    xlsx_path = UPLOAD_DIR / f"{job_id}.xlsx"

    try:
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        excel_bytes = convert_pdf_to_excel(str(pdf_path), lang=lang)

        with open(xlsx_path, "wb") as f:
            f.write(excel_bytes)

        original_name = Path(file.filename).stem
        download_name = f"{original_name}_변환.xlsx"

        return FileResponse(
            path=str(xlsx_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=download_name,
            background=None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 중 오류 발생: {str(e)}")
    finally:
        if pdf_path.exists():
            pdf_path.unlink()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
