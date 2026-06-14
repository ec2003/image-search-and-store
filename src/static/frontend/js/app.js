// Configure API base URL
const API_BASE = window.location.origin + '/api/v1';

// Fetch and display all images
async function loadGallery() {
    const gallery = document.getElementById('gallery');
    try {
        const res = await fetch(`${API_BASE}/images/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const images = await res.json();

        if (images.length === 0) {
            gallery.innerHTML = '<div class="empty">No images uploaded yet.</div>';
            return;
        }

        gallery.innerHTML = images.map(img => `
            <div class="gallery-item">
                <img src="${img.image_url || '/placeholder.jpg'}" alt="${img.name}" loading="lazy" />
                <div class="info">
                    <div class="name">${escapeHtml(img.name)}</div>
                    <div class="meta">${new Date(img.uploaded_at).toLocaleString()} &middot; ${formatBytes(img.file_size)}</div>
                    <div class="url"><a href="${img.image_url}" target="_blank">Open S3 URL &rarr;</a></div>
                </div>
            </div>
        `).join('');
    } catch (err) {
        gallery.innerHTML = '<div class="error">Failed to load images. Make sure the API is running.</div>';
        console.error('Load error:', err);
    }
}

// Upload an image
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('name').value.trim();
    const fileInput = document.getElementById('image');
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

    btn.disabled = true;
    msg.innerHTML = '<div class="loading">Uploading...</div>';

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
        loadGallery();
    } catch (err) {
        msg.innerHTML = `<div class="error">❌ Upload failed: ${err.message}</div>`;
        console.error('Upload error:', err);
    } finally {
        btn.disabled = false;
    }
});

// Helpers
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (!bytes) return 'Unknown';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// Initial load
loadGallery();