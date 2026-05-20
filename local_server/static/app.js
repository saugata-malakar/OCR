const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('image');
const fileName = document.getElementById('fileName');

if (dropzone && fileInput && fileName) {
  const updateLabel = () => {
    fileName.textContent = fileInput.files && fileInput.files.length
      ? fileInput.files[0].name
      : 'No file selected';
  };

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (event) => {
    const files = event.dataTransfer.files;
    if (files && files.length) {
      fileInput.files = files;
      updateLabel();
    }
  });

  fileInput.addEventListener('change', updateLabel);
  updateLabel();
}

// Async upload/poll flow
const uploadForm = document.getElementById('uploadForm');
const asyncStatus = document.getElementById('asyncStatus');
const asyncResults = document.getElementById('asyncResults');

if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    asyncStatus.textContent = '';
    asyncResults.innerHTML = '';

    const files = fileInput.files;
    if (!files || files.length === 0) {
      asyncStatus.textContent = 'Please select a file first.';
      return;
    }

    const fd = new FormData();
    fd.append('image', files[0]);

    try {
      asyncStatus.textContent = 'Uploading…';
      const resp = await fetch('/upload_async', { method: 'POST', body: fd });
      if (resp.status !== 202) {
        const err = await resp.json();
        asyncStatus.textContent = 'Upload failed: ' + (err.error || resp.statusText);
        return;
      }
      const body = await resp.json();
      const jobId = body.job_id;
      asyncStatus.textContent = `Job ${jobId} queued — waiting for results...`;

      // Poll
      const statusUrl = body.status_url;
      const resultUrl = body.result_url;

      const poll = setInterval(async () => {
        try {
          const s = await fetch(statusUrl);
          const data = await s.json();
          if (data.status === 'done') {
            clearInterval(poll);
            asyncStatus.textContent = 'Processing complete — fetching results…';
            const r = await fetch(resultUrl);
            const res = await r.json();
            renderResults(res);
            asyncStatus.textContent = 'Ready';
          } else if (data.status === 'failed') {
            clearInterval(poll);
            asyncStatus.textContent = 'Job failed: ' + (data.error || 'unknown error');
          } else {
            asyncStatus.textContent = 'Job ' + jobId + ' status: ' + data.status;
          }
        } catch (err) {
          console.error(err);
          asyncStatus.textContent = 'Error polling job status';
          clearInterval(poll);
        }
      }, 2000);
    } catch (err) {
      console.error(err);
      asyncStatus.textContent = 'Upload failed';
    }
  });
}

function renderResults(res) {
  if (!asyncResults) return;
  if (res.status !== 'done') {
    asyncResults.innerHTML = `<div class="results-error">${res.error || 'No results available'}</div>`;
    return;
  }

  const texts = (res.result_texts || []).map(t => `<span class="text-chip">${escapeHtml(t)}</span>`).join(' ');
  const summary = res.result_summary || '';
  const img = res.annotated_url ? `<img class="result-image" src="${res.annotated_url}" alt="Annotated result">` : '';
  const artifacts = (res.output_files || []).map(p => `<a class="artifact-link" href="${p}" target="_blank" rel="noreferrer">${p}</a>`).join('<br>');

  asyncResults.innerHTML = `
    <div class="results-stack">
      <section class="results-card">
        <div class="section-heading"><h2>Recognized text</h2></div>
        <div class="text-grid">${texts || '<div class="empty-state">No text found</div>'}</div>
      </section>
      <section class="results-card results-card-split">
        <div>
          <div class="section-heading"><h2>OCR summary</h2></div>
          <pre class="summary-block">${escapeHtml(summary)}</pre>
        </div>
        <div>
          <div class="section-heading"><h2>Preview</h2></div>
          ${img || '<div class="empty-preview">No preview available.</div>'}
        </div>
      </section>
      <section class="results-card">
        <div class="section-heading"><h2>Saved artifacts</h2></div>
        <div class="artifact-list">${artifacts || '<div class="empty-state">No artifacts</div>'}</div>
      </section>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}