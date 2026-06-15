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

// ════════════════════════════════════════════════════
// TAB SWITCHING
// ════════════════════════════════════════════════════
function switchTab(tab) {
    state.currentTab = tab;
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === 'tab-' + tab);
    });
    // Lazy load
    if (tab === 'gallery') renderGallery(state.galleryPage);
}

document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => switchTab(el.dataset.tab));
});

// ════════════════════════════════════════════════════
// GALLERY
// ════════════════════════════════════════════════════
async function renderGallery(page) {
    const container = document.getElementById('gallery');
    const pagination = document.getElementById('gallery-pagination');
    container.innerHTML = '<div class="loading">Loading images...</div>';
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
            container.innerHTML = '<div class="empty">No images uploaded yet.</div>';
            pagination.innerHTML = '';
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
                            ? '<span style="color:#2a9d8f;font-weight:600;">✅ Yes</span>'
                            : '<span style="color:#e63946;font-weight:600;">❌ No</span>'}
                    </div>
                    <div class="url"><a href="${img.image_url}" target="_blank">Open S3 URL &rarr;</a></div>
                </div>
            </div>
        `).join('');

        // Pagination controls
        if (data.count !== undefined) {
            renderPagination(pagination);
        }
    } catch (err) {
        container.innerHTML = '<div class="error">Failed to load images. Make sure the API is running.</div>';
        console.error('Load error:', err);
    }
}

function renderPagination(container) {
    const page = state.galleryPage;
    const total = state.totalPages;
    container.innerHTML = `
        <button onclick="goToPage(${page - 1})" ${page <= 1 ? 'disabled' : ''}>&larr; Previous</button>
        <span>Page ${page} of ${total} (${state.totalCount} total)</span>
        <button onclick="goToPage(${page + 1})" ${page >= total ? 'disabled' : ''}>Next &rarr;</button>
    `;
}

window.goToPage = function(page) {
    if (page < 1 || page > state.totalPages) return;
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

    if (!name || !file) {
        msg.innerHTML = '<div class="error">Please provide a name and select an image.</div>';
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('image', file);

    state.uploading = true;
    btn.disabled = true;
    msg.innerHTML = '<div class="loading">Uploading...</div>';

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
        msg.innerHTML = `<div class="success">✅ Uploaded successfully! <a href="${result.image_url}" target="_blank">View image</a></div>`;
        document.getElementById('uploadForm').reset();

        // Update status to vectorizing
        updateStatusItem(tempId, result.id, result.name, result.image_url, 'vectorizing');

        // Poll for vectorized status
        pollVectorization(result.id, tempId);

    } catch (err) {
        updateStatusItem(tempId, null, name, null, 'error');
        msg.innerHTML = `<div class="error">❌ Upload failed: ${err.message}</div>`;
        console.error('Upload error:', err);
    } finally {
        state.uploading = false;
        btn.disabled = false;
    }
});

function addStatusItem(id, name, imageUrl, status) {
    const list = document.getElementById('uploadStatusList');
    const item = document.createElement('div');
    item.className = 'status-item';
    item.id = 'status-' + id;
    item.innerHTML = `
        <img src="${imageUrl || '/placeholder.jpg'}" alt="${escapeHtml(name)}" />
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
        case 'uploaded': return '✅ Uploaded';
        case 'error': return '❌ Failed';
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
    const resultsContainer = document.getElementById('searchResults');

    if (!file) {
        msg.innerHTML = '<div class="error">Please select an image to search with.</div>';
        return;
    }

    const formData = new FormData();
    formData.append('image', file);
    formData.append('limit', '20');

    state.searching = true;
    btn.disabled = true;
    msg.innerHTML = '<div class="loading">Searching for similar images...</div>';
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
        msg.innerHTML = `<div class="success">✅ Found ${data.results.length} similar images</div>`;

        // Show query image
        document.getElementById('queryImagePreview').src = data.query_image_url;
        document.getElementById('queryImagePreview').alt = 'Query Image';

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

    } catch (err) {
        msg.innerHTML = `<div class="error">❌ Search failed: ${err.message}</div>`;
        console.error('Search error:', err);
    } finally {
        state.searching = false;
        btn.disabled = false;
    }
});

// ════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════
renderGallery(1);