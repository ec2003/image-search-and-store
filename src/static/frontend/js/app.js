// ─── Configuration ──────────────────────────────────
const API_BASE = window.location.origin + '/api/v1';

// ─── State ──────────────────────────────────────────
const state = {
    currentTab: 'gallery',
    galleryPage: 1,
    totalPages: 1,
    totalCount: 0,
    uploading: false,
    searching: false,
};

// ─── Helpers ────────────────────────────────────────
function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

function formatBytes(bytes) {
    if (!bytes) return 'Unknown';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString();
}

function scoreClass(score) {
    if (score >= 0.85) return 'score-high';
    if (score >= 0.6) return 'score-mid';
    return 'score-low';
}

function showMessage(container, type, text) {
    container.style.display = 'block';
    container.className = 'message-box ' + type;
    container.textContent = text;
}

function hideMessage(container) {
    container.style.display = 'none';
    container.className = 'message-box';
    container.textContent = '';
}

function showLoading(container, text) {
    container.style.display = 'block';
    container.className = 'message-box';
    container.innerHTML = '<div class="loading" style="padding:0;">' + (text || 'Loading...') + '</div>';
}

// ════════════════════════════════════════════════════
// TAB SWITCHING
// ════════════════════════════════════════════════════
function switchTab(tab) {
    if (state.currentTab === tab) return;
    state.currentTab = tab;

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(el => {
        const isActive = el.dataset.tab === tab;
        el.classList.toggle('active', isActive);
        el.setAttribute('aria-selected', isActive ? 'true' : 'false');
        el.setAttribute('tabindex', isActive ? '0' : '-1');
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === 'tab-' + tab);
    });

    // Lazy load
    if (tab === 'gallery') renderGallery(state.galleryPage);
    if (tab === 'upload') document.getElementById('up-name').focus();
}

// Keyboard navigation for tabs
document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => switchTab(el.dataset.tab));

    el.addEventListener('keydown', (e) => {
        const items = Array.from(document.querySelectorAll('.nav-item'));
        const idx = items.indexOf(el);

        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
            e.preventDefault();
            const next = items[(idx + 1) % items.length];
            next.focus();
            switchTab(next.dataset.tab);
        }
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
            e.preventDefault();
            const prev = items[(idx - 1 + items.length) % items.length];
            prev.focus();
            switchTab(prev.dataset.tab);
        }
        if (e.key === 'Home') {
            e.preventDefault();
            items[0].focus();
            switchTab(items[0].dataset.tab);
        }
        if (e.key === 'End') {
            e.preventDefault();
            items[items.length - 1].focus();
            switchTab(items[items.length - 1].dataset.tab);
        }
    });
});

// ════════════════════════════════════════════════════
// GALLERY
// ════════════════════════════════════════════════════
async function renderGallery(page) {
    const container = document.getElementById('gallery');
    const skeleton = document.getElementById('gallery-skeleton');
    const pagination = document.getElementById('gallery-pagination');

    // Show skeleton, hide gallery + pagination
    skeleton.style.display = 'grid';
    container.style.display = 'none';
    container.innerHTML = '';
    pagination.style.display = 'none';
    pagination.innerHTML = '';

    try {
        const res = await fetch(`${API_BASE}/images/?page=${page}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        state.galleryPage = page;
        state.totalCount = data.count || 0;
        state.totalPages = Math.max(1, Math.ceil((data.count || 0) / (data.results?.length || 1)));

        const images = data.results || data;
        if (!images || images.length === 0) {
            skeleton.style.display = 'none';
            container.style.display = 'block';
            container.innerHTML = '<div class="empty">No images uploaded yet. Try uploading one!</div>';
            pagination.style.display = 'none';
            return;
        }

        container.innerHTML = images.map(img => `
            <div class="gallery-item">
                <img src="${img.image_url || '/placeholder.jpg'}" alt="${escapeHtml(img.name)}" loading="lazy" />
                <div class="info">
                    <div class="name">${escapeHtml(img.name)}</div>
                    <div class="meta">${formatDate(img.uploaded_at)} &middot; ${formatBytes(img.file_size)}</div>
                    <div class="meta">
                        Vector: ${img.vectorized
                            ? '<span class="vector-badge" style="color:#3a9d7a;font-weight:600;">Embedded</span>'
                            : '<span class="vector-badge" style="color:#c4943a;font-weight:600;">Pending</span>'}
                    </div>
                    <div class="url"><a href="${img.image_url}" target="_blank" rel="noopener">Open original &rarr;</a></div>
                </div>
            </div>
        `).join('');

        // Hide skeleton, show gallery
        skeleton.style.display = 'none';
        container.style.display = 'grid';

        // Pagination controls
        if (data.count !== undefined) {
            renderPagination(pagination);
            pagination.style.display = 'flex';
        }
    } catch (err) {
        skeleton.style.display = 'none';
        container.style.display = 'block';
        container.innerHTML = '<div class="empty" style="color:var(--error);">Failed to load images. Make sure the API is running.</div>';
        console.error('Load error:', err);
    }
}

function renderPagination(container) {
    const page = state.galleryPage;
    const total = state.totalPages;
    container.innerHTML = `
        <button onclick="goToPage(${page - 1})" ${page <= 1 ? 'disabled' : ''} aria-label="Previous page">&larr; Previous</button>
        <span>Page ${page} of ${total} <span style="color:var(--text-tertiary);font-weight:400;">(${state.totalCount} total)</span></span>
        <button onclick="goToPage(${page + 1})" ${page >= total ? 'disabled' : ''} aria-label="Next page">Next &rarr;</button>
    `;
}

window.goToPage = function(page) {
    if (page < 1 || page > state.totalPages) return;
    // Scroll to top of gallery
    document.getElementById('tab-gallery').scrollIntoView({ behavior: 'smooth', block: 'start' });
    renderGallery(page);
};

// ════════════════════════════════════════════════════
// UPLOAD
// ════════════════════════════════════════════════════
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (state.uploading) return;

    const name = document.getElementById('up-name').value.trim();
    const fileInput = document.getElementById('up-image');
    const file = fileInput.files[0];
    const msg = document.getElementById('uploadMessage');
    const btn = document.getElementById('uploadBtn');
    const btnText = btn.querySelector('.btn-text');

    // Client-side validation
    if (!name) {
        showMessage(msg, 'error', 'Please provide a name for the image.');
        document.getElementById('up-name').focus();
        return;
    }
    if (!file) {
        showMessage(msg, 'error', 'Please select an image to upload.');
        fileInput.focus();
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showMessage(msg, 'error', 'File is too large. Maximum size is 50 MB.');
        return;
    }

    hideMessage(msg);

    const formData = new FormData();
    formData.append('name', name);
    formData.append('image', file);

    state.uploading = true;
    btn.disabled = true;
    btnText.textContent = 'Uploading...';

    // Add a pending status item immediately
    const tempId = 'temp-' + Date.now();
    addStatusItem(tempId, file.name, null, 'pending');

    try {
        const res = await fetch(`${API_BASE}/images/upload/`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || JSON.stringify(errData));
        }
        const result = await res.json();
        showMessage(msg, 'success', 'Uploaded successfully');
        document.getElementById('uploadForm').reset();

        // Update status to vectorizing
        updateStatusItem(tempId, result.id, result.name, result.image_url, 'vectorizing');

        // Poll for vectorized status
        pollVectorization(result.id, tempId);

    } catch (err) {
        updateStatusItem(tempId, null, name, null, 'error');
        showMessage(msg, 'error', 'Upload failed: ' + err.message);
        console.error('Upload error:', err);
    } finally {
        state.uploading = false;
        btn.disabled = false;
        btnText.textContent = 'Upload';
    }
});

function addStatusItem(id, name, imageUrl, status) {
    const list = document.getElementById('uploadStatusList');
    const item = document.createElement('div');
    item.className = 'status-item';
    item.id = 'status-' + id;
    item.innerHTML = `
        <img src="${imageUrl || '/placeholder.jpg'}" alt="${escapeHtml(name)}" loading="lazy" />
        <div class="info">
            <div class="name">${escapeHtml(name)}</div>
            <div class="meta">${id.startsWith('temp-') ? 'Just now' : ''}</div>
        </div>
        <span class="badge badge-${status}">${statusLabel(status)}</span>
    `;
    list.prepend(item);
}

function updateStatusItem(tempId, realId, name, imageUrl, status) {
    const el = document.getElementById('status-' + tempId);
    if (!el) return;
    if (name) el.querySelector('.name').textContent = name;
    if (imageUrl) el.querySelector('img').src = imageUrl;
    const badge = el.querySelector('.badge');
    badge.className = 'badge badge-' + status;
    badge.textContent = statusLabel(status);
    // If vectorizing, show animated dots
    if (status === 'vectorizing') {
        let dots = 0;
        badge._animInterval = setInterval(() => {
            dots = (dots + 1) % 4;
            badge.textContent = 'Vectorizing' + '.'.repeat(dots);
        }, 500);
    } else if (badge._animInterval) {
        clearInterval(badge._animInterval);
    }
}

function statusLabel(status) {
    switch (status) {
        case 'pending': return 'Pending';
        case 'vectorizing': return 'Vectorizing...';
        case 'uploaded': return 'Uploaded';
        case 'error': return 'Failed';
        default: return status;
    }
}

async function pollVectorization(imageId, tempId) {
    const maxAttempts = 30;  // 30 * 2s = 60s timeout
    let attempts = 0;

    const poll = async () => {
        if (attempts >= maxAttempts) {
            updateStatusItem(tempId, imageId, null, null, 'error');
            return;
        }
        attempts++;
        try {
            const res = await fetch(`${API_BASE}/images/${imageId}/`);
            if (!res.ok) throw new Error('Not found');
            const data = await res.json();
            if (data.vectorized) {
                updateStatusItem(tempId, imageId, data.name, data.image_url, 'uploaded');
                return;  // Done
            }
            // Still vectorizing
            setTimeout(poll, 2000);
        } catch {
            // Server may still be processing
            setTimeout(poll, 2000);
        }
    };
    setTimeout(poll, 2000);
}

// ════════════════════════════════════════════════════
// SEARCH
// ════════════════════════════════════════════════════
document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (state.searching) return;

    const fileInput = document.getElementById('sr-image');
    const file = fileInput.files[0];
    const msg = document.getElementById('searchMessage');
    const btn = document.getElementById('searchBtn');
    const btnText = btn.querySelector('.btn-text');
    const resultsContainer = document.getElementById('searchResults');

    if (!file) {
        showMessage(msg, 'error', 'Please select an image to search with.');
        fileInput.focus();
        return;
    }

    hideMessage(msg);

    const formData = new FormData();
    formData.append('image', file);
    formData.append('limit', '20');

    state.searching = true;
    btn.disabled = true;
    btnText.textContent = 'Searching...';
    resultsContainer.style.display = 'none';

    try {
        const res = await fetch(`${API_BASE}/images/search/`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || errData.error || JSON.stringify(errData));
        }
        const data = await res.json();
        showMessage(msg, 'success', 'Found ' + data.results.length + ' similar images');

        // Show query image
        document.getElementById('queryImagePreview').src = data.query_image_url;
        document.getElementById('queryImagePreview').alt = 'Query image';

        // Show results
        const grid = document.getElementById('resultsGrid');
        if (data.results.length === 0) {
            grid.innerHTML = '<div class="empty">No similar images found.</div>';
        } else {
            grid.innerHTML = data.results.map(r => `
                <div class="result-item">
                    <img src="${r.image_url || '/placeholder.jpg'}" alt="${escapeHtml(r.name)}" loading="lazy" />
                    <div class="info">
                        <div class="name">${escapeHtml(r.name)}</div>
                        <div class="meta">${formatDate(r.uploaded_at)}</div>
                        <div class="meta">
                            <span class="score-badge ${scoreClass(r.score)}">${(r.score * 100).toFixed(1)}% match</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        resultsContainer.style.display = 'block';
        // Scroll to results
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        showMessage(msg, 'error', 'Search failed: ' + err.message);
        console.error('Search error:', err);
    } finally {
        state.searching = false;
        btn.disabled = false;
        btnText.textContent = 'Search';
    }
});

// ════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════
renderGallery(1);