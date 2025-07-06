TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Stock Prices Uploader</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet"/>
  <style>
    .dropzone {border:2px dashed #0d6efd;border-radius:16px;background:#f8fafc;transition:border-color .2s;text-align:center;padding:2.5rem 1rem;cursor:pointer;color:#6c757d;margin-bottom:1rem;}
    .dropzone.dragover {background:#e7f1ff;border-color:#0a58ca;color:#0a58ca;}
    .hidden-input {display:none;}
    #fileList {list-style-type: disc; margin: 0 0 1em 2em; padding: 0; font-size: 0.95em; color: #6c757d;}
    body {background:#f5f7fa;}
  </style>
</head>
<body>
<div class="container py-4">
  <h2 class="mb-4 text-center fw-bold">Stock CSV Uploader & Database</h2>
  <div class="row g-4">
    <div class="col-lg-5">
      <form id="uploadForm" enctype="multipart/form-data" method="post" action="/upload">
        <label class="dropzone" id="dropzone">
          <input type="file" class="hidden-input" id="fileInput" name="file" accept=".csv" multiple>
          <span id="dropzoneText">Drag & drop CSV file(s) here<br>or <span class="text-primary text-decoration-underline" style="cursor:pointer;">browse</span></span>
        </label>
        <ul id="fileList"></ul>
        <div class="mb-3 text-center fw-semibold">or</div>
        <div class="mb-3">
          <input type="text" class="form-control" name="folder_path" id="folder_path" placeholder="Type a folder path (local only)">
        </div>
        <button type="submit" class="btn btn-primary w-100 mb-2" id="uploadBtn">
          <span id="btnText">Upload</span>
          <span id="spinner" class="spinner-border spinner-border-sm d-none"></span>
        </button>
      </form>
      <div id="result" class="mt-3"></div>
    </div>
    <div class="col-lg-7">
<form method="get" class="mb-2 d-flex gap-2 align-items-center">
  <input type="text" class="form-control" name="search" placeholder="Search (e.g. file_name:Visa, date:2024-05-01, volume:10000, etc.)" value="{{ search }}">
  <button class="btn btn-outline-secondary" type="submit">Search</button>
  <a href="/" class="btn btn-outline-secondary">Clear</a>
</form>
<small class="text-muted">
  Search by <b>column:value</b> (e.g. <code>file_name:Visa</code>, <code>date:2024-05-01</code>, <code>volume:10000</code>), or just enter text to search file name/date.
</small>
      <div class="table-responsive border rounded-3 p-2 bg-white shadow-sm" style="min-height:300px;">
        {{ table_html|safe }}
      </div>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>
<script>
$(document).ready(function() {
  $('table').DataTable({
    searching: false,
    paging: true,
    ordering: true,
    pageLength: 20
  });
});

// File list logic
let selectedFiles = [];

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');

function updateFileList() {
  fileList.innerHTML = selectedFiles.length
    ? selectedFiles.map(f => `<li>${f.name}</li>`).join('')
    : '';
  document.getElementById('dropzoneText').textContent = selectedFiles.length
    ? 'Files selected:'
    : 'Drag & drop CSV file(s) here or browse';
}

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', e => {
  e.preventDefault(); dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', e => {
  e.preventDefault(); dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    for (let file of e.dataTransfer.files) {
      if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
        selectedFiles.push(file);
      }
    }
    updateFileList();
  }
});

fileInput.addEventListener('change', () => {
  for (let file of fileInput.files) {
    if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
      selectedFiles.push(file);
    }
  }
  updateFileList();
});

function clearFileInput() {
  fileInput.value = "";
  selectedFiles = [];
  updateFileList();
}

// FIXED AJAX Upload Logic
const form = document.getElementById('uploadForm');
form.onsubmit = async function(e) {
  e.preventDefault();
  const btn = document.getElementById('uploadBtn');
  const btnText = document.getElementById('btnText');
  const spinner = document.getElementById('spinner');
  btn.disabled = true; btnText.textContent = 'Uploading...'; spinner.classList.remove('d-none');
  // Build FormData manually (not from form element!)
  const formData = new FormData();
  // Add folder_path if present
  const folderPath = document.getElementById('folder_path').value;
  if (folderPath) formData.append('folder_path', folderPath);
  // Add all selected files
  selectedFiles.forEach(f => formData.append('file', f));
  let res, json;
  try {
    res = await fetch("/upload", {method: "POST", body: formData});
    json = await res.json();
  } catch {
    json = {error: "Upload failed. Try again."};
  }
  btn.disabled = false; btnText.textContent = 'Upload'; spinner.classList.add('d-none');
  let result = document.getElementById('result');
  if(json.results) {
    let html = json.results.map(r =>
      r.status === 'ok'
        ? `<div class="alert alert-success shadow rounded-3">✅ ${r.file}: ${r.rows} rows imported</div>`
        : `<div class="alert alert-danger shadow rounded-3">❌ ${r.file}: ${r.error}</div>`
    ).join('');
    result.innerHTML = html;
    clearFileInput();
  } else if(res?.ok) {
    result.innerHTML = `<div class="alert alert-success shadow rounded-3">${json.message}</div>`;
  } else {
    result.innerHTML = `<div class="alert alert-danger shadow rounded-3">${json.error || 'Unknown error.'}</div>`;
  }
};
</script>

</body>
</html>
"""