/* ============================================================
   AI DIGITAL BRAIN — UI interactions
   ============================================================ */
(function () {
  'use strict';

  /* ---------- Theme ---------- */
  const THEME_KEY = 'adb.theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0b0d12' : '#f6f7f9');
  }

  function getPreferredTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
    updateThemeToggle();
  }

  function updateThemeToggle() {
    const current = document.documentElement.getAttribute('data-theme');
    const label = document.querySelector('[data-theme-label]');
    if (label) label.textContent = current === 'dark' ? 'Light mode' : 'Dark mode';
  }

  // Apply immediately (before paint) to avoid flash
  applyTheme(getPreferredTheme());

  document.addEventListener('DOMContentLoaded', () => {
    updateThemeToggle();
    document.querySelectorAll('[data-theme-toggle]').forEach(el => {
      el.addEventListener('click', toggleTheme);
    });
  });

  /* ---------- Sidebar ---------- */
  window.sbToggle = function () {
    document.getElementById('sidebar')?.classList.toggle('open');
    document.getElementById('sbBackdrop')?.classList.toggle('show');
  };
  window.sbClose = function () {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sbBackdrop')?.classList.remove('show');
  };

  document.addEventListener('DOMContentLoaded', () => {
    // Close on item click (mobile only)
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => {
        if (window.innerWidth < 900) window.sbClose();
      });
    });

    // Close on ESC
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') window.sbClose();
    });
  });

  /* ---------- Copy to clipboard ---------- */
  window.copyText = function (text, btn) {
    if (!text) return;
    const done = () => showToast('📋 Copied');
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallback(text, done));
    } else {
      fallback(text, done);
    }
  };

  function fallback(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { showToast('Copy failed', true); }
    document.body.removeChild(ta);
  }

  window.copyFrom = function (elId) {
    const el = document.getElementById(elId);
    if (el) window.copyText(el.textContent.trim());
  };

  /* ---------- Toast ---------- */
  let toastEl = null;
  let toastTimer = null;
  function showToast(msg, isError) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'copied-toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.style.background = isError ? 'var(--danger)' : 'var(--accent)';
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), 1600);
  }
  window.showToast = showToast;

  /* ---------- Confirm helper ---------- */
  window.confirmAction = function (message, form) {
    if (confirm(message || 'Continue?')) {
      form.submit();
    }
    return false;
  };
})();

/* ---------- Help banner toggle ---------- */
(function () {
  const STORAGE_PREFIX = 'adb.help.';

  window.toggleHelp = function (key) {
    const banner = document.getElementById('help-' + key);
    if (!banner) return;
    const body = banner.querySelector('.help-body');
    if (!body) return;
    const isOpen = !body.hasAttribute('hidden');
    if (isOpen) {
      body.setAttribute('hidden', '');
      banner.classList.remove('open');
      try { localStorage.setItem(STORAGE_PREFIX + key, 'closed'); } catch (e) {}
    } else {
      body.removeAttribute('hidden');
      banner.classList.add('open');
      try { localStorage.setItem(STORAGE_PREFIX + key, 'open'); } catch (e) {}
    }
  };

  // Auto-restore state on load
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.help-banner').forEach(banner => {
      const key = banner.id.replace(/^help-/, '');
      let state = null;
      try { state = localStorage.getItem(STORAGE_PREFIX + key); } catch (e) {}
      if (state === 'open') {
        const body = banner.querySelector('.help-body');
        if (body) {
          body.removeAttribute('hidden');
          banner.classList.add('open');
        }
      }
    });
  });
})();


/* ============================================================
   Global Confirm / Alert dialog (replaces native confirm/alert)
   ============================================================ */
(function () {
  var el = {
    backdrop: null, icon: null, title: null, text: null,
    cancel: null, ok: null,
  };
  var currentResolve = null;

  function init() {
    el.backdrop = document.getElementById('g-modal');
    if (!el.backdrop) return false;
    el.icon = document.getElementById('g-modal-icon');
    el.title = document.getElementById('g-modal-title');
    el.text = document.getElementById('g-modal-text');
    el.cancel = document.getElementById('g-modal-cancel');
    el.ok = document.getElementById('g-modal-ok');

    el.cancel.addEventListener('click', function () { close(false); });
    el.ok.addEventListener('click', function () { close(true); });
    el.backdrop.addEventListener('click', function (e) {
      if (e.target === el.backdrop) close(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close(false);
      if (e.key === 'Enter' && el.backdrop.classList.contains('show')) {
        e.preventDefault();
        close(true);
      }
    });
    return true;
  }

  function setIcon(kind) {
    var map = {
      warn: '⚠️', danger: '🗑', info: '❓', success: '✅',
    };
    el.icon.className = 'g-modal-icon ' + (kind || 'info');
    el.icon.textContent = map[kind] || '❓';
  }

  function open(opts, resolve) {
    if (!el.backdrop) init();
    if (!el.backdrop) {
      // Fallback to native if modal not present
      resolve(window.confirm(opts.message || ''));
      return;
    }
    el.title.textContent = opts.title || 'Confirm';
    el.text.textContent = opts.message || '';
    setIcon(opts.kind || 'info');

    // Customize buttons
    el.ok.textContent = opts.okText || 'OK';
    el.cancel.textContent = opts.cancelText || 'Cancel';
    el.cancel.style.display = opts.hideCancel ? 'none' : 'inline-flex';

    // Style ok button
    el.ok.className = 'btn';
    if (opts.kind === 'danger') el.ok.classList.add('danger');
    else if (opts.kind === 'warn') el.ok.classList.add('warn');

    currentResolve = resolve;
    el.backdrop.classList.add('show');
    setTimeout(function () { el.ok.focus(); }, 50);
  }

  function close(result) {
    if (!el.backdrop) return;
    el.backdrop.classList.remove('show');
    var r = currentResolve;
    currentResolve = null;
    if (r) setTimeout(function () { r(result); }, 120);
  }

  // Public API
  window.confirmDialog = function (opts) {
    return new Promise(function (resolve) {
      if (typeof opts === 'string') opts = { message: opts };
      open(opts, resolve);
    });
  };

  window.alertDialog = function (opts) {
    return new Promise(function (resolve) {
      if (typeof opts === 'string') opts = { message: opts };
      opts.hideCancel = true;
      opts.okText = opts.okText || 'OK';
      open(opts, resolve);
    });
  };

  // Auto-replace native confirm on page load
  document.addEventListener('DOMContentLoaded', function () {
    init();
  });
})();


/* ============================================================
   Auto-patch: intercept all inline onclick="return confirm(...)"
   Uses capture phase so it beats the inline handler.
   ============================================================ */
document.addEventListener('click', function (e) {
  var t = e.target.closest('button, input[type=submit], a');
  if (!t) return;

  // Inline onclick with return confirm(...)
  var onclick = t.getAttribute('onclick') || '';
  if (/return\s+confirm\(/.test(onclick)) {
    e.preventDefault();
    e.stopPropagation();

    // Extract the message inside confirm('...')
    var m = onclick.match(/confirm\(\s*['"]([^'"]*)['"]\s*\)/);
    var msg = m ? m[1] : 'Continue?';
    var form = t.closest('form');

    window.confirmDialog({
      title: 'Confirm',
      message: msg,
      kind: /delete|remove|archive/i.test(msg) ? 'danger' : 'warn',
      okText: 'Yes',
    }).then(function (ok) {
      if (!ok) return;
      if (form) {
        form.submit();
      } else if (t.tagName === 'A') {
        window.location = t.href;
      }
    });
    return;
  }
}, true);


/* ============================================================
   customConfirm — used by template buttons
   Usage: onclick="return customConfirm(event, 'message', 'kind')"
   ============================================================ */
window.customConfirm = function (event, message, kind) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  var t = event ? event.currentTarget : null;
  if (!t) return false;

  var form = t.closest('form');
  var isDelete = /delete|remove|archive|disable|block|unlink/i.test(message || '');
  var k = kind || (isDelete ? 'danger' : 'warn');

  window.confirmDialog({
    title: k === 'danger' ? 'Delete / Archive' : 'Confirm',
    message: message || 'Continue?',
    kind: k,
    okText: k === 'danger' ? 'Yes, proceed' : 'Yes',
  }).then(function (ok) {
    if (!ok) return;
    if (form) form.submit();
  });
  return false;
};


/* ============================================================
   Auto-patch for ALL buttons with onclick="return confirm(...)"
   ============================================================ */
document.addEventListener('click', function (e) {
  var t = e.target.closest('button, input[type=submit], a');
  if (!t) return;

  // ★ Skip if explicitly marked
  if (t.hasAttribute('data-no-patch')) return;

  var onclick = t.getAttribute('onclick') || '';
  if (/return\s+confirm\(/.test(onclick) && !/customConfirm/.test(onclick)) {
    e.preventDefault();
    e.stopPropagation();
    var m = onclick.match(/confirm\(\s*['"]([^'"]*)['"]\s*\)/);
    var msg = m ? m[1] : 'Continue?';
    var form = t.closest('form');
    var isDelete = /delete|remove|archive|disable|block|unlink/i.test(msg);
    window.confirmDialog({
      title: isDelete ? 'Delete / Archive' : 'Confirm',
      message: msg,
      kind: isDelete ? 'danger' : 'warn',
      okText: 'Yes',
    }).then(function (ok) {
      if (!ok) return;
      if (form) form.submit();
      else if (t.tagName === 'A') window.location = t.href;
    });
  }
}, true);
