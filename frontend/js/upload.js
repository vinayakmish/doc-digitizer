/**
 * DocDigitizer — Upload Manager
 * Handles drag-and-drop, file selection, validation, and API upload.
 */

class UploadManager {
    constructor() {
        this.dropZone = document.getElementById('drop-zone');
        this.fileInput = document.getElementById('file-input');
        this.fileInfoCard = document.getElementById('file-info-card');
        this.fileNameEl = document.getElementById('file-name');
        this.fileSizeEl = document.getElementById('file-size');
        this.fileIconEl = document.getElementById('file-icon');
        this.processBtn = document.getElementById('process-btn');
        this.changeFileBtn = document.getElementById('change-file-btn');

        this.maxFileSize = 50 * 1024 * 1024; // 50 MB
        this.supportedExtensions = [
            'pdf', 'docx', 'doc', 'xlsx', 'xls',
            'csv', 'txt', 'png', 'jpg', 'jpeg',
            'tiff', 'tif', 'bmp', 'webp'
        ];

        this.abortController = null;
        this.init();
    }

    init() {
        // Drag & Drop
        this.dropZone.addEventListener('dragenter', (e) => this.handleDragEnter(e));
        this.dropZone.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.dropZone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.dropZone.addEventListener('drop', (e) => this.handleDrop(e));

        // Click to browse
        this.dropZone.addEventListener('click', () => this.fileInput.click());
        this.dropZone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.fileInput.click();
            }
        });

        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.selectFile(e.target.files[0]);
            }
        });

        // Process button
        this.processBtn.addEventListener('click', () => this.startUpload());

        // Change file
        this.changeFileBtn.addEventListener('click', () => this.reset());
    }

    handleDragEnter(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.add('dragover');
    }

    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        // Only remove if leaving the drop zone entirely
        if (!this.dropZone.contains(e.relatedTarget)) {
            this.dropZone.classList.remove('dragover');
        }
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.selectFile(files[0]);
        }
    }

    /**
     * Validate and select a file
     */
    selectFile(file) {
        const validation = this.validateFile(file);
        if (!validation.valid) {
            app.showToast(validation.error, 'error');
            return;
        }

        app.selectedFile = file;

        // Update UI
        this.fileNameEl.textContent = file.name;
        this.fileSizeEl.textContent = app.formatFileSize(file.size);
        this.fileIconEl.textContent = this.getFileIcon(this.getExtension(file.name));

        this.fileInfoCard.classList.remove('hidden');
        this.processBtn.disabled = false;

        app.showToast(`Selected: ${file.name}`, 'success');
    }

    /**
     * Validate file type and size
     */
    validateFile(file) {
        const ext = this.getExtension(file.name);

        if (!this.supportedExtensions.includes(ext)) {
            return {
                valid: false,
                error: `Unsupported file format: .${ext}. Please upload a supported document.`
            };
        }

        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                error: `File too large (${app.formatFileSize(file.size)}). Maximum size is 50 MB.`
            };
        }

        if (file.size === 0) {
            return {
                valid: false,
                error: 'The selected file is empty.'
            };
        }

        return { valid: true };
    }

    /**
     * Get file extension from filename
     */
    getExtension(filename) {
        return filename.split('.').pop().toLowerCase();
    }

    /**
     * Get appropriate icon/emoji for file type
     */
    getFileIcon(ext) {
        const icons = {
            pdf: '📄',
            docx: '📝',
            doc: '📝',
            xlsx: '📊',
            xls: '📊',
            csv: '📑',
            txt: '📃',
            png: '🖼️',
            jpg: '🖼️',
            jpeg: '🖼️',
            tiff: '🖼️',
            tif: '🖼️',
            bmp: '🖼️',
            webp: '🖼️'
        };
        return icons[ext] || '📄';
    }

    /**
     * Start the upload and processing flow
     */
    async startUpload() {
        if (!app.selectedFile) {
            app.showToast('No file selected.', 'warning');
            return;
        }

        this.processBtn.disabled = true;

        // Switch to processing view
        app.showView('processing');
        app.processing.startProcessing(app.selectedFile.name, app.formatFileSize(app.selectedFile.size));

        // Start simulated progress
        app.processing.simulateProgress();

        // Upload file
        try {
            this.abortController = new AbortController();

            const formData = new FormData();
            formData.append('file', app.selectedFile);

            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData,
                signal: this.abortController.signal
            });

            if (!response.ok) {
                let errorMessage = `Upload failed (${response.status})`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch {
                    // ignore parse error
                }
                throw new Error(errorMessage);
            }

            const result = await response.json();
            app.currentResult = result;
            app.currentJobId = result.job_id;

            // Complete processing animation then show results
            await app.processing.completeProcessing();

            // Short delay for the completion animation
            setTimeout(() => {
                app.showView('results');
                app.results.displayResults(result);
                app.showToast('Document processed successfully!', 'success');
            }, 600);

        } catch (error) {
            if (error.name === 'AbortError') {
                app.showToast('Upload cancelled.', 'info');
                app.showView('upload');
            } else {
                console.error('Upload error:', error);
                app.processing.failProcessing(error.message);
                app.showToast(error.message || 'Upload failed. Please try again.', 'error');

                setTimeout(() => {
                    app.showView('upload');
                }, 2000);
            }
        } finally {
            this.processBtn.disabled = false;
            this.abortController = null;
        }
    }

    /**
     * Cancel the current upload
     */
    cancelUpload() {
        if (this.abortController) {
            this.abortController.abort();
        }
    }

    /**
     * Reset to initial state
     */
    reset() {
        app.selectedFile = null;
        this.fileInput.value = '';
        this.fileInfoCard.classList.add('hidden');
        this.processBtn.disabled = false;
    }
}

// Initialize after DOM loaded
document.addEventListener('DOMContentLoaded', () => {
    app.upload = new UploadManager();
});
