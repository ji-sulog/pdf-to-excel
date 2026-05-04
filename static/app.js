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
const convertAgainBtn = document.getElementById('convertAgainBtn');
const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');
const retryBtn = document.getElementById('retryBtn');

let selectedFile = null;
let downloadUrl = null;
let downloadFileName = null;

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
}

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  setFile(file);
});

fileInput.addEventListener('change', () => {
  setFile(fileInput.files[0]);
});

removeFile.addEventListener('click', resetFile);

convertAgainBtn.addEventListener('click', resetFile);
retryBtn.addEventListener('click', resetFile);

downloadBtn.addEventListener('click', () => {
  if (downloadUrl) {
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = downloadFileName || 'converted.xlsx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
});

convertBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  // UI: loading state
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

    const response = await fetch('/convert', {
      method: 'POST',
      body: formData,
    });

    clearInterval(msgInterval);

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '알 수 없는 오류' }));
      throw new Error(err.detail || '변환 실패');
    }

    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition') || '';
    const nameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
    downloadFileName = nameMatch
      ? decodeURIComponent(nameMatch[1].replace(/['"]/g, ''))
      : `${selectedFile.name.replace('.pdf', '')}_변환.xlsx`;

    downloadUrl = URL.createObjectURL(blob);

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
