/**
 * Upload Progress Handler
 * Provides file upload progress indicators for large file uploads
 * Supports both single and multiple file uploads with progress bars
 */

class UploadProgressHandler {
    constructor() {
        this.uploading = false;
        this.progressModal = null;
        this.progressBar = null;
        this.progressText = null;
        this.currentXHR = null;

        this.initializeProgressModal();
        this.bindEventListeners();
    }

    initializeProgressModal() {
        // Create progress modal HTML
        const modalHTML = `
            <div id="upload-progress-modal" class="upload-modal" style="display: none;">
                <div class="upload-modal__backdrop"></div>
                <div class="upload-modal__content">
                    <div class="upload-modal__header">
                        <h3 class="upload-modal__title">📤 Uploading Files</h3>
                        <div class="upload-modal__subtitle">Please wait while your files are being processed...</div>
                    </div>

                    <div class="upload-progress">
                        <div class="upload-progress__bar-container">
                            <div id="upload-progress-bar" class="upload-progress__bar">
                                <div class="upload-progress__fill"></div>
                            </div>
                        </div>

                        <div class="upload-progress__info">
                            <div id="upload-progress-text" class="upload-progress__text">Preparing upload...</div>
                            <div id="upload-progress-percentage" class="upload-progress__percentage">0%</div>
                        </div>

                        <div class="upload-progress__details">
                            <div id="upload-file-info" class="upload-file-info">
                                <span id="current-file">Preparing files...</span>
                            </div>
                            <div id="upload-speed" class="upload-speed"></div>
                        </div>
                    </div>

                    <div class="upload-modal__actions">
                        <button type="button" id="cancel-upload-btn" class="btn btn--outline">Cancel Upload</button>
                    </div>
                </div>
            </div>
        `;

        // Add to document
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Cache elements
        this.progressModal = document.getElementById('upload-progress-modal');
        this.progressBar = document.getElementById('upload-progress-bar');
        this.progressText = document.getElementById('upload-progress-text');
        this.progressPercentage = document.getElementById('upload-progress-percentage');
        this.currentFileElement = document.getElementById('current-file');
        this.uploadSpeedElement = document.getElementById('upload-speed');
        this.cancelButton = document.getElementById('cancel-upload-btn');

        // Bind cancel functionality
        this.cancelButton.addEventListener('click', () => this.cancelUpload());
    }

    bindEventListeners() {
        // Intercept all form submissions with file uploads
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (this.shouldInterceptForm(form)) {
                e.preventDefault();
                this.handleFormSubmission(form);
            }
        });
    }

    shouldInterceptForm(form) {
        // Check if form has file inputs and is an upload form
        if (form.enctype !== 'multipart/form-data') {
            return false;
        }

        const fileInputs = form.querySelectorAll('input[type="file"]');
        if (fileInputs.length === 0) {
            return false;
        }

        // Check if any file inputs have files
        for (const input of fileInputs) {
            if (input.files && input.files.length > 0) {
                // Check total file size
                const totalSize = this.getTotalFileSize(input.files);
                // Show progress for files > 5MB or multiple files
                if (totalSize > 5 * 1024 * 1024 || input.files.length > 1) {
                    return true;
                }
            }
        }

        return false;
    }

    getTotalFileSize(files) {
        let total = 0;
        for (const file of files) {
            total += file.size;
        }
        return total;
    }

    handleFormSubmission(form) {
        if (this.uploading) {
            return; // Already uploading
        }

        this.uploading = true;
        this.showProgressModal();

        // Prepare form data
        const formData = new FormData(form);
        const fileInputs = form.querySelectorAll('input[type="file"]');

        // Get file information for display
        const files = [];
        fileInputs.forEach(input => {
            if (input.files) {
                Array.from(input.files).forEach(file => files.push(file));
            }
        });

        const totalSize = this.getTotalFileSize(files);
        const fileCount = files.length;

        // Update initial display
        this.updateProgress(0, `Preparing ${fileCount} file${fileCount > 1 ? 's' : ''}...`);
        this.currentFileElement.textContent = `${fileCount} file${fileCount > 1 ? 's' : ''} • ${this.formatFileSize(totalSize)}`;

        // Create XHR request
        const xhr = new XMLHttpRequest();
        this.currentXHR = xhr;

        // Track upload progress
        let uploadStartTime = Date.now();
        let lastLoaded = 0;

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentage = Math.round((e.loaded / e.total) * 100);
                const currentTime = Date.now();
                const timeElapsed = (currentTime - uploadStartTime) / 1000; // seconds

                // Calculate speed
                const bytesPerSecond = e.loaded / timeElapsed;
                const speed = this.formatUploadSpeed(bytesPerSecond);

                // Calculate estimated time remaining
                const bytesRemaining = e.total - e.loaded;
                const timeRemaining = bytesRemaining / bytesPerSecond;
                const eta = this.formatTimeRemaining(timeRemaining);

                this.updateProgress(
                    percentage,
                    `Uploading... ${this.formatFileSize(e.loaded)} of ${this.formatFileSize(e.total)}`
                );

                this.uploadSpeedElement.textContent = `${speed} • ${eta} remaining`;

                lastLoaded = e.loaded;
            }
        });

        // Handle completion
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                this.updateProgress(100, 'Upload complete! Processing...');
                this.uploadSpeedElement.textContent = 'Processing files on server...';

                // Simulate processing time
                setTimeout(() => {
                    this.hideProgressModal();

                    // Handle redirect or form response
                    try {
                        // Check if response is JSON first
                        const contentType = xhr.getResponseHeader('content-type');
                        if (contentType && contentType.includes('application/json')) {
                            const response = JSON.parse(xhr.responseText);
                            if (response.redirect) {
                                window.location.href = response.redirect;
                                return;
                            }
                        }

                        // For HTML responses, check if it's a Django redirect by looking at the final URL
                        // XHR will follow redirects automatically, so xhr.responseURL gives us the final destination
                        if (xhr.responseURL && xhr.responseURL !== window.location.href) {
                            // The server redirected us, follow that redirect
                            window.location.href = xhr.responseURL;
                        } else {
                            // No redirect detected, try form action or reload current page
                            const formAction = form.getAttribute('action') || window.location.href;
                            window.location.href = formAction;
                        }
                    } catch (e) {
                        // Fallback: try responseURL first, then form action
                        if (xhr.responseURL && xhr.responseURL !== window.location.href) {
                            window.location.href = xhr.responseURL;
                        } else {
                            const formAction = form.getAttribute('action') || window.location.href;
                            window.location.href = formAction;
                        }
                    }
                }, 1000);
            } else {
                this.handleUploadError('Upload failed. Please try again.');
            }
        });

        // Handle errors
        xhr.addEventListener('error', () => {
            this.handleUploadError('Network error occurred. Please check your connection and try again.');
        });

        xhr.addEventListener('abort', () => {
            this.hideProgressModal();
        });

        // Send request - use getAttribute to avoid conflict with form elements named "action"
        const formAction = form.getAttribute('action') || window.location.href;
        xhr.open('POST', formAction);
        xhr.send(formData);
    }

    updateProgress(percentage, message) {
        if (this.progressBar) {
            const fill = this.progressBar.querySelector('.upload-progress__fill');
            fill.style.width = `${percentage}%`;
        }

        if (this.progressText) {
            this.progressText.textContent = message;
        }

        if (this.progressPercentage) {
            this.progressPercentage.textContent = `${percentage}%`;
        }
    }

    showProgressModal() {
        if (this.progressModal) {
            this.progressModal.style.display = 'flex';
            document.body.classList.add('upload-modal-open');

            // Reset progress
            this.updateProgress(0, 'Preparing upload...');
            this.uploadSpeedElement.textContent = '';
        }
    }

    hideProgressModal() {
        if (this.progressModal) {
            this.progressModal.style.display = 'none';
            document.body.classList.remove('upload-modal-open');
            this.uploading = false;
            this.currentXHR = null;
        }
    }

    cancelUpload() {
        if (this.currentXHR) {
            this.currentXHR.abort();
            this.currentXHR = null;
        }
        this.hideProgressModal();
    }

    handleUploadError(message) {
        this.updateProgress(0, message);
        this.uploadSpeedElement.textContent = '';
        this.cancelButton.textContent = 'Close';

        // Auto-hide after delay
        setTimeout(() => {
            this.hideProgressModal();
            this.cancelButton.textContent = 'Cancel Upload';
        }, 3000);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';

        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatUploadSpeed(bytesPerSecond) {
        return this.formatFileSize(bytesPerSecond) + '/s';
    }

    formatTimeRemaining(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.round(seconds % 60);
            return `${minutes}m ${remainingSeconds}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on a page with file upload forms
    const fileInputs = document.querySelectorAll('input[type="file"]');
    if (fileInputs.length > 0) {
        new UploadProgressHandler();
    }
});

// Export for use in other scripts
window.UploadProgressHandler = UploadProgressHandler;