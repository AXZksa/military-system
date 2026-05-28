document.addEventListener('DOMContentLoaded', function() {
    initTooltips();
    initGeolocation();
});

function initTooltips() {
    [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')).map(function(el) {
        return new bootstrap.Tooltip(el);
    });
}

function confirmAction(msg) { return confirm(msg || 'هل أنت متأكد؟'); }

function showToast(msg, type) {
    var c = document.getElementById('toastContainer');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toastContainer';
        c.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;width:auto;max-width:90%;';
        document.body.appendChild(c);
    }
    var t = document.createElement('div');
    t.className = 'alert alert-' + (type || 'info') + ' alert-dismissible fade show shadow-lg d-flex align-items-center gap-2';
    var icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    else if (type === 'danger') icon = 'x-circle';
    else if (type === 'warning') icon = 'exclamation-triangle';
    t.innerHTML = '<i class="bi bi-' + icon + ' fs-5"></i><span>' + msg + '</span><button type="button" class="btn-close me-auto" data-bs-dismiss="alert"></button>';
    c.appendChild(t);
    setTimeout(function() { if (t.parentNode) t.remove(); }, 5000);
}

function doAttendance(action, note) {
    var btn = document.querySelector('[data-action="' + action + '"], .btn-checkin');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm ms-2"></span> جاري التحميل...';
    }
    if (!navigator.geolocation) {
        showToast('الرجاء تفعيل خدمة الموقع في جهازك', 'danger');
        if (btn) { btn.disabled = false; btn.innerHTML = action === 'check_in' ? 'تسجيل الحضور' : 'تسجيل الانصراف'; }
        return;
    }
    navigator.geolocation.getCurrentPosition(
        function(pos) {
            fetch(action === 'check_in' ? '/employee/check-in' : '/employee/check-out', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, note: note || '' })
            })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.ok) { showToast(res.msg, 'success'); setTimeout(function() { location.reload(); }, 1200); }
                else { showToast(res.msg, 'danger'); if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); } }
            })
            .catch(function(err) {
                showToast('فشل الاتصال بالخادم', 'danger');
                if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
            });
        },
        function(err) {
            var msgs = { 1: 'تم رفض طلب الموقع.', 2: 'تعذر تحديد الموقع. تأكد من GPS.', 3: 'انتهت مهلة طلب الموقع.' };
            showToast(msgs[err.code] || 'خطأ في تحديد الموقع', 'danger');
            if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

function originalText(btn, action) {
    return action === 'check_in' ? 'تسجيل الحضور' : 'تسجيل الانصراف';
}

function initGeolocation() {
    var btns = document.querySelectorAll('[data-action="check_in"], [data-action="check_out"]');
    btns.forEach(function(b) {
        b.addEventListener('click', function(e) {
            e.preventDefault();
            var action = this.dataset.action;
            var noteInput = document.getElementById('noteInput');
            doAttendance(action, noteInput ? noteInput.value : '');
        });
    });
}
