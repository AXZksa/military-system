document.addEventListener('DOMContentLoaded', function() {
    initTooltips();
});

function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(el) {
        return new bootstrap.Tooltip(el);
    });
}

function confirmAction(msg) {
    return confirm(msg || 'هل أنت متأكد؟');
}

function showToast(msg, type) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;width:auto;max-width:90%;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'alert alert-' + (type || 'info') + ' alert-dismissible fade show shadow-lg';
    toast.innerHTML = msg + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
    document.getElementById('toastContainer').appendChild(toast);
    setTimeout(function() { toast.remove(); }, 5000);
}
