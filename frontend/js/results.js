/**
 * DocDigitizer — Results Manager
 * Handles rendering extraction results across all tabs.
 */

class ResultsManager {
    constructor() {
        this.tabs = document.querySelectorAll('.tab-bar .tab');
        this.panels = document.querySelectorAll('.tab-panel');
        this.result = null;

        this.init();
    }

    init() {
        // Tab switching
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });

        // Download buttons
        document.getElementById('download-json-btn')?.addEventListener('click', () => {
            if (this.result) this.downloadJSON(this.result);
        });

        document.getElementById('download-csv-btn')?.addEventListener('click', () => {
            if (this.result) this.downloadCSV(this.result);
        });

        // Process another
        document.getElementById('process-another-btn')?.addEventListener('click', () => {
            this.processAnother();
        });
    }

    /**
     * Switch active tab
     */
    switchTab(tabName) {
        // Update tab buttons
        this.tabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update panels
        this.panels.forEach(panel => {
            const panelTab = panel.id.replace('panel-', '');
            panel.classList.toggle('active', panelTab === tabName);
        });
    }

    /**
     * Display all results from an ExtractionResult
     */
    displayResults(result) {
        this.result = result;

        // Update results header
        this.updateHeader(result);

        // Render all tab contents
        this.renderSummary(result);
        this.renderKeyValuePairs(result.key_value_pairs || []);
        this.renderTables(result.tables || []);
        this.renderEntities(result.entities || []);
        this.renderRawText(result.raw_text || '');
        this.renderJSON(result);

        // Default to summary tab
        this.switchTab('summary');
    }

    /**
     * Update the results header with metadata
     */
    updateHeader(result) {
        const docTypeEl = document.getElementById('result-doc-type');
        const pagesEl = document.getElementById('result-pages');
        const timeEl = document.getElementById('result-time');
        const confBarEl = document.getElementById('result-confidence-bar');
        const confTextEl = document.getElementById('result-confidence-text');

        if (docTypeEl) docTypeEl.textContent = result.document_type || 'Unknown';
        if (pagesEl) pagesEl.textContent = result.pages_processed || 0;
        if (timeEl) timeEl.textContent = app.formatDuration(result.processing_time_seconds || 0);

        // Calculate average confidence
        const allConfidences = [
            ...(result.key_value_pairs || []).map(kv => kv.confidence || 0),
            ...(result.entities || []).map(e => e.confidence || 0)
        ];
        const avgConf = allConfidences.length > 0
            ? allConfidences.reduce((a, b) => a + b, 0) / allConfidences.length
            : 0;
        const confPct = Math.round(avgConf * 100);

        if (confBarEl) {
            setTimeout(() => {
                confBarEl.style.width = `${confPct}%`;
            }, 200);
        }
        if (confTextEl) confTextEl.textContent = `${confPct}%`;
    }

    /* ==========================
       Summary Tab
    ========================== */
    renderSummary(result) {
        const panel = document.getElementById('panel-summary');
        if (!panel) return;

        const summary = result.summary || 'No summary available for this document.';
        const metadata = result.metadata || {};

        let metadataCardsHTML = '';
        const metaItems = [
            { label: 'Document Type', value: result.document_type || 'N/A', icon: '📋' },
            { label: 'Category', value: result.category || 'N/A', icon: '📁' },
            { label: 'Pages', value: result.pages_processed || 0, icon: '📄' },
            { label: 'Processing Time', value: app.formatDuration(result.processing_time_seconds || 0), icon: '⏱️' },
            { label: 'Language', value: (metadata.language || 'N/A').toUpperCase(), icon: '🌐' },
            { label: 'Job ID', value: (result.job_id || 'N/A').substring(0, 8) + '...', icon: '🔑' }
        ];

        metaItems.forEach(item => {
            metadataCardsHTML += `
                <div class="metadata-card">
                    <div class="metadata-card-label">${item.icon} ${this.escapeHTML(item.label)}</div>
                    <div class="metadata-card-value">${this.escapeHTML(String(item.value))}</div>
                </div>
            `;
        });

        panel.innerHTML = `
            <div class="summary-text">${this.escapeHTML(summary)}</div>
            <div class="metadata-cards">${metadataCardsHTML}</div>
        `;
    }

    /* ==========================
       Key-Value Pairs Tab
    ========================== */
    renderKeyValuePairs(pairs) {
        const panel = document.getElementById('panel-key-values');
        if (!panel) return;

        if (!pairs || pairs.length === 0) {
            panel.innerHTML = this.emptyState('🔑', 'No key-value pairs extracted');
            return;
        }

        let cardsHTML = '';
        pairs.forEach(pair => {
            const confidence = pair.confidence || 0;
            const confPct = Math.round(confidence * 100);
            let confClass = 'high';
            if (confPct < 70) confClass = 'low';
            else if (confPct < 90) confClass = 'medium';

            cardsHTML += `
                <div class="kv-card">
                    <div class="kv-key">${this.escapeHTML(pair.key)}</div>
                    <div class="kv-value">${this.escapeHTML(pair.value)}</div>
                    <div class="kv-confidence">
                        <div class="kv-confidence-bar">
                            <div class="kv-confidence-fill ${confClass}" style="width: ${confPct}%"></div>
                        </div>
                        <span class="kv-confidence-text">${confPct}%</span>
                    </div>
                </div>
            `;
        });

        panel.innerHTML = `<div class="kv-grid">${cardsHTML}</div>`;
    }

    /* ==========================
       Tables Tab
    ========================== */
    renderTables(tables) {
        const panel = document.getElementById('panel-tables');
        if (!panel) return;

        if (!tables || tables.length === 0) {
            panel.innerHTML = this.emptyState('📊', 'No tables extracted');
            return;
        }

        let tablesHTML = '';
        tables.forEach((table, index) => {
            const title = table.title || `Table ${index + 1}`;
            const headers = table.headers || [];
            const rows = table.rows || [];

            let headersHTML = '';
            headers.forEach(h => {
                headersHTML += `<th>${this.escapeHTML(h)}</th>`;
            });

            let rowsHTML = '';
            rows.forEach(row => {
                let cellsHTML = '';
                // Handle rows being arrays
                const cells = Array.isArray(row) ? row : Object.values(row);
                cells.forEach(cell => {
                    cellsHTML += `<td>${this.escapeHTML(String(cell))}</td>`;
                });
                // Pad if fewer cells than headers
                for (let i = cells.length; i < headers.length; i++) {
                    cellsHTML += `<td></td>`;
                }
                rowsHTML += `<tr>${cellsHTML}</tr>`;
            });

            tablesHTML += `
                <div class="table-section">
                    <h3 class="table-title">${this.escapeHTML(title)}</h3>
                    <div class="data-table-wrapper">
                        <table class="data-table">
                            <thead><tr>${headersHTML}</tr></thead>
                            <tbody>${rowsHTML}</tbody>
                        </table>
                    </div>
                </div>
            `;
        });

        panel.innerHTML = tablesHTML;
    }

    /* ==========================
       Entities Tab
    ========================== */
    renderEntities(entities) {
        const panel = document.getElementById('panel-entities');
        if (!panel) return;

        if (!entities || entities.length === 0) {
            panel.innerHTML = this.emptyState('🏷️', 'No entities extracted');
            return;
        }

        // Group by entity_type
        const groups = {};
        entities.forEach(entity => {
            const type = (entity.entity_type || 'OTHER').toUpperCase();
            if (!groups[type]) groups[type] = [];
            groups[type].push(entity);
        });

        let groupsHTML = '';
        const sortedTypes = Object.keys(groups).sort();

        sortedTypes.forEach(type => {
            const items = groups[type];
            let chipsHTML = '';

            items.forEach(entity => {
                const confPct = Math.round((entity.confidence || 0) * 100);
                chipsHTML += `
                    <span class="entity-chip" data-type="${this.escapeHTML(type)}" title="Confidence: ${confPct}%">
                        ${this.escapeHTML(entity.value)}
                        <span class="entity-conf">${confPct}%</span>
                    </span>
                `;
            });

            groupsHTML += `
                <div class="entity-group">
                    <div class="entity-group-title">
                        ${this.escapeHTML(type)}
                        <span class="entity-count">${items.length}</span>
                    </div>
                    <div class="entity-chips">${chipsHTML}</div>
                </div>
            `;
        });

        panel.innerHTML = groupsHTML;
    }

    /* ==========================
       Raw Text Tab
    ========================== */
    renderRawText(text) {
        const panel = document.getElementById('panel-raw-text');
        if (!panel) return;

        if (!text || text.trim().length === 0) {
            panel.innerHTML = this.emptyState('📝', 'No raw text extracted');
            return;
        }

        panel.innerHTML = `
            <div class="raw-text-container">
                <button class="copy-btn" id="copy-raw-text-btn" type="button">Copy</button>
                <pre class="raw-text-block">${this.escapeHTML(text)}</pre>
            </div>
        `;

        document.getElementById('copy-raw-text-btn')?.addEventListener('click', () => {
            this.copyToClipboard(text, 'copy-raw-text-btn');
        });
    }

    /* ==========================
       JSON Tab
    ========================== */
    renderJSON(result) {
        const panel = document.getElementById('panel-json');
        if (!panel) return;

        const jsonStr = JSON.stringify(result, null, 2);
        const highlighted = this.syntaxHighlight(jsonStr);

        panel.innerHTML = `
            <div class="json-container">
                <button class="copy-btn" id="copy-json-btn" type="button">Copy</button>
                <pre class="json-block">${highlighted}</pre>
            </div>
        `;

        document.getElementById('copy-json-btn')?.addEventListener('click', () => {
            this.copyToClipboard(jsonStr, 'copy-json-btn');
        });

        // Set up collapsible sections
        this.setupCollapsible(panel);
    }

    /**
     * Syntax highlight JSON string
     */
    syntaxHighlight(json) {
        // Escape HTML first
        let escaped = json
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Apply syntax highlighting
        return escaped.replace(
            /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            (match) => {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'json-key';
                        // Remove the trailing colon from the span content, add it outside
                        return `<span class="${cls}">${match.slice(0, -1)}</span>:`;
                    } else {
                        cls = 'json-string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
    }

    /**
     * Set up collapsible JSON sections
     */
    setupCollapsible(container) {
        const jsonBlock = container.querySelector('.json-block');
        if (!jsonBlock) return;

        // Add click handlers for opening/closing brackets
        jsonBlock.addEventListener('click', (e) => {
            const toggle = e.target.closest('.json-toggle');
            if (toggle) {
                toggle.classList.toggle('collapsed');
            }
        });
    }

    /* ==========================
       Downloads
    ========================== */
    downloadJSON(result) {
        const jsonStr = JSON.stringify(result, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const filename = (result.filename || 'result').replace(/\.[^.]+$/, '') + '_extracted.json';
        this.downloadBlob(blob, filename);
        app.showToast('JSON downloaded!', 'success');
    }

    downloadCSV(result) {
        let csvContent = 'key,value\n';

        // Key-Value pairs as clean key,value rows
        if (result.key_value_pairs && result.key_value_pairs.length > 0) {
            result.key_value_pairs.forEach(kv => {
                csvContent += `${this.csvEscape(kv.key)},${this.csvEscape(kv.value)}\n`;
            });
        }

        // If no KV pairs, try entities as key,value
        else if (result.entities && result.entities.length > 0) {
            result.entities.forEach(e => {
                csvContent += `${this.csvEscape(e.entity_type)},${this.csvEscape(e.value)}\n`;
            });
        }

        // If no KV pairs or entities, convert tables to key,value
        else if (result.tables && result.tables.length > 0) {
            result.tables.forEach(table => {
                const headers = table.headers || [];
                (table.rows || []).forEach(row => {
                    const cells = Array.isArray(row) ? row : Object.values(row);
                    headers.forEach((header, idx) => {
                        const value = idx < cells.length ? String(cells[idx]) : '';
                        if (header.trim() && value.trim()) {
                            csvContent += `${this.csvEscape(header)},${this.csvEscape(value)}\n`;
                        }
                    });
                });
            });
        }

        if (csvContent.trim() === 'key,value') {
            app.showToast('No data available for CSV export.', 'warning');
            return;
        }

        const blob = new Blob([csvContent], { type: 'text/csv' });
        const filename = (result.filename || 'result').replace(/\.[^.]+$/, '') + '_extracted.csv';
        this.downloadBlob(blob, filename);
        app.showToast('CSV downloaded!', 'success');
    }

    /**
     * Trigger file download from a Blob
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Escape value for CSV
     */
    csvEscape(str) {
        if (!str) return '';
        return str.replace(/"/g, '""');
    }

    /* ==========================
       Utilities
    ========================== */

    /**
     * Copy text to clipboard with visual feedback
     */
    async copyToClipboard(text, buttonId) {
        try {
            await navigator.clipboard.writeText(text);
            const btn = document.getElementById(buttonId);
            if (btn) {
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.classList.remove('copied');
                }, 2000);
            }
            app.showToast('Copied to clipboard!', 'success');
        } catch {
            app.showToast('Failed to copy to clipboard.', 'error');
        }
    }

    /**
     * Escape HTML
     */
    escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Generate empty state HTML
     */
    emptyState(icon, text) {
        return `
            <div class="empty-state">
                <div class="empty-state-icon">${icon}</div>
                <p class="empty-state-text">${this.escapeHTML(text)}</p>
            </div>
        `;
    }

    /**
     * Go back to upload view for another document
     */
    processAnother() {
        this.result = null;
        app.currentResult = null;
        app.currentJobId = null;

        if (app.upload) {
            app.upload.reset();
        }

        app.showView('upload');
    }
}

// Initialize after DOM loaded
document.addEventListener('DOMContentLoaded', () => {
    app.results = new ResultsManager();
});
