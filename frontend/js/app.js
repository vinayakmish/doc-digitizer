/**
 * DocDigitizer — Main Application Controller
 * Manages state, views, toasts, and initializes all modules.
 */

const API_BASE = window.location.origin;

class App {
    constructor() {
        this.currentView = 'upload';
        this.selectedFile = null;
        this.currentJobId = null;
        this.currentResult = null;

        // Module references (set after modules init)
        this.upload = null;
        this.processing = null;
        this.results = null;
    }

    /**
     * Initialize the application
     */
    init() {
        this.setupModalListeners();
        this.checkHealth();

        // Keyboard listener
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });

        // Global error handler
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.showToast('An unexpected error occurred. Please try again.', 'error');
        });

        window.addEventListener('error', (event) => {
            console.error('Unhandled error:', event.error);
        });
    }

    /**
     * Switch between upload / processing / results views with animations
     */
    showView(viewName) {
        const views = document.querySelectorAll('.view');
        views.forEach(view => {
            view.classList.remove('active');
        });

        const target = document.getElementById(`${viewName}-view`);
        if (target) {
            // Small delay to allow the CSS transition to trigger on re-adding
            requestAnimationFrame(() => {
                target.classList.add('active');
                this.currentView = viewName;
                // Scroll to top
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
    }

    /**
     * Show a toast notification
     * @param {string} message 
     * @param {'success'|'error'|'info'|'warning'} type 
     */
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✗',
            warning: '⚠',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${this.escapeHTML(message)}</span>
        `;

        container.appendChild(toast);

        // Auto-remove after 4 seconds
        setTimeout(() => {
            toast.classList.add('removing');
            toast.addEventListener('animationend', () => {
                toast.remove();
            });
        }, 4000);
    }

    /**
     * Set up modal open/close listeners
     */
    setupModalListeners() {
        const formatsBtn = document.getElementById('formats-btn');
        const closeModalBtn = document.getElementById('close-modal-btn');
        const modalOverlay = document.getElementById('formats-modal');

        if (formatsBtn) {
            formatsBtn.addEventListener('click', () => {
                modalOverlay.classList.remove('hidden');
            });
        }

        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', () => {
                this.closeModal();
            });
        }

        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    this.closeModal();
                }
            });
        }
    }

    closeModal() {
        const modal = document.getElementById('formats-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    /**
     * Check API health status
     */
    async checkHealth() {
        const dot = document.getElementById('health-indicator');
        try {
            const response = await fetch(`${API_BASE}/api/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(5000)
            });
            if (response.ok) {
                dot.classList.add('online');
                dot.classList.remove('offline');
                dot.title = 'API Online';
            } else {
                throw new Error('Not OK');
            }
        } catch {
            dot.classList.add('offline');
            dot.classList.remove('online');
            dot.title = 'API Offline';
        }
    }

    /**
     * Format bytes into human-readable file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Format seconds into human-readable duration
     */
    formatDuration(seconds) {
        if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${mins}m ${secs}s`;
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// --- Global app instance ---
const app = new App();

document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
