document.addEventListener('DOMContentLoaded', function() {
    initTooltips();
    initGeolocation();
    initPageTransition();
});

function initTooltips() {
    var els = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    els.map(function(el) { return new bootstrap.Tooltip(el); });
}

function confirmAction(msg) {
    return confirm(msg || 'هل أنت متأكد؟');
}

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

var geoWatchId = null;

function initGeolocation() {
    if ('geolocation' in navigator) {
        var btn = document.querySelector('.btn-checkin, .btn-checkout');
        if (btn) {
            btn.addEventListener('click', function(e) {
                var action = this.dataset.action || 'check_in';
                var noteInput = document.getElementById('noteInput');
                doAttendance(action, noteInput ? noteInput.value : '');
            });
        }
        var checkinBtns = document.querySelectorAll('[data-action="check_in"], [data-action="check_out"]');
        checkinBtns.forEach(function(b) {
            b.addEventListener('click', function(e) {
                e.preventDefault();
                var action = this.dataset.action;
                var note = this.dataset.note || '';
                doAttendance(action, note);
            });
        });
    }
}

function doAttendance(action, note) {
    var btn = document.querySelector('[data-action="' + action + '"]');
    if (!btn) btn = document.querySelector('.btn-checkin');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm ms-2"></span> جاري التحميل...';
    }
    if (!navigator.geolocation) {
        showToast('الرجاء تفعيل خدمة الموقع في جهازك', 'danger');
        if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
        return;
    }
    navigator.geolocation.getCurrentPosition(
        function(pos) {
            var data = {
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                note: note || ''
            };
            fetch(action === 'check_in' ? '/employee/check-in' : '/employee/check-out', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.ok) {
                    showToast(res.msg, 'success');
                    setTimeout(function() { location.reload(); }, 1200);
                } else {
                    showToast(res.msg, 'danger');
                    if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
                }
            })
            .catch(function(err) {
                showToast('فشل الاتصال بالخادم', 'danger');
                if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
            });
        },
        function(err) {
            var msgs = {
                1: 'تم رفض طلب الموقع. سمح للوصول للموقع في إعدادات المتصفح.',
                2: 'تعذر تحديد الموقع. تأكد من تفعيل GPS.',
                3: 'انتهت مهلة طلب الموقع. حاول مرة أخرى.'
            };
            showToast(msgs[err.code] || 'خطأ في تحديد الموقع', 'danger');
            if (btn) { btn.disabled = false; btn.innerHTML = originalText(btn, action); }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

function originalText(btn, action) {
    if (action === 'check_in') return '<i class="bi bi-box-arrow-in-right ms-1"></i> تسجيل الحضور';
    return '<i class="bi bi-box-arrow-right ms-1"></i> تسجيل الانصراف';
}

function initPageTransition() {
    var bar = document.getElementById('nprogress-bar');
    if (!bar) return;
    var links = document.querySelectorAll('a:not([target="_blank"]):not([href^="#"]):not([href^="javascript"]):not([download])');
    for (var i = 0; i < links.length; i++) {
        (function(l) {
            l.addEventListener('click', function(e) {
                var href = l.getAttribute('href');
                if (!href || href === '' || href.startsWith('http')) return;
                if (l.getAttribute('data-bs-toggle') || l.dataset.bsToggle) return;
                bar.classList.add('loading');
                bar.classList.remove('done');
            });
        })(links[i]);
    }
    window.addEventListener('pageshow', function() {
        bar.classList.remove('loading');
        bar.classList.add('done');
        setTimeout(function() { bar.classList.remove('done'); }, 400);
    });
    bar.classList.add('done');
    setTimeout(function() { bar.classList.remove('done'); }, 300);
}

var themeToggle = document.getElementById('themeToggle');
if (themeToggle) {
    themeToggle.addEventListener('click', function() {
        var html = document.documentElement;
        var cur = html.getAttribute('data-theme');
        var next = cur === 'light' ? 'dark' : 'light';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        this.querySelector('i').className = next === 'dark' ? 'bi bi-moon-stars' : 'bi bi-sun';
        showToast('تم التبديل إلى الوضع ' + (next === 'dark' ? 'الليلي' : 'النهاري'), 'info');
    });
}
