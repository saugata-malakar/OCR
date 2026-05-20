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