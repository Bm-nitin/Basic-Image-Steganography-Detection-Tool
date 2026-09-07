// Main JavaScript for Basic Image Steganography Detection Tool

document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('image-input');
    const uploadForm = document.getElementById('upload-form');
    const fileDetails = document.getElementById('file-details');
    const fileNameSpan = document.getElementById('file-name');
    const fileSizeSpan = document.getElementById('file-size');
    const submitBtn = document.getElementById('submit-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingStatus = document.getElementById('loading-status');

    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
    const ALLOWED_EXTS = ['png', 'jpg', 'jpeg', 'bmp', 'webp'];

    if (dropzone && fileInput) {
        // Trigger file picker on dropzone click or keyboard activation
        dropzone.addEventListener('click', () => {
            fileInput.click();
        });

        dropzone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        // Drag & Drop event listeners
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('dragover');
            });
        });

        // Drop handling with DataTransfer binding
        dropzone.addEventListener('drop', (e) => {
            if (e.dataTransfer && e.dataTransfer.files.length > 0) {
                const droppedFile = e.dataTransfer.files[0];
                try {
                    const dt = new DataTransfer();
                    dt.items.add(droppedFile);
                    fileInput.files = dt.files;
                } catch (err) {
                    console.warn('DataTransfer API fallback:', err);
                }
                handleFileSelection(droppedFile);
            }
        });

        // File input change handling
        fileInput.addEventListener('change', (e) => {
            if (fileInput.files && fileInput.files.length > 0) {
                handleFileSelection(fileInput.files[0]);
            }
        });
    }

    function handleFileSelection(file) {
        if (!file) return;

        const ext = file.name.split('.').pop().toLowerCase();
        
        // Check extension
        if (!ALLOWED_EXTS.includes(ext)) {
            alert(`Unsupported file format ('.${ext}'). Allowed formats: PNG, JPG, JPEG, BMP, WEBP.`);
            fileInput.value = '';
            if (fileDetails) fileDetails.style.display = 'none';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            alert(`File size exceeds 10 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB). Please select a smaller image.`);
            fileInput.value = '';
            if (fileDetails) fileDetails.style.display = 'none';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        // Display selected file info
        if (fileNameSpan) fileNameSpan.textContent = file.name;
        if (fileSizeSpan) fileSizeSpan.textContent = formatBytes(file.size);
        if (fileDetails) fileDetails.style.display = 'block';
        if (submitBtn) submitBtn.disabled = false;
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Handle form submit with dynamic loading state
    if (uploadForm) {
        uploadForm.addEventListener('submit', (e) => {
            if (!fileInput.files || fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select an image to inspect.');
                return;
            }

            if (loadingOverlay) {
                loadingOverlay.style.display = 'flex';
                const statusSteps = [
                    'Verifying file signature and magic bytes...',
                    'Scanning for appended data past EOF...',
                    'Decomposing RGB and grayscale bit planes...',
                    'Executing Chi-Square Pairs of Values attack...',
                    'Calculating Shannon Entropy and Sample Pair metrics...',
                    'Synthesizing heuristic suspicion index...'
                ];

                let stepIdx = 0;
                const statusInterval = setInterval(() => {
                    stepIdx = (stepIdx + 1) % statusSteps.length;
                    if (loadingStatus) {
                        loadingStatus.textContent = statusSteps[stepIdx];
                    }
                }, 750);
            }
        });
    }
});
