/**
 * DocDigitizer — Processing Manager
 * Handles processing stage animations and progress simulation.
 */

class ProcessingManager {
    constructor() {
        this.stages = ['detection', 'preprocessing', 'extraction', 'analysis', 'output'];
        this.currentStageIndex = -1;
        this.simulationTimer = null;
        this.isComplete = false;
        this.isFailed = false;

        this.cancelBtn = document.getElementById('cancel-btn');
        this.statusBadge = document.getElementById('processing-status-badge');
        this.fileNameEl = document.getElementById('processing-file-name');
        this.fileSizeEl = document.getElementById('processing-file-size');
        this.fileIconEl = document.getElementById('processing-file-icon');

        this.init();
    }

    init() {
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => {
                this.cancelProcessing();
            });
        }
    }

    /**
     * Start the processing view
     */
    startProcessing(filename, fileSize) {
        this.isComplete = false;
        this.isFailed = false;
        this.currentStageIndex = -1;

        // Update file info
        if (this.fileNameEl) this.fileNameEl.textContent = filename;
        if (this.fileSizeEl) this.fileSizeEl.textContent = fileSize;

        // Determine file icon
        const ext = filename.split('.').pop().toLowerCase();
        if (this.fileIconEl) {
            this.fileIconEl.textContent = app.upload ? app.upload.getFileIcon(ext) : '📄';
        }

        // Reset status badge
        if (this.statusBadge) {
            this.statusBadge.textContent = 'Processing...';
            this.statusBadge.className = 'processing-status-badge';
        }

        // Reset all stages to pending
        this.stages.forEach(stage => {
            this.setStageStatus(stage, 'pending');
        });
    }

    /**
     * Set stage status: pending | active | complete | error
     */
    setStageStatus(stage, status) {
        const stageEl = document.querySelector(`.stage[data-stage="${stage}"]`);
        if (stageEl) {
            stageEl.setAttribute('data-status', status);
        }
    }

    /**
     * Simulate progress through stages while waiting for the API response.
     * We advance one stage every ~800ms but stop before the last stage
     * so we can complete it when the real result arrives.
     */
    simulateProgress() {
        this.currentStageIndex = 0;
        this.setStageStatus(this.stages[0], 'active');

        const advance = () => {
            if (this.isComplete || this.isFailed) return;

            // Complete current stage
            if (this.currentStageIndex >= 0 && this.currentStageIndex < this.stages.length) {
                this.setStageStatus(this.stages[this.currentStageIndex], 'complete');
            }

            this.currentStageIndex++;

            // Don't go past the second-to-last stage during simulation
            if (this.currentStageIndex >= this.stages.length - 1) {
                // Set last stage to active and wait for actual completion
                this.setStageStatus(this.stages[this.stages.length - 1], 'active');
                return;
            }

            // Activate next stage
            this.setStageStatus(this.stages[this.currentStageIndex], 'active');

            // Schedule next advancement with slight randomness
            const delay = 600 + Math.random() * 600;
            this.simulationTimer = setTimeout(advance, delay);
        };

        // Start first advancement
        const initialDelay = 500 + Math.random() * 400;
        this.simulationTimer = setTimeout(advance, initialDelay);
    }

    /**
     * Mark all stages as complete
     */
    async completeProcessing() {
        this.isComplete = true;

        if (this.simulationTimer) {
            clearTimeout(this.simulationTimer);
            this.simulationTimer = null;
        }

        // Complete all remaining stages with staggered timing
        for (let i = 0; i < this.stages.length; i++) {
            const stageEl = document.querySelector(`.stage[data-stage="${this.stages[i]}"]`);
            const currentStatus = stageEl?.getAttribute('data-status');
            if (currentStatus !== 'complete') {
                this.setStageStatus(this.stages[i], 'complete');
                await this.delay(150);
            }
        }

        // Update status badge
        if (this.statusBadge) {
            this.statusBadge.textContent = 'Complete!';
            this.statusBadge.classList.add('complete');
        }
    }

    /**
     * Show error state
     */
    failProcessing(errorMessage) {
        this.isFailed = true;

        if (this.simulationTimer) {
            clearTimeout(this.simulationTimer);
            this.simulationTimer = null;
        }

        // Mark current active stage as error
        if (this.currentStageIndex >= 0 && this.currentStageIndex < this.stages.length) {
            this.setStageStatus(this.stages[this.currentStageIndex], 'error');
        }

        // Update status badge
        if (this.statusBadge) {
            this.statusBadge.textContent = 'Failed';
            this.statusBadge.className = 'processing-status-badge error';
        }
    }

    /**
     * Cancel processing
     */
    cancelProcessing() {
        if (app.upload) {
            app.upload.cancelUpload();
        }
        this.isFailed = true;
        if (this.simulationTimer) {
            clearTimeout(this.simulationTimer);
            this.simulationTimer = null;
        }
    }

    /**
     * Promise-based delay helper
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize after DOM loaded
document.addEventListener('DOMContentLoaded', () => {
    app.processing = new ProcessingManager();
});
