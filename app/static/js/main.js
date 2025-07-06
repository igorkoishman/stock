// Initialize DataTables after DOM is ready
document.addEventListener("DOMContentLoaded", function () {
  const table = document.querySelector("table");
  if (table) {
    $(table).DataTable({
      searching: false,
      paging: true,
      ordering: true,
      pageLength: 20,
    });
  }

  // --- Upload Elements ---
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileList = document.getElementById("fileList");
  const folderPathInput = document.getElementById("folder_path");
  const uploadBtn = document.getElementById("uploadBtn");
  const btnText = document.getElementById("btnText");
  const spinner = document.getElementById("spinner");
  const result = document.getElementById("result");

  let selectedFiles = [];

  function updateFileList() {
    fileList.innerHTML = selectedFiles.length
      ? selectedFiles.map((f) => `<li>${f.name}</li>`).join("")
      : "";
    document.getElementById("dropzoneText").textContent = selectedFiles.length
      ? "Files selected:"
      : "Drag & drop CSV file(s) here or browse";
  }

  // Drag and drop behavior
  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      const files = e.dataTransfer.files;
      if (files.length) {
        for (let file of files) {
          if (!selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
          }
        }
        updateFileList();
      }
    });

    fileInput.addEventListener("change", () => {
      for (let file of fileInput.files) {
        if (!selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
          selectedFiles.push(file);
        }
      }
      updateFileList();
    });
  }

  function clearFileInput() {
    fileInput.value = "";
    selectedFiles = [];
    updateFileList();
  }

  // Handle upload
  const form = document.getElementById("uploadForm");
  if (form) {
    form.onsubmit = async function (e) {
      e.preventDefault();

      uploadBtn.disabled = true;
      btnText.textContent = "Uploading...";
      spinner.classList.remove("d-none");

      const formData = new FormData();
      const folderPath = folderPathInput.value;
      if (folderPath) {
        formData.append("folder_path", folderPath);
      }
      selectedFiles.forEach((f) => formData.append("file", f));

      let res, json;
      try {
        res = await fetch("/upload", {
          method: "POST",
          body: formData,
        });
        json = await res.json();
      } catch (err) {
        console.error("Upload failed", err);
        json = { error: "Upload failed. Try again." };
      }

      uploadBtn.disabled = false;
      btnText.textContent = "Upload";
      spinner.classList.add("d-none");

      if (json.results) {
        result.innerHTML = json.results
          .map((r) =>
            r.status === "ok"
              ? `<div class="alert alert-success shadow rounded-3">✅ ${r.file}: ${r.rows} rows imported</div>`
              : `<div class="alert alert-danger shadow rounded-3">❌ ${r.file}: ${r.error}</div>`
          )
          .join("");
        clearFileInput();
      } else if (res?.ok) {
        result.innerHTML = `<div class="alert alert-success shadow rounded-3">${json.message}</div>`;
      } else {
        result.innerHTML = `<div class="alert alert-danger shadow rounded-3">${json.error || "Unknown error."}</div>`;
      }
    };
  }
});