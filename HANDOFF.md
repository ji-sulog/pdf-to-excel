# PDF → Excel 변환기 — 작업 인수인계 문서

> 다른 로컬 환경에서 동일한 AI와 이어서 작업하기 위한 문서입니다.

---

## 프로젝트 개요

PDF 파일을 엑셀(.xlsx)로 변환하는 FastAPI 웹 애플리케이션.
텍스트, 표, 스캔 이미지(OCR), 임베디드 이미지를 모두 지원하며
PDF의 **2D 레이아웃(x/y 좌표)을 Excel 그리드에 최대한 재현**하는 것이 핵심 목표.

- GitHub: https://github.com/ji-sulog/pdf-to-excel
- 로컬 실행: http://localhost:8000

---

## 환경 설정

### 사전 요구사항
```bash
brew install tesseract tesseract-lang   # OCR 엔진
brew install poppler                     # pdf2image 의존성 (pdftoppm)
```

### 설치 및 실행
```bash
git clone https://github.com/ji-sulog/pdf-to-excel.git
cd pdf-to-excel

python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pdfplumber openpyxl python-multipart pillow pytesseract pdf2image

python main.py
```

---

## 파일 구조

```
pdf-to-excel/
├── main.py           # FastAPI 서버, /convert POST 엔드포인트
├── converter.py      # PDF → Excel 변환 핵심 로직 (가장 중요)
├── static/
│   ├── index.html    # UI (드래그앤드롭, 변환, 미리보기 모달)
│   ├── app.js        # 프론트엔드 JS (SheetJS 기반 인브라우저 미리보기)
│   └── style.css     # 스타일
├── uploads/          # 임시 업로드 디렉토리 (변환 후 자동 삭제)
├── README.md         # 사용자용 문서
└── HANDOFF.md        # 이 파일
```

---

## converter.py 핵심 구조

### 상수
```python
NUM_COLS = 12   # PDF 전체 너비를 나눌 Excel 컬럼 수
```

### 좌표 변환
```python
def x_to_col(x, page_width, num_cols=NUM_COLS):
    """PDF x 좌표(pt) → Excel 컬럼 번호(1-indexed)"""
    col = int(x / page_width * num_cols) + 1
    return max(1, min(num_cols, col))

def bbox_to_cols(x0, x1, page_width, num_cols=NUM_COLS):
    """bbox x 범위 → (col_start, col_end)"""
```

### 처리 파이프라인
```
pdfplumber.open()
  └─ 페이지별
       ├─ is_scanned_page() → True: OCR(pytesseract)로 텍스트 추출
       └─ False: collect_elements()
                  ├─ 테이블: find_tables() + 행별 높이 수집
                  ├─ 이미지: page.images → crop_page_region() → PIL 크롭
                  └─ 텍스트: extract_words() → 줄 단위 그룹핑
            → build_render_plan()  (y 오름차순 정렬)
            → 렌더링:
                 ├─ 'table' → write_table() (병합 셀 + 테두리 + PDF 행높이)
                 └─ 'band'  → 텍스트(서브행 배정 + 셀병합) / 이미지(XLImage)
```

### 핵심 함수 요약

| 함수 | 역할 |
|------|------|
| `safe_value(v)` | 불법 문자(`\x00` 등) 제거, openpyxl 호환 값 반환 |
| `is_scanned_page(page)` | 텍스트 20자 미만이면 스캔 페이지로 판단 |
| `collect_elements()` | 테이블/이미지/텍스트를 bbox와 함께 수집 |
| `group_by_y_bands()` | y 범위 겹치는 요소를 같은 밴드로 묶음 (tolerance=10pt) |
| `build_render_plan()` | 테이블은 개별, 텍스트/이미지는 y-밴드로 묶어 y순 정렬 |
| `detect_spans()` | 수직 병합 먼저 → 수평 병합 (순서 중요, 반대면 버그) |
| `write_table()` | 병합 셀 + 테두리 + PDF 행높이 반영해 테이블 작성 |
| `crop_page_region()` | PDF 좌표 → PIL 이미지 크롭 |

---

## 지금까지 구현된 기능

### v1 (초기)
- FastAPI 서버, `/convert` 엔드포인트
- pdfplumber 기반 텍스트/테이블 추출
- openpyxl 엑셀 생성
- 드래그앤드롭 웹 UI

### v2 (레이아웃 개선)
- PDF 2D 좌표 기반 Excel 컬럼 매핑 (`x_to_col`)
- 이미지 추출 및 Excel 삽입 (`XLImage`)
- y-밴드 그룹핑으로 레이아웃 보존
- 테이블/텍스트/이미지 y순 렌더링 (`build_render_plan`)
- 수직 우선 셀 병합 감지로 RESULT 셀 버그 수정
- 테이블 간 MergedCell 충돌 수정

### v3 (서식 정리)
- `[ N 페이지 ]` 구분 헤더 제거
- 모든 셀 스타일(fill, 색상, bold) 제거
- **테이블 테두리만 유지** (검은색 실선)

### v4 (비례 레이아웃)
- 컬럼 너비: PDF 페이지 너비 비례 자동 계산
  - `col_width = page_width * 0.143 / NUM_COLS`
  - A4(598pt) 기준 컬럼당 7.1 chars
- 텍스트 셀 병합: bbox x0~x1 범위만큼 셀 병합
- 행 높이: PDF bbox 높이(pt) 직접 반영
  - 텍스트: 각 줄의 bbox 높이
  - 테이블: `tobj.rows[i].bbox` 기반

### 인브라우저 미리보기
- SheetJS(xlsx.full.min.js CDN) 사용
- 변환 완료 후 "미리보기" 버튼 → 모달로 엑셀 렌더링
- 모달 내 다운로드 버튼 제공

---

## 알려진 이슈 / 개선 필요 사항

### 레이아웃 재현
- [ ] 텍스트 폰트 크기를 PDF에서 읽어 Excel에 반영 (현재 고정 9pt)
- [ ] 텍스트 정렬(왼쪽/가운데/오른쪽)을 PDF 위치 기반으로 추론
- [ ] 다단 컬럼 PDF에서 컬럼 경계 자동 감지

### 테이블
- [ ] 복잡한 중첩 병합 셀 처리 정확도 향상
- [ ] 테이블 내 이미지(로고 등) 처리

### 기타
- [ ] 변환 완료 후 xlsx 임시 파일 자동 삭제 (현재 pdf만 삭제)
- [ ] 대용량 PDF 비동기 처리 (현재 동기 처리)
- [ ] 다중 페이지 PDF에서 페이지별 컬럼 너비 가중평균 적용

---

## 주요 버그 및 해결 기록

### 1. `Tel +8223002300 cannot be used in worksheets`
- 원인: pdfplumber가 `\x00` 등 불법 문자를 포함한 텍스트 반환
- 해결: `_ILLEGAL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')` 로 제거

### 2. RESULT 셀이 5컬럼을 잘못 흡수
- 원인: 수평 병합을 먼저 탐지해 수직 병합 대상 None 셀까지 흡수
- 해결: `detect_spans()`에서 수직 병합 먼저 처리, merged 집합에 추가 후 수평 탐지

### 3. `MergedCell attribute 'value' is read-only`
- 원인: 인접한 두 테이블이 y-밴드로 묶여 같은 시작 행에 겹쳐 기록
- 해결: `build_render_plan()`에서 테이블은 밴드에 묶지 않고 개별 항목으로 처리

### 4. Tel/Fax/email 중 마지막 것만 표시되는 문제
- 원인: 같은 y-밴드 내 3줄이 모두 `current_row`에 덮어쓰기
- 해결: 고유 y 좌표마다 서브행 인덱스 배정, 각 줄을 별도 행에 기록

---

## 앞으로 이어서 할 작업 (우선순위순)

1. **폰트 크기 반영** — PDF 텍스트 폰트 크기를 읽어 Excel 폰트 크기에 적용
2. **텍스트 정렬 추론** — x 좌표 기반으로 left/center/right 정렬 자동 적용
3. **xlsx 임시파일 자동 삭제** — 변환 완료 후 서버 측 파일 정리
4. **다중 PDF 일괄 변환** — 여러 파일 동시 업로드 및 ZIP 다운로드
