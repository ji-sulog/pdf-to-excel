const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeFile = document.getElementById('removeFile');
const convertBtn = document.getElementById('convertBtn');
const btnText = document.getElementById('btnText');
const btnSpinner = document.getElementById('btnSpinner');
const langSelect = document.getElementById('langSelect');
const progressSection = document.getElementById('progressSection');
const progressText = document.getElementById('progressText');
const resultSection = document.getElementById('resultSection');
const resultMessage = document.getElementById('resultMessage');
const downloadBtn = document.getElementById('downloadBtn');
const previewBtn = document.getElementById('previewBtn');
const convertAgainBtn = document.getElementById('convertAgainBtn');
const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');
const retryBtn = document.getElementById('retryBtn');
const previewModal = document.getElementById('previewModal');
const previewContent = document.getElementById('previewContent');
const previewInfo = document.getElementById('previewInfo');
const closeModal = document.getElementById('closeModal');
const modalDownloadBtn = document.getElementById('modalDownloadBtn');
const modalBackdrop = document.querySelector('.modal-backdrop');

let selectedFile = null;
let downloadUrl = null;
let downloadFileName = null;
let excelBlob = null;

const pdfThumbnailWrap = document.getElementById('pdfThumbnailWrap');
const pdfThumbnail = document.getElementById('pdfThumbnail');

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    alert('PDF 파일만 업로드 가능합니다.');
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    alert('파일 크기가 50MB를 초과합니다.');
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  dropzone.classList.add('hidden');
  filePreview.classList.remove('hidden');
  convertBtn.disabled = false;
  resetResult();
  loadPdfThumbnail(file);
}

function resetFile() {
  selectedFile = null;
  fileInput.value = '';
  dropzone.classList.remove('hidden');
  filePreview.classList.add('hidden');
  convertBtn.disabled = true;
  resetResult();
}

function resetResult() {
  resultSection.classList.add('hidden');
  errorSection.classList.add('hidden');
  progressSection.classList.add('hidden');
  downloadUrl = null;
  downloadFileName = null;
  excelBlob = null;
}

async function loadPdfThumbnail(file) {
  pdfThumbnailWrap.classList.add('hidden');
  pdfThumbnail.src = '';
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/preview-pdf', { method: 'POST', body: formData });
    if (!res.ok) return;
    const blob = await res.blob();
    pdfThumbnail.src = URL.createObjectURL(blob);
    pdfThumbnailWrap.classList.remove('hidden');
  } catch (e) {
    // 썸네일 실패는 조용히 무시
  }
}

// 드래그앤드롭
dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  setFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => setFile(fileInput.files[0]));
removeFile.addEventListener('click', resetFile);
convertAgainBtn.addEventListener('click', resetFile);
retryBtn.addEventListener('click', resetFile);

// 다운로드
function triggerDownload() {
  if (!downloadUrl) return;
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = downloadFileName || 'converted.xlsx';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
downloadBtn.addEventListener('click', triggerDownload);
modalDownloadBtn.addEventListener('click', triggerDownload);

// 미리보기 모달
previewBtn.addEventListener('click', () => openPreview());
closeModal.addEventListener('click', closePreview);
modalBackdrop.addEventListener('click', closePreview);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePreview(); });

function closePreview() {
  previewModal.classList.add('hidden');
}

function openPreview() {
  previewModal.classList.remove('hidden');
  previewContent.innerHTML = '<div class="preview-loading">데이터를 불러오는 중...</div>';

  if (!excelBlob) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });

      if (!rows.length) {
        previewContent.innerHTML = '<div class="preview-loading">미리볼 데이터가 없습니다.</div>';
        return;
      }

      // 병합 셀 맵 구성
      const merges = sheet['!merges'] || [];
      const mergeMap = {};
      for (const { s, e } of merges) {
        for (let r = s.r; r <= e.r; r++) {
          if (!mergeMap[r]) mergeMap[r] = {};
          for (let c = s.c; c <= e.c; c++) {
            mergeMap[r][c] = (r === s.r && c === s.c)
              ? { rowspan: e.r - s.r + 1, colspan: e.c - s.c + 1 }
              : 'skip';
          }
        }
      }

      const totalCols = Math.max(...rows.map(r => r.length));
      const dataRows = rows.filter(r => r.some(c => c !== '')).length;
      previewInfo.textContent = `${dataRows}행 × ${totalCols}열`;

      let html = '<div class="preview-table-wrap"><table class="preview-table">';
      rows.forEach((row, ri) => {
        html += '<tr>';
        for (let ci = 0; ci < totalCols; ci++) {
          const m = mergeMap[ri]?.[ci];
          if (m === 'skip') continue;
          const val = row[ci] !== undefined ? row[ci] : '';
          const attrs = m ? ` rowspan="${m.rowspan}" colspan="${m.colspan}"` : '';
          html += `<td${attrs}>${escapeHtml(String(val))}</td>`;
        }
        html += '</tr>';
      });
      html += '</table></div>';
      previewContent.innerHTML = html;
    } catch (err) {
      previewContent.innerHTML = `<div class="preview-loading">미리보기 오류: ${err.message}</div>`;
    }
  };
  reader.readAsArrayBuffer(excelBlob);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 변환
convertBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  btnText.textContent = '변환 중...';
  btnSpinner.classList.remove('hidden');
  convertBtn.disabled = true;
  progressSection.classList.remove('hidden');
  progressText.textContent = 'PDF를 분석하고 있습니다...';
  resultSection.classList.add('hidden');
  errorSection.classList.add('hidden');

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('lang', langSelect.value);

  try {
    const messages = [
      'PDF를 분석하고 있습니다...',
      '텍스트를 추출하고 있습니다...',
      '표 데이터를 처리하고 있습니다...',
      '엑셀 파일을 생성하고 있습니다...',
    ];
    let msgIdx = 0;
    const msgInterval = setInterval(() => {
      msgIdx = (msgIdx + 1) % messages.length;
      progressText.textContent = messages[msgIdx];
    }, 2000);

    const response = await fetch('/convert', { method: 'POST', body: formData });
    clearInterval(msgInterval);

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '알 수 없는 오류' }));
      throw new Error(err.detail || '변환 실패');
    }

    excelBlob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition') || '';
    const nameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
    downloadFileName = nameMatch
      ? decodeURIComponent(nameMatch[1].replace(/['"]/g, ''))
      : `${selectedFile.name.replace('.pdf', '')}_변환.xlsx`;

    downloadUrl = URL.createObjectURL(excelBlob);

    progressSection.classList.add('hidden');
    resultSection.classList.remove('hidden');
    resultMessage.textContent = `"${selectedFile.name}" 변환이 완료되었습니다.`;

  } catch (err) {
    progressSection.classList.add('hidden');
    errorSection.classList.remove('hidden');
    errorMessage.textContent = err.message;
  } finally {
    btnText.textContent = '변환하기';
    btnSpinner.classList.add('hidden');
    convertBtn.disabled = false;
  }
});
