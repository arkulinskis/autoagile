/* core.js: the shared front-end engine (window.UI). Same in every app made from APP_MAKER/template;
   app-specific things live in web/app.js (brand, nav, footer) and web/pages/*.html (the pages).

   Pages:   UI.page(name, {title, nav, icon, auth, order, chrome}, mount)
              auth: null (anyone) | 'guest' (signed-out only) | 'user' | 'admin'
              nav: label for the header / phone tab bar (omit to keep it out of the menus)
              mount(view, ctx) draws into `view`; ctx = {args, me, go, api}. Return a Promise (the page
              is "ready" when it resolves) or {ready, destroy}. URLs are #name/arg1/arg2.
   Server:  UI.api(fn, ...args) -> Promise of the server function's return value. A reply of
              {ok: false, error} rejects with that message (shown as a toast unless you .catch it).
            UI.apiQuiet(fn, ...args) is the same without Anvil's loading spinner.
   Auth:    UI.auth('login'|'signup'|'reset'|'logout', {...}) -> Promise of {ok, me, message}
   Helpers: UI.esc, UI.icon, UI.toast, UI.modal, UI.confirm, UI.busy, UI.formData, UI.fmtDate, UI.ago,
            UI.store, UI.setTheme, UI.feedback, UI.go, UI.refresh
   Tests:   window.UI_READY is true when the current page has finished loading. */
(function () {
  'use strict';
  if (window.UI && window.UI.__v) return;
  var UI = window.UI = { __v: 1, pages: {}, me: null, config: { name: 'App', key: 'app', home: 'home', landing: 'landing' } };
  window.UI_READY = false;

  UI.configure = function (cfg) { Object.keys(cfg).forEach(function (k) { UI.config[k] = cfg[k]; }); };

  /* ------------------------------------------------------------------ small helpers */
  UI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  UI.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  UI.initials = function (name) {
    var p = String(name || '?').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  };
  UI.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  UI.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  UI.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return UI.plural(n, steps[i][1]) + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  UI.store = {
    get: function (k, dflt) { try { var v = localStorage.getItem(UI.config.key + '.' + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
    set: function (k, v) { try { localStorage.setItem(UI.config.key + '.' + k, JSON.stringify(v)); } catch (e) {} }
  };
  UI.formData = function (form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox') out[el.name] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value;
    });
    return out;
  };
  /* Disable a button while a Promise runs; returns the Promise. */
  UI.busy = function (btn, promise) {
    if (!btn) return promise;
    btn.disabled = true; btn.classList.add('is-busy');
    var done = function () { btn.disabled = false; btn.classList.remove('is-busy'); };
    promise.then(done, done);
    return promise;
  };

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c2.2.6 3.5 2.4 3.5 5.3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M12 8V5M9 5.5 7.5 4M15 5.5 16.5 4M7 13H3M21 13h-4M7.5 18l-3 2M16.5 18l3 2M7.5 9.5l-3-2M16.5 9.5l3-2"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'
  };
  UI.ICONS = ICONS;
  UI.icon = function (name, cls) {
    return '<svg class="ui-ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.sparkle) + '</svg>';
  };

  /* ------------------------------------------------------------------ toasts, modals */
  UI.toast = function (msg, kind) {
    var box = document.querySelector('.ui-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'ui ui-toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div');
    t.className = 'ui-toast' + (kind ? ' ' + kind : '');
    t.innerHTML = (kind === 'error' ? UI.icon('info') : kind === 'ok' ? UI.icon('check') : '') + '<span>' + UI.esc(msg) + '</span>';
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'error' ? 6500 : 3200);
  };
  UI.modal = function (html, opts) {
    opts = opts || {};
    var prev = document.activeElement;
    var wrap = document.createElement('div');
    wrap.className = 'ui ui-modal-wrap';
    wrap.innerHTML = '<div class="ui-modal' + (opts.wide ? ' wide' : '') + '" role="dialog" aria-modal="true">' +
      '<button class="ui-btn ghost icon ui-modal-x" data-close aria-label="Close">' + UI.icon('x') + '</button>' + html + '</div>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    function key(e) { if (e.key === 'Escape') close(); }
    function close() {
      if (!wrap.parentNode) return;
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (opts.onclose) opts.onclose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });
    wrap.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    var first = wrap.querySelector('input, textarea, select');
    setTimeout(function () { (first || wrap.querySelector('.ui-modal')).focus && (first || wrap.querySelector('.ui-modal')).focus(); }, 30);
    return { el: wrap.querySelector('.ui-modal'), close: close };
  };
  UI.confirm = function (o) {
    o = typeof o === 'string' ? { title: o } : (o || {});
    return new Promise(function (resolve) {
      var answered = false;
      var m = UI.modal('<h2>' + UI.esc(o.title || 'Are you sure?') + '</h2>' + (o.text ? '<p class="muted">' + UI.esc(o.text) + '</p>' : '') +
        '<div class="ui-row end" style="margin-top:20px"><button class="ui-btn ghost" data-close>' + UI.esc(o.cancel || 'Cancel') + '</button>' +
        '<button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" data-ok>' + UI.esc(o.ok || 'OK') + '</button></div>',
      { onclose: function () { if (!answered) resolve(false); } });
      m.el.querySelector('[data-ok]').onclick = function () { answered = true; m.close(); resolve(true); };
    });
  };

  /* ------------------------------------------------------------------ theme */
  UI.theme = function () { return UI.store.get('theme', 'auto'); };
  UI.applyTheme = function (t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    var dark = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('ui-dark', !!dark);
  };
  UI.setTheme = function (t) { UI.store.set('theme', t); UI.applyTheme(t); };
  UI.applyTheme(UI.theme());
  if (window.matchMedia) {
    try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { UI.applyTheme(UI.theme()); }); } catch (e) {}
  }

  /* ------------------------------------------------------------------ server bridge */
  var bridge = null;
  function send(kind, payload) {
    if (!bridge) return Promise.reject(new Error('The app is still starting.'));
    var out;
    try { out = bridge(kind, JSON.stringify(payload || {})); } catch (e) { return Promise.reject(e); }
    return Promise.resolve(out).then(function (r) {
      r = typeof r === 'string' ? JSON.parse(r) : (r || {});
      if (r.error) {
        var err = new Error(r.error); err.uiApi = true; err.denied = !!r.denied;
        if (r.detail) console.error(kind, payload && payload.fn, r.detail);
        if (r.reload) setTimeout(function () { location.reload(); }, 2500);
        throw err;
      }
      return r.result;
    });
  }
  function apiCall(quiet, fn, args) {
    return send('call', { fn: fn, args: args, quiet: quiet }).then(function (res) {
      if (res && typeof res === 'object' && res.ok === false) {
        var err = new Error(res.error || 'That didn\'t work.'); err.uiApi = true; err.expected = true; err.result = res;
        throw err;
      }
      return res;
    });
  }
  UI.api = function (fn) { return apiCall(false, fn, Array.prototype.slice.call(arguments, 1)); };
  UI.apiQuiet = function (fn) { return apiCall(true, fn, Array.prototype.slice.call(arguments, 1)); };
  /* Errors nobody caught become a toast, so a failed action is never silent. */
  window.addEventListener('unhandledrejection', function (e) {
    if (e.reason && e.reason.uiApi) { e.preventDefault(); UI.toast(e.reason.message, 'error'); }
  });

  /* Sign in / up / out. On success it navigates: to where the visitor was heading (UI.after) or home
     after signing in, to the landing page after signing out. */
  UI.auth = function (kind, payload) {
    return send(kind, payload || {}).then(function (r) {
      if (r && r.ok === false) { var err = new Error(r.error); err.uiApi = true; err.expected = true; throw err; }
      if (r && 'me' in r && (r.me || kind === 'logout')) {
        UI.me = r.me || null;
        var target = r.me ? (UI.after || '#' + UI.config.home) : '#' + UI.config.landing;
        UI.after = null;
        if (location.hash === target) route(); else location.hash = target;
      }
      return r;
    });
  };
  /* Update the signed-in user's details (e.g. a new name) and redraw the header, without reloading the page. */
  UI.setMe = function (me) {
    UI.me = me || null;
    if (shellRoot) renderChrome(current.name);
  };

  /* ------------------------------------------------------------------ pages and routing */
  UI.page = function (name, opts, mount) {
    if (typeof opts === 'function') { mount = opts; opts = {}; }
    opts.name = name; opts.mount = mount;
    UI.pages[name] = opts;
  };
  UI.allowed = function (p) {
    if (!p) return false;
    if (p.auth === 'user') return !!UI.me;
    if (p.auth === 'admin') return !!(UI.me && UI.me.is_admin);
    if (p.auth === 'guest') return !UI.me;
    return true;
  };
  UI.navPages = function () {
    return Object.keys(UI.pages).map(function (k) { return UI.pages[k]; })
      .filter(function (p) { return p.nav && UI.allowed(p) && (!p.when || p.when()); })
      .sort(function (a, b) { return (a.order || 50) - (b.order || 50); });
  };
  UI.parseHash = function () {
    var h = (location.hash || '').replace(/^#!?\/?/, '');
    var parts = h.split('?')[0].split('/').filter(function (x) { return x !== ''; }).map(decodeURIComponent);
    return { name: parts[0] || '', args: parts.slice(1) };
  };
  UI.hashFor = function (name) {
    var args = Array.prototype.slice.call(arguments, 1).filter(function (a) { return a != null && a !== ''; });
    return '#' + [name].concat(args.map(encodeURIComponent)).join('/');
  };
  UI.go = function (name) {
    var h = UI.hashFor.apply(null, arguments);
    if (location.hash === h) route(); else location.hash = h;
  };
  UI.refresh = function () { route(); };
  UI.after = null;  // where to go after signing in

  var shellRoot = null, view = null, current = { name: null, destroy: null }, routeSeq = 0;

  function defaultPage() { return UI.me ? UI.config.home : UI.config.landing; }

  function route() {
    var r = UI.parseHash(), name = r.name || defaultPage(), p = UI.pages[name];
    if (!p) { name = defaultPage(); p = UI.pages[name]; r.args = []; }
    if (p.auth === 'guest' && UI.me) { p = UI.pages[UI.config.home]; name = UI.config.home; r.args = []; }
    if ((p.auth === 'user' || p.auth === 'admin') && !UI.me) {
      UI.after = location.hash && location.hash !== '#' ? location.hash : null;
      p = UI.pages.auth; name = 'auth'; r.args = [];
    }
    if (p.auth === 'admin' && !(UI.me && UI.me.is_admin)) {
      UI.toast('That page is for admins only.', 'error');
      p = UI.pages[UI.config.home]; name = UI.config.home; r.args = [];
    }
    var seq = ++routeSeq;
    window.UI_READY = false;
    if (current.destroy) { try { current.destroy(); } catch (e) { console.error(e); } }
    current = { name: name, args: r.args, destroy: null };
    if (shellRoot) {
      shellRoot.className = 'ui ui-shell page-' + name + (UI.me ? ' signed-in' : ' signed-out') + (p.chrome === false ? ' no-chrome' : '');
      renderChrome(name);
    }
    // A fresh element for every page, so listeners a page adds to `view` never pile up.
    var fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    view = fresh;
    window.scrollTo(0, 0);
    document.title = (p.title ? (typeof p.title === 'function' ? p.title(r.args) : p.title) + ' · ' : '') + UI.config.name;
    var ctx = { name: name, args: r.args, me: UI.me, go: UI.go, api: UI.api, page: p };
    var out;
    try { out = p.mount(view, ctx); } catch (e) { console.error(e); out = Promise.reject(e); }
    var ready = out && typeof out.then === 'function' ? out : (out && out.ready) || Promise.resolve();
    if (out && out.destroy) current.destroy = out.destroy;
    Promise.resolve(ready).then(function () { if (seq === routeSeq) window.UI_READY = true; },
      function (e) {
        if (seq !== routeSeq) return;
        console.error(e);
        if (!view.innerHTML) view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('info') +
          '<h3>This page didn\'t load</h3><p class="muted">' + UI.esc(e && e.message || 'Something went wrong.') + '</p>' +
          '<button class="ui-btn" onclick="UI.refresh()">Try again</button></div></div>';
        window.UI_READY = true;
      });
  }
  UI.current = function () { return current; };

  /* The shell's parts come from web/app.js: UI.shell = {header(me, active), footer(me), tabbar(me, active)} */
  function renderChrome(active) {
    var S = UI.shell || {};
    var hd = shellRoot.querySelector('[data-ui-header]'), ft = shellRoot.querySelector('[data-ui-footer]'), tb = shellRoot.querySelector('[data-ui-tabbar]');
    if (hd) hd.innerHTML = S.header ? S.header(UI.me, active) : '';
    if (ft) ft.innerHTML = S.footer ? S.footer(UI.me, active) : '';
    if (tb) tb.innerHTML = S.tabbar ? S.tabbar(UI.me, active) : '';
  }
  UI.renderChrome = function () { if (shellRoot) renderChrome(current.name); };

  /* Called by client_code/Main.py (and by the local harness) once the page is up. */
  UI.start = function (node, bridgeFn, bootJson) {
    bridge = bridgeFn;
    var boot = typeof bootJson === 'string' ? JSON.parse(bootJson || '{}') : (bootJson || {});
    UI.me = boot.me || null;
    var host = node && node.matches && node.matches('[data-ui-app]') ? node : (node && node.querySelector('[data-ui-app]')) || node || document.body;
    host.innerHTML = '<div class="ui ui-shell">' +
      '<header class="ui-header" data-ui-header></header>' +
      '<main class="ui-main" data-ui-view></main>' +
      '<footer class="ui-footer" data-ui-footer></footer>' +
      '<nav class="ui-tabbar" data-ui-tabbar aria-label="Main"></nav></div>';
    shellRoot = host.firstChild;
    view = host.querySelector('[data-ui-view]');
    if (UI.shell && UI.shell.wire) UI.shell.wire(shellRoot);
    window.addEventListener('hashchange', route);
    route();
  };

  /* ------------------------------------------------------------------ feedback (footer + menu)
     All feedback goes to Prepsto. The widget tag in head.html (data-prepsto="CODE") slides its panel in;
     any [data-feedback] or [data-prepsto-open] element opens it. If the widget hasn't loaded, the panel opens in a new tab.
     There is no in-app feedback form any more: Admin -> Feedback only lists older messages (and app requests). */
  UI.feedback = function () {
    if (window.Prepsto && window.Prepsto.open) { window.Prepsto.open(); return; }
    var tag = document.querySelector('script[data-prepsto]');
    var code = tag && tag.getAttribute('data-prepsto');
    if (code && code.indexOf('__') !== 0) window.open('https://prepsto.com/#f/' + encodeURIComponent(code), '_blank', 'noopener');
    else UI.toast('Feedback is not set up yet.', 'error');
  };

  /* Shared clicks: [data-go="page/arg"], [data-feedback], [data-theme-set] anywhere in the app. */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-go],[data-feedback],[data-theme-set]');
    if (!el) return;
    if (el.hasAttribute('data-go')) { e.preventDefault(); UI.go.apply(null, el.getAttribute('data-go').split('/')); }
    else if (el.hasAttribute('data-feedback')) { e.preventDefault(); UI.feedback(el.getAttribute('data-feedback') || null); }
    else if (el.hasAttribute('data-theme-set')) { e.preventDefault(); UI.setTheme(el.getAttribute('data-theme-set')); if (UI.shell && UI.shell.onTheme) UI.shell.onTheme(); }
  });
})();


/* app.js: this app's identity and frame: name, header, footer, phone tab bar.
   Pages live in web/pages/*.html. The engine (window.UI) is web/core.js. */
(function () {
  'use strict';
  UI.configure({
    name: 'AutoAgile',
    key: 'autoagile',          // prefix for this app's browser storage
    tagline: 'Agile that levels up. For crews of humans and AI developers.',
    home: 'deck',                // first page after signing in
    landing: 'landing'           // first page for visitors who aren't signed in
  });

  var esc = UI.esc;

  function brand() {
    return '<a class="ui-brand" href="#" data-go="' + (UI.me ? UI.config.home : UI.config.landing) + '" aria-label="' + esc(UI.config.name) + ' home">' +
      '<img src="_/theme/icon.svg" alt="" width="32" height="32"><span>' + esc(UI.config.name) + '</span></a>';
  }

  function themeSwitch() {
    var t = UI.theme();
    return '<div class="ui-seg" role="group" aria-label="Appearance">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function userMenu(me) {
    return '<div class="ui-menu" data-menu hidden>' +
      '<div class="ui-menu-head"><strong>' + esc(me.name) + '</strong><span class="muted small">' + esc(me.email) + '</span></div>' +
      '<a href="#profile" data-go="profile">' + UI.icon('user') + 'Your profile</a>' +
      '<a href="#crew" data-go="crew">' + UI.icon('users') + 'Crew settings</a>' +
      '<a href="#agents" data-go="agents">' + UI.icon('bot') + 'AI agents</a>' +
      '<a href="#insights" data-go="insights">' + UI.icon('chart') + 'Insights</a>' +
      '<a href="#requests" data-go="requests">' + UI.icon('megaphone') + 'Requests</a>' +
      '<a href="#import" data-go="import">' + UI.icon('upload') + 'Import and export</a>' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<div class="ui-menu-block"><span class="small muted">Appearance</span>' + themeSwitch() + '</div>' +
      '<button type="button" data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
      '<button type="button" data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms</button>' +
      '<button type="button" data-signout>' + UI.icon('logout') + 'Sign out</button></div>';
  }

  UI.shell = {
    header: function (me, active) {
      var nav = UI.navPages();
      return '<div class="ui-header-in">' + brand() +
        (me ? '<nav class="ui-nav" aria-label="Main">' + nav.map(function (p) {
          return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
        }).join('') + '</nav>' : '') +
        '<div class="ui-header-right">' + (me && window.AA ? AA.crewChip() : '') +
        (me ? '<button type="button" class="ui-avatar-btn" data-menu-toggle aria-label="Your account" aria-haspopup="true">' + esc(UI.initials(me.name)) + '</button>' + userMenu(me)
          : (active === 'auth' ? '' : '<a class="ui-btn ghost" href="#auth" data-go="auth">Sign in</a><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Get started</a>')) +
        '</div></div>';
    },
    footer: function (me) {
      return '<div class="ui-footer-in"><div class="ui-footer-brand">' + brand() + '<p class="muted small">' + esc(UI.config.tagline) + '</p></div>' +
        '<div class="ui-footer-links">' +
        '<a href="#landing" data-go="landing">About</a>' +
        '<a href="https://prepsto.com/#f/xybae8y" target="_blank" rel="noopener" data-prepsto-open>Submit feedback</a>' +
        '<button type="button" data-lk-open="overview">Privacy &amp; Terms</button>' +
        '</div><p class="ui-footer-legal small muted">© ' + new Date().getFullYear() + ' ' + esc(UI.config.name) + '</p></div>';
    },
    tabbar: function (me, active) {
      var nav = UI.navPages();
      if (!me || nav.length < 2) return '';
      return nav.slice(0, 4).map(function (p) {
        return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
      }).join('') + '<a href="#profile" class="' + (active === 'profile' ? 'on' : '') + '">' + UI.icon('user') + '<span>You</span></a>';
    },
    wire: function (root) {
      root.addEventListener('click', function (e) {
        var t = e.target.closest('[data-menu-toggle]');
        var menu = root.querySelector('[data-menu]');
        if (t && menu) { menu.hidden = !menu.hidden; t.setAttribute('aria-expanded', String(!menu.hidden)); return; }
        if (e.target.closest('[data-signout]')) { if (window.AA) AA.crews = null; UI.auth('logout').then(function () { UI.toast('Signed out. See you soon!'); }); }
        if (menu && !menu.hidden && !e.target.closest('[data-menu] .ui-seg')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        var menu = root.querySelector('[data-menu]');
        if (e.key === 'Escape' && menu) menu.hidden = true;
      });
    },
    onTheme: function () {  // redraw the menu's Auto/Light/Dark buttons and keep the menu open
      var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
      UI.renderChrome();
      if (open) document.querySelector('[data-menu]').hidden = false;
    }
  };
})();


/* ===== _aa.html ===== */
(function () {
  'use strict';
  var AA = window.AA = {};
  var esc = UI.esc;

  Object.assign(UI.ICONS, {
    bot: '<rect x="5" y="8" width="14" height="11" rx="2"/><path d="M12 4v4M9.5 13h.01M14.5 13h.01M9.5 16.5h5M3 12v3M21 12v3"/>',
    chart: '<path d="M4 20V4M4 20h16"/><path d="M8 16v-4M12 16V8M16 16v-7M20 16v-2"/>',
    board: '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="11" rx="1"/><rect x="17" y="4" width="4" height="7" rx="1"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
    deck: '<path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="m12 17 4.5-6"/><path d="M3 20h18"/>',
    gate: '<path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-7h6v7M4 11h16"/>',
    zap: '<path d="M13 3 4 14h7l-1 7 9-11h-7z"/>',
    flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
    terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    play: '<path d="M7 4v16l13-8z"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    up: '<path d="m6 15 6-6 6 6"/>', down: '<path d="m6 9 6 6 6-6"/>', top: '<path d="M6 4h12M6 14l6-6 6 6M12 8v12"/>',
    settings: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    download: '<path d="M12 4v11M7 10l5 5 5-5M4 20h16"/>', upload: '<path d="M12 16V5M7 10l5-5 5 5M4 20h16"/>',
    megaphone: '<path d="M3 10v4h4l7 5V5L7 10z"/><path d="M18 9a4 4 0 0 1 0 6"/>',
    printer: '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="1"/><path d="M7 14h10v7H7z"/>'
  });

  /* ---------------------------------------------------------------- crews */
  AA.crews = null; AA._for = null;
  AA.crewId = function () { return UI.store.get('crew', null); };
  AA.current = function () {
    if (!AA.crews || !UI.me || AA._for !== UI.me.id) return null;
    var id = AA.crewId();
    return AA.crews.filter(function (c) { return c.id === id; })[0] || AA.crews[0] || null;
  };
  AA.loadCrews = function (force) {
    if (!UI.me) return Promise.resolve([]);
    if (AA.crews && !force && AA._for === UI.me.id) return Promise.resolve(AA.crews);
    return UI.api('my_crews').then(function (r) {
      AA.crews = r.crews; AA._for = UI.me.id;
      var c = AA.current();
      if (c) UI.store.set('crew', c.id);
      UI.renderChrome();
      return AA.crews;
    });
  };
  AA.setCrew = function (id) { UI.store.set('crew', id); UI.renderChrome(); };
  /* Run fn(crew) once crews are loaded; with no crew at all, send people to make one. */
  AA.withCrew = function (view, fn) {
    return AA.loadCrews().then(function () {
      var c = AA.current();
      if (!c) { UI.go('crew', 'new'); return; }
      return fn(c);
    });
  };
  AA.crewChip = function () {
    var c = AA.current();
    if (!c) return '';
    return '<button type="button" class="aa-kbtn" data-palette title="Jump anywhere (Ctrl K or /)" aria-label="Search and jump">CTRL K</button>' +
      '<button type="button" class="aa-crewchip" data-crew-switch title="Switch crew" aria-label="Crew ' + esc(c.name) + ', switch crew">' +
      '<span class="aa-led ' + (c.demo ? 'pink' : 'on') + '"></span>' + esc(c.key) + ' <span class="faint">L' + c.level + '</span>' + UI.icon('chevron') + '</button>';
  };
  AA.switcher = function () {
    var cur = AA.current();
    var m = UI.modal('<h2>Your crews</h2><p class="muted">A crew is a team with one board. Demo crews are a shared sandbox: play freely.</p>' +
      '<div class="aa-crewlist">' + (AA.crews || []).map(function (c) {
        return '<button type="button" data-pick="' + esc(c.id) + '" class="' + (cur && cur.id === c.id ? 'on' : '') + '"><span class="k">' + esc(c.key) + '</span>' +
          '<span style="flex:1;min-width:0"><b>' + esc(c.name) + '</b><br><span class="small muted">Level ' + c.level + ' · ' + esc(c.level_name) + ' · ' + UI.plural(c.open, 'open card') +
          (c.demo ? ' · <b style="color:var(--c-accent)">DEMO</b>' : ' · ' + esc(c.role)) + '</span></span></button>';
      }).join('') + '</div><div class="ui-row"><button class="ui-btn primary" data-go="crew/new" data-close>' + UI.icon('plus') + 'New crew</button>' +
      '<button class="ui-btn" data-go="crew/join" data-close>' + UI.icon('key') + 'Join with a code</button></div>');
    m.el.addEventListener('click', function (e) {
      var b = e.target.closest('[data-pick]');
      if (b) { AA.setCrew(b.getAttribute('data-pick')); m.close(); if (UI.current().name === 'card') UI.go('deck'); else UI.refresh(); }
    });
  };
  AA.demoNote = function (crew) {
    return crew && crew.demo ? '<div class="aa-demo-note"><b>DEMO CREW</b> // a shared sandbox: everyone signed in can play here. ' +
      '<a href="#crew/new" data-go="crew/new">Start your own crew</a> when you\'re ready.</div>' : '';
  };

  /* ---------------------------------------------------------------- small pieces */
  AA.TYPES = ['story', 'bug', 'task', 'spike', 'chore'];
  AA.STATUS = { backlog: 'Backlog', ready: 'Ready', doing: 'Doing', review: 'Review', done: 'Done' };
  AA.FIT = { solo: 'AGENT SOLO', pair: 'AGENT + HUMAN', human: 'HUMAN LED' };
  AA.type = function (t) { return '<span class="aa-type t-' + esc(t) + '">' + esc(t) + '</span>'; };
  AA.pts = function (p) { return p == null ? '<span class="aa-pts none" title="Not estimated">?</span>' : '<span class="aa-pts" title="' + p + ' points">' + p + '</span>'; };
  AA.prio = function (p) { return p === 2 || p == null ? '' : '<span class="aa-prio p' + p + '" title="Priority P' + p + '">P' + p + '</span>'; };
  AA.fit = function (f) { return f ? '<span class="aa-fit ' + f + '">' + (f === 'solo' ? '⚡ ' : '') + AA.FIT[f] + '</span>' : ''; };
  AA.who = function (p, cls) {
    if (!p) return '<span class="aa-who none ' + (cls || '') + '" title="Nobody yet">?</span>';
    if (p.kind === 'agent') return '<span class="aa-who agent ' + (cls || '') + '" style="background:' + esc(p.color || '#00e5ff') + '" title="' + esc(p.name) + ' (AI agent)">' + UI.icon('bot') + '</span>';
    return '<span class="aa-who ' + (cls || '') + '" title="' + esc(p.name) + '">' + esc(UI.initials(p.name)) + '</span>';
  };
  AA.whoName = function (p) {
    return '<span class="aa-chipname">' + AA.who(p) + '<b>' + esc(p ? p.name : 'Unassigned') + '</b>' + (p && p.kind === 'agent' ? '<span class="ui-badge">AI</span>' : '') + '</span>';
  };
  AA.label = function (l) { return '<span class="aa-label' + (l === 'agent-proposed' ? ' agentp' : '') + '">' + esc(l) + '</span>'; };
  AA.age = function (d) {
    if (d == null) return '';
    var cls = d > 5 ? 'stale' : d > 2.5 ? 'old' : '';
    return '<span class="age ' + cls + '" title="Days in this column">' + (d < 1 ? Math.max(1, Math.round(d * 24)) + 'h' : Math.round(d) + 'd') + '</span>';
  };
  AA.card = function (c, o) {
    o = o || {};
    var agent = c.assignee && c.assignee.kind === 'agent';
    return '<button type="button" class="aa-card t-' + esc(c.type) + (c.blocked ? ' blocked' : '') + (agent ? ' agentcard' : '') + '" data-card="' + esc(c.key) + '" data-id="' + esc(c.id) + '"' +
      (o.drag ? ' draggable="true"' : '') + ' style="' + (c.epic ? '--epic:' + esc(c.epic.color) + ';' : '') + (agent ? '--agent:' + esc(c.assignee.color) : '') + '">' +
      '<div class="top"><span class="key">' + esc(c.key) + '</span>' + AA.type(c.type) + AA.prio(c.priority) + '<span class="ui-spacer"></span>' + AA.pts(c.points) + '</div>' +
      '<div class="title">' + (c.blocked ? '⛔ ' : '') + esc(c.title) + '</div>' +
      (c.labels && c.labels.length ? '<div class="aa-tagline">' + c.labels.map(AA.label).join('') + '</div>' : '') +
      '<div class="bot">' + AA.who(c.assignee) + (c.acc_total ? '<span title="Acceptance criteria ticked">☑ ' + c.acc_done + '/' + c.acc_total + '</span>' : '') +
      (c.fit === 'solo' && c.agent_ready && c.status !== 'done' ? '<span title="Agent-ready: passes the Definition of Ready" style="color:var(--c-good)">⚡RDY</span>' : '') +
      '<span class="sp"></span>' + (o.age !== false && (c.status === 'doing' || c.status === 'review') ? AA.age(c.age) : '') +
      (c.status === 'done' && c.done_at ? '<span>' + esc(UI.ago(c.done_at)) + '</span>' : '') + '</div></button>';
  };
  AA.lcd = function (value, label, cls) { return '<div class="aa-lcd ' + (cls || '') + '"><b>' + value + '</b><span>' + esc(label) + '</span></div>'; };
  AA.win = function (title, body, o) {
    o = o || {};
    return '<section class="aa-win ' + (o.cls || '') + '"' + (o.attrs || '') + '><header class="aa-win-bar"><span>' + title + '</span>' + (o.extra ? '<em>' + o.extra + '</em>' : '') +
      '<i></i><i></i><i></i></header><div class="aa-win-body' + (o.flush ? ' flush' : '') + '">' + body + '</div></section>';
  };
  AA.spark = function (vals) {
    var max = Math.max.apply(null, vals.concat([1]));
    return '<span class="aa-spark" aria-hidden="true">' + vals.map(function (v) { return '<i style="height:' + Math.max(2, Math.round(26 * v / max)) + 'px"></i>'; }).join('') + '</span>';
  };
  AA.meter = function (pct, n) {
    n = n || 10; var on = Math.round(pct / 100 * n), out = '';
    for (var i = 0; i < n; i++) out += '<i class="' + (i < on ? 'on' : '') + '"></i>';
    return '<div class="aa-meter" role="img" aria-label="' + pct + '%">' + out + '</div>';
  };
  AA.smiley = function (size, color) {
    color = color || '#b4ff1f';
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" fill="' + color + '" stroke="#07070d" stroke-width="5"/>' +
      '<ellipse cx="35" cy="38" rx="6" ry="11" fill="#07070d"/><ellipse cx="65" cy="38" rx="6" ry="11" fill="#07070d"/>' +
      '<path d="M24 58 Q50 86 76 58" fill="none" stroke="#07070d" stroke-width="6" stroke-linecap="round"/></svg>';
  };
  AA.ticker = function (items) {
    if (!items.length) return '';
    var s = items.map(function (t) { return '<em>+++</em> ' + esc(t) + ' '; }).join('');
    return '<div class="aa-ticker" aria-label="Agent activity"><div class="in">' + s + '<em>+++</em></div></div>';
  };
  AA.copy = function (text, msg) {
    var done = function () { UI.toast(msg || 'Copied', 'ok'); };
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).then(done, function () { fallback(); });
    fallback();
    function fallback() {
      var t = document.createElement('textarea'); t.value = text; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) { UI.toast('Copy failed: select the text by hand.', 'error'); }
      t.remove();
    }
  };
  AA.apiBase = function () { return location.origin + '/_/api'; };

  /* Mini markdown: escapes first, then # headings, - lists, **bold**, `code`, [links](https://...). */
  AA.md = function (src) {
    var lines = esc(src || '').split('\n'), out = [], list = false;
    function inline(s) {
      return s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    }
    lines.forEach(function (l) {
      var m = l.match(/^\s*[-*] (.*)$/);
      if (m) { if (!list) { out.push('<ul>'); list = true; } out.push('<li>' + inline(m[1].replace(/^\[( |x)\] /, function (_, x) { return x === 'x' ? '☑ ' : '☐ '; })) + '</li>'); return; }
      if (list) { out.push('</ul>'); list = false; }
      var h = l.match(/^#{1,4} (.*)$/);
      if (h) { out.push('<h4>' + inline(h[1]) + '</h4>'); return; }
      if (l.trim()) out.push('<p>' + inline(l) + '</p>');
    });
    if (list) out.push('</ul>');
    return '<div class="aa-md">' + out.join('') + '</div>';
  };

  /* ---------------------------------------------------------------- complexity gates (mirror of Gates.py) */
  AA.gateScore = function (answers, cfg) {
    var a = {}, n = 0;
    cfg.gates.forEach(function (g) { var v = answers[g.id]; if (v === 0 || v === 1 || v === 2 || v === 3) { a[g.id] = v; n++; } });
    if (n < cfg.gates.length) return { complete: false, answered: n, points: null };
    var total = 0; Object.keys(a).forEach(function (k) { total += a[k]; });
    var points = 1, rung = 'TICK';
    cfg.ladder.forEach(function (r) { if (total >= r.min) { points = r.points; } });
    var floor = 1;
    Object.keys(a).forEach(function (k) { var f = cfg.floors[String(a[k])]; if (f && f > floor) floor = f; });
    var floored = floor > points; points = Math.max(points, floor);
    cfg.ladder.forEach(function (r) { if (r.points === points) rung = r.name; });
    var notes = [], verdict = 'go';
    if (floored) notes.push('A red answer raised the floor to ' + floor + ' points.');
    if (a.clarity === 3) { verdict = 'spike'; notes.push('Clarity is unknown: run a time-boxed spike before building.'); }
    else if (points >= cfg.split_at) { verdict = 'split'; notes.push(points + ' points will not fit one sprint comfortably: split it.'); }
    var fit = 'human';
    if (a.clarity <= 1 && a.verify <= 1 && a.risk <= 1 && a.deps <= 1 && points <= 5) fit = 'solo';
    else if (a.clarity <= 2 && a.risk <= 2 && points <= 8) fit = 'pair';
    return { complete: true, total: total, points: points, rung: rung, floored: floored, verdict: verdict, fit: fit, notes: notes };
  };
  AA.gateWidget = function (el, cfg, answers, onchange) {
    answers = Object.assign({}, answers || {});
    function draw() {
      var s = AA.gateScore(answers, cfg), next = null;
      cfg.gates.forEach(function (g) { if (next == null && answers[g.id] == null) next = g.id; });
      var lit = s.complete ? s.points : null;
      el.innerHTML = '<div class="aa-gates"><div class="aa-gate-rows">' + cfg.gates.map(function (g, gi) {
        return '<div class="aa-gate' + (g.id === next ? ' next' : '') + '" data-g="' + g.id + '"><div class="q"><b>' + esc(g.name) + '</b><span>' + esc(g.q) + '</span>' +
          (g.id === next ? '<kbd>keys 1-4</kbd>' : '') + '</div>' +
          '<div class="opts" role="radiogroup" aria-label="' + esc(g.name) + '">' + g.opts.map(function (o, i) {
            return '<button type="button" role="radio" aria-checked="' + (answers[g.id] === i) + '" class="lv' + i + (answers[g.id] === i ? ' on' : '') + '" data-v="' + i + '">' + esc(o) + '</button>';
          }).join('') + '</div></div>';
      }).join('') + '</div><div><div class="aa-ladder" aria-label="Points ladder">' + cfg.ladder.slice().reverse().map(function (r) {
        var on = lit != null && r.points <= lit;
        return '<div class="aa-rung' + (on ? ' lit' : '') + (on && r.points >= 8 ? ' hot' : '') + (on && r.points >= 13 ? ' fire' : '') + (r.points === lit ? ' top' : '') + '">' +
          '<i></i><b>' + r.points + '</b><span>' + r.name + '</span></div>';
      }).join('') + '</div>' +
        '<div class="aa-verdict">' + (s.complete ? '<div class="big">' + s.points + ' PTS <span class="faint">//</span> ' + esc(s.rung) + '</div>' + AA.fit(s.fit) +
          s.notes.map(function (n) { return '<div class="note' + (s.verdict !== 'go' ? ' bad' : '') + '">' + esc(n) + '</div>'; }).join('')
          : '<div class="big faint">' + s.answered + '/' + cfg.gates.length + '</div><span class="small muted">Answer every gate to light the ladder.</span>') + '</div></div></div>';
    }
    el.addEventListener('click', function (e) {
      var b = e.target.closest('.aa-gate [data-v]');
      if (!b) return;
      answers[b.closest('[data-g]').getAttribute('data-g')] = +b.getAttribute('data-v');
      draw(); if (onchange) onchange(answers, AA.gateScore(answers, cfg));
    });
    draw();
    return {
      answers: function () { return answers; },
      score: function () { return AA.gateScore(answers, cfg); },
      key: function (n) {
        var g = cfg.gates.filter(function (x) { return answers[x.id] == null; })[0];
        if (!g || n < 1 || n > 4) return false;
        answers[g.id] = n - 1; draw(); if (onchange) onchange(answers, AA.gateScore(answers, cfg)); return true;
      },
      reset: function (a) { answers = Object.assign({}, a || {}); draw(); }
    };
  };

  /* ---------------------------------------------------------------- levels */
  AA.levels = function (levels, cur) {
    return '<div class="aa-levels">' + levels.map(function (l) {
      var st = l.n < cur ? 'done' : l.n === cur ? 'cur' : 'locked';
      return '<div class="aa-lvl ' + st + '"><span class="n">LVL ' + l.n + '</span><b>' + esc(l.name) + '</b><small>' + esc(l.title) + '</small></div>';
    }).join('') + '</div>';
  };
  AA.rave = function (title, sub) {
    var o = document.createElement('div');
    o.className = 'ui aa-rave'; o.setAttribute('role', 'status');
    var bits = '', cols = ['#b4ff1f', '#ff2bd6', '#00e5ff', '#ffd60a', '#ffffff'];
    for (var i = 0; i < 70; i++) {
      bits += '<i class="bit" style="left:' + (Math.random() * 100) + '%;background:' + cols[i % cols.length] + ';animation-duration:' + (1.6 + Math.random() * 2.2) +
        's;animation-delay:' + (Math.random() * .8) + 's;' + (i % 3 ? '' : 'border-radius:50%') + '"></i>';
    }
    o.innerHTML = bits + '<div class="msg">' + AA.smiley(110) + '<h2>' + esc(title) + '</h2><p>' + esc(sub || '') + '</p></div>';
    document.body.appendChild(o);
    var close = function () { o.remove(); };
    o.addEventListener('click', close);
    setTimeout(close, 3400);
  };

  /* ---------------------------------------------------------------- charts (SVG, hover tooltips) */
  var tip = null;
  function showTip(e, head, rows) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'ui aa-tip'; document.body.appendChild(tip); }
    tip.textContent = '';
    if (head) { var h = document.createElement('div'); h.className = 'head'; h.textContent = head; tip.appendChild(h); }
    rows.forEach(function (r) {
      var d = document.createElement('div'); d.className = 'row';
      if (r.color) { var k = document.createElement('span'); k.className = 'key'; k.style.background = r.color; d.appendChild(k); }
      var b = document.createElement('b'); b.textContent = r.value; d.appendChild(b);
      var s = document.createElement('span'); s.textContent = r.label || ''; d.appendChild(s);
      tip.appendChild(d);
    });
    var x = (e.clientX || 0) + 14, y = (e.clientY || 0) + 14;
    tip.style.display = 'block';
    var w = tip.offsetWidth, hgt = tip.offsetHeight;
    if (x + w > innerWidth - 8) x = (e.clientX || 0) - w - 14;
    if (y + hgt > innerHeight - 8) y = (e.clientY || 0) - hgt - 14;
    tip.style.left = Math.max(4, x) + 'px'; tip.style.top = Math.max(4, y) + 'px';
  }
  function hideTip() { if (tip) tip.style.display = 'none'; }
  AA.hideTip = hideTip;
  AA.showTip = showTip;
  function nice(max) {
    if (max <= 0) return 4;
    var p = Math.pow(10, Math.floor(Math.log10(max))), f = max / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  }
  function frame(el, h, pad) {
    el.classList.add('aa-chart');
    var w = Math.max(260, el.clientWidth || 600);
    return { w: w, h: h, l: pad.l, r: pad.r, t: pad.t, b: pad.b, iw: w - pad.l - pad.r, ih: h - pad.t - pad.b };
  }
  function yAxis(f, max, fmt) {
    var top = nice(max), steps = 4, s = '';
    for (var i = 0; i <= steps; i++) {
      var v = top * i / steps, y = f.t + f.ih - f.ih * i / steps;
      s += '<line class="grid" x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + y + '" y2="' + y + '"/>' +
        '<text x="' + (f.l - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + (fmt ? fmt(v) : Math.round(v * 10) / 10) + '</text>';
    }
    return { svg: s, top: top };
  }
  function legend(series) {
    return series.length < 2 ? '' : '<div class="aa-legend">' + series.map(function (s) {
      return '<span><i class="' + (s.kind || '') + '" style="background:' + s.color + '"></i>' + esc(s.name) + '</span>';
    }).join('') + '</div>';
  }
  function bindHits(el, items) {
    el.querySelectorAll('[data-hit]').forEach(function (h) {
      var it = items[+h.getAttribute('data-hit')];
      var on = function (e) {
        var r = h.getBoundingClientRect();
        showTip(e.clientX != null && e.type !== 'focus' ? e : { clientX: r.right, clientY: r.top }, it.head, it.rows);
        el.querySelectorAll('[data-mk="' + h.getAttribute('data-hit') + '"]').forEach(function (m) { m.classList.add('hov'); });
      };
      var off = function () { hideTip(); el.querySelectorAll('.hov').forEach(function (m) { m.classList.remove('hov'); }); };
      h.addEventListener('pointermove', on); h.addEventListener('focus', on);
      h.addEventListener('pointerleave', off); h.addEventListener('blur', off);
    });
  }
  function bar(x, y, w, h) {  // a column with a 4px rounded top, square at the baseline
    var r = Math.min(4, w / 2, h);
    if (h <= 0) return '';
    return 'M' + x + ',' + (y + h) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + h) + 'Z';
  }
  AA.chart = {};
  /* Columns. o: {data: [{label, value, head}], color, height, unit, labelEvery} */
  AA.chart.bars = function (el, o) {
    var f = frame(el, o.height || 200, { l: 34, r: 8, t: 12, b: 26 });
    var max = Math.max.apply(null, o.data.map(function (d) { return d.value; }).concat([1]));
    var ax = yAxis(f, max), slot = f.iw / o.data.length, bw = Math.min(24, slot * 0.62), items = [], s = ax.svg;
    o.data.forEach(function (d, i) {
      var h = f.ih * d.value / ax.top, x = f.l + slot * i + (slot - bw) / 2, y = f.t + f.ih - h;
      s += '<path class="mk" data-mk="' + i + '" d="' + bar(x, y, bw, h) + '" fill="' + (d.color || o.color || 'var(--ch-1)') + '"/>';
      if (!o.labelEvery || i % o.labelEvery === 0 || i === o.data.length - 1) s += '<text x="' + (f.l + slot * i + slot / 2) + '" y="' + (f.h - 8) + '" text-anchor="middle">' + esc(d.label) + '</text>';
      s += '<rect class="hit" data-hit="' + i + '" tabindex="0" x="' + (f.l + slot * i) + '" y="' + f.t + '" width="' + slot + '" height="' + f.ih + '"/>';
      items.push({ head: d.head || d.label, rows: [{ value: d.value, label: o.unit || '', color: d.color || o.color || 'var(--ch-1)' }] });
    });
    s += '<line class="axis" x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + (f.t + f.ih) + '" y2="' + (f.t + f.ih) + '"/>';
    el.innerHTML = '<svg viewBox="0 0 ' + f.w + ' ' + f.h + '" height="' + f.h + '" role="img" aria-label="' + esc(o.title || 'Bar chart') + '">' + s + '</svg>';
    bindHits(el, items);
  };
  /* Grouped columns. o: {data: [{label, values: [a, b]}], series: [{name, color}]} */
  AA.chart.grouped = function (el, o) {
    var f = frame(el, o.height || 210, { l: 34, r: 8, t: 12, b: 26 });
    var max = 1;
    o.data.forEach(function (d) { d.values.forEach(function (v) { max = Math.max(max, v); }); });
    var ax = yAxis(f, max), slot = f.iw / o.data.length, n = o.series.length, bw = Math.min(16, (slot * 0.7 - 2 * (n - 1)) / n), s = ax.svg, items = [];
    o.data.forEach(function (d, i) {
      var gx = f.l + slot * i + (slot - (bw * n + 2 * (n - 1))) / 2;
      d.values.forEach(function (v, k) {
        var h = f.ih * v / ax.top;
        s += '<path class="mk" data-mk="' + i + '" d="' + bar(gx + k * (bw + 2), f.t + f.ih - h, bw, h) + '" fill="' + o.series[k].color + '"/>';
      });
      s += '<text x="' + (f.l + slot * i + slot / 2) + '" y="' + (f.h - 8) + '" text-anchor="middle">' + esc(d.label) + '</text>';
      s += '<rect class="hit" data-hit="' + i + '" tabindex="0" x="' + (f.l + slot * i) + '" y="' + f.t + '" width="' + slot + '" height="' + f.ih + '"/>';
      items.push({ head: d.head || d.label, rows: d.values.map(function (v, k) { return { value: v, label: o.series[k].name, color: o.series[k].color }; }) });
    });
    s += '<line class="axis" x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + (f.t + f.ih) + '" y2="' + (f.t + f.ih) + '"/>';
    el.innerHTML = legend(o.series.map(function (x) { return { name: x.name, color: x.color }; })) +
      '<svg viewBox="0 0 ' + f.w + ' ' + f.h + '" height="' + f.h + '" role="img" aria-label="' + esc(o.title || 'Grouped bar chart') + '">' + s + '</svg>';
    bindHits(el, items);
  };
  /* Lines (crosshair). o: {x: [labels], series: [{name, color, values (null = no data), dashed}], height} */
  AA.chart.lines = function (el, o) {
    var f = frame(el, o.height || 200, { l: 34, r: 12, t: 12, b: 26 });
    var max = 1;
    o.series.forEach(function (sr) { sr.values.forEach(function (v) { if (v != null) max = Math.max(max, v); }); });
    var ax = yAxis(f, max), n = o.x.length, step = n > 1 ? f.iw / (n - 1) : 0, s = ax.svg, items = [];
    var X = function (i) { return f.l + step * i; }, Y = function (v) { return f.t + f.ih - f.ih * v / ax.top; };
    o.series.forEach(function (sr) {
      var d = '', started = false, last = null;
      sr.values.forEach(function (v, i) { if (v == null) return; d += (started ? 'L' : 'M') + X(i) + ',' + Y(v); started = true; last = i; });
      if (sr.area && last != null) s += '<path d="' + d + 'L' + X(last) + ',' + (f.t + f.ih) + 'L' + X(0) + ',' + (f.t + f.ih) + 'Z" fill="' + sr.color + '" opacity=".1"/>';
      s += '<path d="' + d + '" fill="none" stroke="' + sr.color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"' + (sr.dashed ? ' stroke-dasharray="5 5"' : '') + '/>';
      if (last != null && !sr.dashed) s += '<circle cx="' + X(last) + '" cy="' + Y(sr.values[last]) + '" r="5" fill="' + sr.color + '" stroke="var(--c-surface)" stroke-width="2"/>';
    });
    var every = Math.ceil(n / 7);
    o.x.forEach(function (lab, i) {
      if (i % every === 0 || i === n - 1) s += '<text x="' + X(i) + '" y="' + (f.h - 8) + '" text-anchor="middle">' + esc(lab) + '</text>';
      var w = n > 1 ? step : f.iw;
      s += '<rect class="hit" data-hit="' + i + '" tabindex="0" x="' + (X(i) - w / 2) + '" y="' + f.t + '" width="' + w + '" height="' + f.ih + '"/>';
      items.push({ head: lab, rows: o.series.filter(function (sr) { return sr.values[i] != null; }).map(function (sr) { return { value: sr.values[i], label: sr.name, color: sr.color }; }) });
    });
    s += '<line class="axis" x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + (f.t + f.ih) + '" y2="' + (f.t + f.ih) + '"/><line class="xhair" x1="0" x2="0" y1="' + f.t + '" y2="' + (f.t + f.ih) + '" style="display:none"/>';
    el.innerHTML = legend(o.series.map(function (x) { return { name: x.name, color: x.color, kind: x.dashed ? 'dash' : 'line' }; })) +
      '<svg viewBox="0 0 ' + f.w + ' ' + f.h + '" height="' + f.h + '" role="img" aria-label="' + esc(o.title || 'Line chart') + '">' + s + '</svg>';
    bindHits(el, items);
    var xh = el.querySelector('.xhair');
    el.querySelectorAll('[data-hit]').forEach(function (h) {
      h.addEventListener('pointerenter', function () { var i = +h.getAttribute('data-hit'); xh.setAttribute('x1', X(i)); xh.setAttribute('x2', X(i)); xh.style.display = ''; });
      h.addEventListener('pointerleave', function () { xh.style.display = 'none'; });
    });
  };
  /* Stacked areas (cumulative flow). o: {x: [labels], series: [{name, color, values}]} bottom series first. */
  AA.chart.stack = function (el, o) {
    var f = frame(el, o.height || 220, { l: 34, r: 12, t: 12, b: 26 });
    var n = o.x.length, tot = [];
    for (var i = 0; i < n; i++) tot.push(o.series.reduce(function (a, sr) { return a + sr.values[i]; }, 0));
    var ax = yAxis(f, Math.max.apply(null, tot.concat([1]))), step = n > 1 ? f.iw / (n - 1) : 0, s = ax.svg, items = [];
    var X = function (i) { return f.l + step * i; }, Y = function (v) { return f.t + f.ih - f.ih * v / ax.top; };
    var base = o.x.map(function () { return 0; });
    o.series.forEach(function (sr) {
      var top = base.map(function (b, i) { return b + sr.values[i]; });
      var d = 'M' + top.map(function (v, i) { return X(i) + ',' + Y(v); }).join('L') + 'L' + base.map(function (v, i) { return X(i) + ',' + Y(v); }).reverse().join('L') + 'Z';
      s += '<path d="' + d + '" fill="' + sr.color + '" opacity=".85" stroke="var(--c-surface)" stroke-width="2"/>';
      base = top;
    });
    var every = Math.ceil(n / 6);
    o.x.forEach(function (lab, i) {
      if (i % every === 0 || i === n - 1) s += '<text x="' + X(i) + '" y="' + (f.h - 8) + '" text-anchor="middle">' + esc(lab) + '</text>';
      s += '<rect class="hit" data-hit="' + i + '" tabindex="0" x="' + (X(i) - step / 2) + '" y="' + f.t + '" width="' + (step || f.iw) + '" height="' + f.ih + '"/>';
      items.push({ head: lab, rows: o.series.slice().reverse().map(function (sr) { return { value: sr.values[i], label: sr.name, color: sr.color }; }) });
    });
    el.innerHTML = legend(o.series.slice().reverse()) + '<svg viewBox="0 0 ' + f.w + ' ' + f.h + '" height="' + f.h + '" role="img" aria-label="' + esc(o.title || 'Cumulative flow') + '">' + s + '</svg>';
    bindHits(el, items);
  };
  /* Scatter. o: {points: [{x (ms), y, series index, head, label}], series: [{name, color}], refs: [{y, name}]} */
  AA.chart.scatter = function (el, o) {
    var f = frame(el, o.height || 220, { l: 34, r: 40, t: 12, b: 26 });
    var xs = o.points.map(function (p) { return p.x; }), x0 = Math.min.apply(null, xs.concat([Date.now() - 864e5 * 30])), x1 = Date.now();
    var max = Math.max.apply(null, o.points.map(function (p) { return p.y; }).concat((o.refs || []).map(function (r) { return r.y; })).concat([1]));
    var ax = yAxis(f, max), s = ax.svg, items = [];
    var X = function (v) { return f.l + f.iw * (v - x0) / ((x1 - x0) || 1); }, Y = function (v) { return f.t + f.ih - f.ih * v / ax.top; };
    (o.refs || []).forEach(function (r) {
      s += '<line x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + Y(r.y) + '" y2="' + Y(r.y) + '" stroke="var(--c-muted)" stroke-width="1" stroke-dasharray="4 4"/>' +
        '<text x="' + (f.l + f.iw + 4) + '" y="' + (Y(r.y) + 4) + '">' + esc(r.name) + '</text>';
    });
    o.points.forEach(function (p, i) {
      var c = o.series[p.s || 0].color;
      s += '<circle class="mk" data-mk="' + i + '" cx="' + X(p.x) + '" cy="' + Y(p.y) + '" r="5" fill="' + c + '" stroke="var(--c-surface)" stroke-width="2"/>' +
        '<circle class="hit" data-hit="' + i + '" tabindex="0" cx="' + X(p.x) + '" cy="' + Y(p.y) + '" r="12"/>';
      items.push({ head: p.head, rows: [{ value: p.y + ' d', label: p.label, color: c }] });
    });
    [0, 0.5, 1].forEach(function (k) {
      var t = x0 + (x1 - x0) * k;
      s += '<text x="' + (f.l + f.iw * k) + '" y="' + (f.h - 8) + '" text-anchor="' + (k === 0 ? 'start' : k === 1 ? 'end' : 'middle') + '">' + esc(UI.fmtDate(new Date(t).toISOString(), { day: 'numeric', month: 'short' })) + '</text>';
    });
    s += '<line class="axis" x1="' + f.l + '" x2="' + (f.l + f.iw) + '" y1="' + (f.t + f.ih) + '" y2="' + (f.t + f.ih) + '"/>';
    el.innerHTML = legend(o.series) + '<svg viewBox="0 0 ' + f.w + ' ' + f.h + '" height="' + f.h + '" role="img" aria-label="' + esc(o.title || 'Scatter') + '">' + s + '</svg>';
    bindHits(el, items);
  };
  AA.table = function (cols, rows) {
    return '<details class="aa-tv"><summary>Show as a table</summary><table class="aa-table"><thead><tr>' + cols.map(function (c) { return '<th>' + esc(c) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows.map(function (r) { return '<tr>' + r.map(function (v) { return '<td>' + esc(v) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table></details>';
  };
  /* Charts measure their box: redraw them when the window size changes. */
  var redraws = [];
  AA.onResize = function (fn) { redraws.push(fn); };
  var rt = null, lastW = innerWidth;
  window.addEventListener('resize', function () {
    if (Math.abs(innerWidth - lastW) < 40) return;
    lastW = innerWidth; clearTimeout(rt);
    rt = setTimeout(function () { redraws = redraws.filter(function (fn) { return fn() !== false; }); }, 200);
  });
  window.addEventListener('hashchange', function () { redraws = []; hideTip(); });
  AA.shortDate = function (iso) { return UI.fmtDate(iso, { day: 'numeric', month: 'short' }); };

  /* ---------------------------------------------------------------- d3 (self-hosted in assets/, loaded only by pages that chart with it) */
  AA.d3 = function () {
    if (window.d3) return Promise.resolve(window.d3);
    if (!AA._d3) {
      AA._d3 = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '_/theme/d3.v7.9.0.min.js';
        s.onload = function () { resolve(window.d3); };
        s.onerror = function () { AA._d3 = null; reject(new Error('The charts could not load. Check your connection and reload.')); };
        document.head.appendChild(s);
      });
    }
    return AA._d3;
  };

  /* ---------------------------------------------------------------- files: CSV in and out, downloads */
  AA.download = function (name, text, type) {
    var blob = new Blob([text], { type: (type || 'text/plain') + ';charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; a.style.display = 'none';
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  };
  AA.toCSV = function (rows) {
    return rows.map(function (r) {
      return r.map(function (v) { var s = v == null ? '' : String(v); return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(',');
    }).join('\r\n') + '\r\n';
  };
  /* RFC 4180 CSV -> array of rows (quoted fields, "" escapes, newlines inside quotes, a BOM, ; or , or tab). */
  AA.parseCSV = function (text) {
    text = String(text || '').replace(/^﻿/, '');
    var first = text.split(/\r?\n/)[0] || '', sep = ',';
    [';', '\t'].forEach(function (c) { if (first.split(c).length > first.split(sep).length) sep = c; });
    var rows = [], row = [], f = '', q = false, i = 0, n = text.length, ch;
    for (; i < n; i++) {
      ch = text[i];
      if (q) {
        if (ch === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; }
        else f += ch;
      } else if (ch === '"') q = true;
      else if (ch === sep) { row.push(f); f = ''; }
      else if (ch === '\n' || ch === '\r') { if (ch === '\r' && text[i + 1] === '\n') i++; row.push(f); rows.push(row); row = []; f = ''; }
      else f += ch;
    }
    if (f !== '' || row.length) { row.push(f); rows.push(row); }
    return rows.filter(function (r) { return r.length > 1 || (r[0] || '').trim() !== ''; });
  };

  /* ---------------------------------------------------------------- the filter language
     The words you add cards with also find them: @name, #bug (type) or #label, !1 (priority), ~5 (points),
     >3 / <8 (points), +epic, is:blocked is:agent is:human is:mine is:unestimated is:ready, plain words (title, key). */
  AA.parseQuery = function (q) {
    var o = { words: [], who: [], tags: [], prio: [], pts: [], gt: null, lt: null, epic: [], is: [] };
    String(q || '').toLowerCase().split(/\s+/).forEach(function (w) {
      if (!w) return;
      var m;
      if (w[0] === '@' && w.length > 1) o.who.push(w.slice(1));
      else if (w[0] === '#' && w.length > 1) o.tags.push(w.slice(1));
      else if ((m = w.match(/^!p?([0-3])$/))) o.prio.push(+m[1]);
      else if ((m = w.match(/^~(\d{1,2})$/))) o.pts.push(+m[1]);
      else if ((m = w.match(/^>(\d{1,2})$/))) o.gt = +m[1];
      else if ((m = w.match(/^<(\d{1,2})$/))) o.lt = +m[1];
      else if (w[0] === '+' && w.length > 1) o.epic.push(w.slice(1));
      else if (w.indexOf('is:') === 0 && w.length > 3) o.is.push(w.slice(3));
      else o.words.push(w);
    });
    o.empty = !(o.words.length || o.who.length || o.tags.length || o.prio.length || o.pts.length || o.gt != null || o.lt != null || o.epic.length || o.is.length);
    return o;
  };
  AA.match = function (c, q, meId) {
    var o = typeof q === 'string' ? AA.parseQuery(q) : q;
    if (o.empty) return true;
    var hay = (c.key + ' ' + c.title).toLowerCase(), name = c.assignee ? c.assignee.name.toLowerCase().replace(/\s+/g, '') : '';
    var labels = (c.labels || []).map(function (l) { return l.toLowerCase(); }), epic = c.epic ? c.epic.title.toLowerCase().replace(/\s+/g, '') : '';
    if (!o.words.every(function (w) { return hay.indexOf(w) >= 0; })) return false;
    if (!o.who.every(function (w) { return w === 'me' ? (c.assignee && c.assignee.id === meId) : w === 'none' ? !c.assignee : name.indexOf(w) === 0; })) return false;
    if (!o.tags.every(function (t) { return c.type === t || labels.indexOf(t) >= 0; })) return false;
    if (o.prio.length && o.prio.indexOf(c.priority) < 0) return false;
    if (o.pts.length && o.pts.indexOf(c.points) < 0) return false;
    if (o.gt != null && !(c.points != null && c.points > o.gt)) return false;
    if (o.lt != null && !(c.points != null && c.points < o.lt)) return false;
    if (!o.epic.every(function (e) { return epic.indexOf(e) === 0; })) return false;
    return o.is.every(function (k) {
      if (k === 'blocked') return c.blocked;
      if (k === 'agent') return c.assignee && c.assignee.kind === 'agent';
      if (k === 'human') return c.assignee && c.assignee.kind === 'user';
      if (k === 'mine') return c.assignee && c.assignee.id === meId;
      if (k === 'unestimated') return c.points == null;
      if (k === 'ready') return c.agent_ready;
      return true;
    });
  };
  AA.queryHelp = 'Filter: words, @name, #bug or #label, !1, ~5, >3, +epic, is:blocked, is:agent, is:mine, is:unestimated';

  /* ---------------------------------------------------------------- command palette (Ctrl K, or / when not typing) */
  var GO = [['deck', 'Deck', 'deck', 'g d'], ['board', 'Board', 'board', 'g b'], ['backlog', 'Backlog', 'list', 'g l'], ['backlog/party', 'Estimation Party', 'gate', ''],
    ['plan', 'Plan', 'calendar', 'g p'], ['reports', 'Reports', 'chart', 'g r'], ['requests', 'Requests', 'flag', 'g q'], ['agents', 'AI agents', 'bot', 'g a'],
    ['insights', 'Insights', 'chart', 'g i'], ['crew', 'Crew settings', 'users', 'g s'], ['import', 'Import and export', 'layers', 'g x']];
  AA.palette = function () {
    if (!UI.me || document.querySelector('.aa-pal')) return;
    var crew = AA.current(), items = [], sel = 0, seq = 0;
    var m = UI.modal('<div class="aa-pal"><input type="text" data-pq placeholder="Jump to a page or card, or type a new card title..." aria-label="Search" autocomplete="off">' +
      '<div class="aa-pal-list" data-pl role="listbox"></div><p class="aa-pal-foot">↑↓ pick · Enter go · Esc close · ' +
      GO.filter(function (g) { return g[3]; }).map(function (g) { return '<kbd>' + g[3] + '</kbd> ' + esc(g[1]); }).join(' · ') + '</p></div>', { wide: true });
    var input = m.el.querySelector('[data-pq]'), list = m.el.querySelector('[data-pl]');
    function draw() {
      list.innerHTML = items.length ? items.map(function (it, i) {
        return '<button type="button" role="option" aria-selected="' + (i === sel) + '" class="' + (i === sel ? 'on' : '') + '" data-pi="' + i + '">' +
          '<span class="ic">' + (it.key ? '<span class="key">' + esc(it.key) + '</span>' : UI.icon(it.icon || 'zap')) + '</span><span class="tx">' + esc(it.label) + '</span>' +
          (it.hint ? '<span class="hint">' + esc(it.hint) + '</span>' : '') + '</button>';
      }).join('') : '<p class="muted small" style="padding:10px">Nothing found.</p>';
      var on = list.querySelector('.on'); if (on && on.scrollIntoView) on.scrollIntoView({ block: 'nearest' });
    }
    function build(cards) {
      var q = input.value.trim(), lq = q.toLowerCase();
      items = GO.filter(function (g) { return !lq || g[1].toLowerCase().indexOf(lq) >= 0; }).map(function (g) { return { label: g[1], icon: g[2], go: g[0], hint: g[3] }; });
      (cards || []).forEach(function (c) { items.push({ key: c.key, label: c.title, hint: AA.STATUS[c.status], card: c.key }); });
      if (q.length >= 3 && crew) items.push({ label: 'New card: ' + q, icon: 'plus', add: q, hint: crew.key + ' backlog' });
      if (lq.indexOf('crew') >= 0 || lq.indexOf('switch') >= 0) items.push({ label: 'Switch crew', icon: 'users', sw: true });
      sel = Math.min(sel, Math.max(0, items.length - 1));
      draw();
    }
    var t = null;
    input.addEventListener('input', function () {
      sel = 0; build([]);
      clearTimeout(t);
      var q = input.value.trim(), my = ++seq;
      if (!q || !crew) return;
      t = setTimeout(function () { UI.apiQuiet('search_cards', crew.id, q).then(function (r) { if (my === seq) build(r.cards); }, function () {}); }, 160);
    });
    function run(it) {
      if (!it) return;
      m.close();
      if (it.go) UI.go.apply(null, it.go.split('/'));
      else if (it.card) UI.go('card', it.card);
      else if (it.sw) AA.loadCrews().then(AA.switcher);
      else if (it.add) UI.api('quick_add', crew.id, it.add).then(function (r) { UI.toast(r.card.key + ' added to the backlog', 'ok'); UI.go('card', r.card.key); });
    }
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); draw(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
      else if (e.key === 'Enter') { e.preventDefault(); run(items[sel]); }
    });
    list.addEventListener('click', function (e) { var b = e.target.closest('[data-pi]'); if (b) run(items[+b.getAttribute('data-pi')]); });
    build([]);
    setTimeout(function () { input.focus(); }, 40);
  };
  var chord = null;
  document.addEventListener('keydown', function (e) {
    if (!UI.me) return;
    var tag = (e.target && e.target.tagName) || '', typing = /INPUT|TEXTAREA|SELECT/.test(tag) || (e.target && e.target.isContentEditable);
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); AA.palette(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector('.ui-modal-wrap, .ui-modal')) return;
    if (e.key === '/') { e.preventDefault(); AA.palette(); return; }
    if (chord && Date.now() - chord < 900) {
      var hit = GO.filter(function (g) { return g[3] === 'g ' + e.key.toLowerCase(); })[0];
      chord = null;
      if (hit) { e.preventDefault(); UI.go.apply(null, hit[0].split('/')); }
      return;
    }
    if (e.key === 'g') chord = Date.now();
  });

  /* ---------------------------------------------------------------- shared clicks */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-crew-switch],[data-card],[data-copy],[data-palette]');
    if (!el) return;
    if (el.hasAttribute('data-palette')) { e.preventDefault(); AA.palette(); return; }
    if (el.hasAttribute('data-crew-switch')) { e.preventDefault(); AA.loadCrews().then(AA.switcher); }
    else if (el.hasAttribute('data-card')) { if (el.closest('[data-nocardclick]')) return; e.preventDefault(); UI.go('card', el.getAttribute('data-card')); }
    else if (el.hasAttribute('data-copy')) {
      e.preventDefault();
      var src = document.querySelector(el.getAttribute('data-copy'));
      AA.copy(src ? (src.value != null && src.tagName !== 'PRE' ? src.value : src.textContent) : el.getAttribute('data-copy'));
    }
  });
})();

/* ===== admin.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['overview', 'Overview', 'grid'], ['feedback', 'Feedback', 'inbox'], ['users', 'Users', 'users'], ['crews', 'Crews', 'board'], ['demo', 'Demo data', 'database']];

  UI.page('admin', { title: 'Admin', auth: 'admin' }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'overview';
    var fbFilter = 'new';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Admin</h1><p class="muted">Only admins see this page.</p></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) {
        return '<a href="#admin/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>';
      }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function overview() {
      return UI.api('admin_overview').then(function (d) {
        var stat = function (n, label, go) { return '<a class="ui-card ui-stat" href="#admin/' + go + '" style="text-decoration:none;color:inherit"><b>' + n + '</b><span>' + label + '</span></a>'; };
        body.innerHTML = '<div class="ad-stats">' + stat(d.users, 'people signed up', 'users') + stat(d.admins, UI.plural(d.admins, 'admin').replace(/^\d+ /, ''), 'users') +
          stat(d.feedback_new, 'new feedback', 'feedback') + stat(d.crews, 'real crews', 'crews') + stat(d.cards, 'cards (all crews)', 'crews') + stat(d.agents, 'AI agents', 'crews') + '</div>' +
          '<p class="muted small" style="margin-top:18px">Demo data is <b>' + esc(d.demo.state) + '</b> (' + d.demo.counts.users + ' demo people). Manage it in the Demo data tab.</p>';
      });
    }

    function feedback() {
      return UI.api('list_feedback', null).then(function (d) {
        var items = d.items.filter(function (i) { return fbFilter === 'all' || i.status === fbFilter; });
        body.innerHTML = '<div class="ui-row" style="margin-bottom:16px"><div class="ui-seg">' + [['new', 'New'], ['read', 'Read'], ['done', 'Done'], ['all', 'All']].map(function (f) {
          var n = f[0] === 'all' ? d.items.length : d.counts[f[0]];
          return '<button data-filter="' + f[0] + '" class="' + (fbFilter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n + ')</button>';
        }).join('') + '</div></div>' +
          (items.length ? '<div class="ad-fb">' + items.map(function (i) {
            var c = i.context || {};
            return '<div class="ui-item" data-id="' + esc(i.id) + '"><div class="meta"><span class="ui-badge ' + (i.kind === 'bug' ? 'bad' : i.kind === 'idea' ? 'brand' : '') + '">' + esc(i.kind_label) + '</span>' +
              '<b>' + esc(i.name) + '</b>' + (i.email ? '<a href="mailto:' + esc(i.email) + '">' + esc(i.email) + '</a>' : '') + '<span>' + esc(UI.fmtDateTime(i.created)) + '</span></div>' +
              '<p class="msg">' + esc(i.message) + '</p>' +
              '<div class="ctx">' + esc([c.page, c.screen, c.theme, c.browser].filter(Boolean).join(' · ')) + '</div>' +
              '<textarea data-note placeholder="Private note (only admins see it)">' + esc(i.note) + '</textarea>' +
              '<div class="ui-row" style="margin-top:10px">' + ['new', 'read', 'done'].map(function (s) {
                return '<button class="ui-btn sm' + (i.status === s ? ' primary' : '') + '" data-status="' + s + '">' + s[0].toUpperCase() + s.slice(1) + '</button>';
              }).join('') + '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-del-fb>' + UI.icon('trash') + 'Delete</button></div></div>';
          }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No ' + (fbFilter === 'all' ? '' : fbFilter + ' ') + 'messages</h3><p>New feedback goes to Prepsto (prepsto.com). Older messages and requests from the app show up here.</p></div>');
      });
    }

    function users(query) {
      return UI.api('list_users', query || null).then(function (d) {
        body.innerHTML = '<form class="ui-row" data-search style="margin-bottom:14px"><input type="search" name="q" placeholder="Search by name or email" value="' + esc(query || '') + '" style="max-width:360px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'person', 'people') + '</span></form>' +
          '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Joined</th><th>Admin</th><th>Active</th></tr></thead><tbody>' +
          d.users.map(function (u) {
            return '<tr data-id="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b></td><td class="email">' + esc(u.email) + '</td><td class="joined muted">' + esc(UI.fmtDate(u.joined)) + '</td>' +
              '<td><label class="ui-check"><input type="checkbox" data-admin' + (u.is_admin ? ' checked' : '') + '> Admin</label></td>' +
              '<td><label class="ui-check"><input type="checkbox" data-enabled' + (u.enabled ? ' checked' : '') + '> Active</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    function demo() {
      return UI.api('admin_overview').then(function (d) {
        var c = d.demo.counts;
        body.innerHTML = '<div class="ui-card ui-narrow" style="margin:0"><h3>Demo data</h3>' +
          '<p class="muted">Example people and content, so the app never looks empty for the first visitors. Demo rows are flagged, so removing them never touches real data. Once removed, it stays removed until you load it again.</p>' +
          '<p>Status: <b>' + esc(d.demo.state) + '</b> · ' + Object.keys(c).map(function (k) { return c[k] + ' ' + esc(k); }).join(', ') + '</p>' +
          '<div class="ui-row"><button class="ui-btn primary" data-demo="load">' + UI.icon('refresh') + (d.demo.state === 'loaded' ? 'Reload demo data' : 'Load demo data') + '</button>' +
          '<button class="ui-btn danger" data-demo="remove">' + UI.icon('trash') + 'Remove demo data</button></div></div>';
      });
    }

    function crews() {
      return UI.api('admin_crews').then(function (d) {
        body.innerHTML = d.crews.length ? '<table class="ad-users"><thead><tr><th>Crew</th><th>Owner</th><th>Level</th><th>Size</th><th></th></tr></thead><tbody>' + d.crews.map(function (c) {
          return '<tr data-id="' + esc(c.id) + '"><td><b>' + esc(c.key) + '</b> ' + esc(c.name) + (c.demo ? ' <span class="ui-badge">demo</span>' : '') + '</td><td>' + esc(c.owner) + '</td><td>' + c.level + '</td>' +
            '<td class="joined muted">' + c.members + ' people · ' + c.agents + ' agents · ' + c.cards + ' cards</td><td>' + (c.demo ? '' : '<button class="ui-btn sm danger" data-delcrew>' + UI.icon('trash') + 'Delete</button>') + '</td></tr>';
        }).join('') + '</tbody></table>' : '<div class="ui-empty">' + UI.icon('board') + '<h3>No crews yet</h3></div>';
      });
    }

    var DRAW = { overview: overview, feedback: feedback, users: users, crews: crews, demo: demo };

    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { fbFilter = f.getAttribute('data-filter'); feedback(); return; }
      var st = e.target.closest('[data-status]');
      if (st) {
        var card = st.closest('[data-id]');
        UI.api('set_feedback_status', card.getAttribute('data-id'), st.getAttribute('data-status'), card.querySelector('[data-note]').value).then(function () { UI.toast('Saved', 'ok'); feedback(); });
        return;
      }
      var del = e.target.closest('[data-del-fb]');
      if (del) {
        UI.confirm({ title: 'Delete this message?', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_feedback', del.closest('[data-id]').getAttribute('data-id')).then(feedback);
        });
        return;
      }
      var dc = e.target.closest('[data-delcrew]');
      if (dc) {
        UI.confirm({ title: 'Delete this crew?', text: 'Every card, sprint, epic, agent and log in it is deleted. Use this for abuse or on request.', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('admin_delete_crew', dc.closest('[data-id]').getAttribute('data-id')).then(function () { UI.toast('Deleted', 'ok'); crews(); });
        });
        return;
      }
      var dm = e.target.closest('[data-demo]');
      if (dm) {
        var load = dm.getAttribute('data-demo') === 'load';
        UI.confirm({ title: load ? 'Load the demo data?' : 'Remove the demo data?', text: load ? 'Demo people and content are added (any old demo rows are replaced).' : 'Every demo row is deleted. Real data stays.', ok: load ? 'Load' : 'Remove', danger: !load })
          .then(function (yes) { if (yes) UI.busy(dm, UI.api(load ? 'demo_load' : 'demo_remove')).then(function () { UI.toast('Done', 'ok'); demo(); }); });
      }
    });
    view.addEventListener('change', function (e) {
      var row = e.target.closest('tr[data-id]');
      if (!row) return;
      var id = row.getAttribute('data-id'), box = e.target;
      var fn = box.hasAttribute('data-admin') ? 'set_admin' : box.hasAttribute('data-enabled') ? 'set_enabled' : null;
      if (fn) UI.api(fn, id, box.checked).then(function () { UI.toast('Saved', 'ok'); }, function (err) { box.checked = !box.checked; UI.toast(err.message, 'error'); });
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-search]')) { e.preventDefault(); users(UI.formData(e.target).q); }
    });
    return DRAW[tab]();
  });
})();

/* ===== agents.html ===== */
(function () {
  var esc = UI.esc;

  function snippet(base, crew) {
    return '## AutoAgile (task board)\n\nThis repo\'s work is tracked on AutoAgile, crew ' + crew.key + '. Your token is in the env var AUTOAGILE_TOKEN.\n' +
      'API: ' + base + '/agent/<op>, header "Authorization: Bearer $AUTOAGILE_TOKEN", JSON in and out.\n\n' +
      '1. GET  next     -> the best Ready card for you, with a markdown brief. Read the whole brief.\n' +
      '2. POST claim    {"key": "' + crew.key + '-12"} before you touch code.\n' +
      '3. POST log      {"key", "text"} at each milestone and whenever you are unsure (humans answer on the card).\n' +
      '4. POST check    {"key", "index", "done": true} as each acceptance criterion passes.\n' +
      '5. POST submit   {"key", "summary", "links": [{"label": "PR", "url": "..."}]} when tests pass. Never claim a second card while one is in Doing.\n' +
      '6. POST release  {"key", "reason"} if you get stuck or the card is wrong. POST propose {"title", "body", "type"} for follow-up work you notice.\n\n' +
      'Example: curl -s -H "Authorization: Bearer $AUTOAGILE_TOKEN" ' + base + '/agent/next\n';
  }
  function tokenModal(tok, agent, base, crew) {
    var m = UI.modal('<h2>Token for ' + esc(agent.name) + '</h2><p><b>Copy it now: it is shown only once.</b> We keep only a fingerprint of it. If it leaks, issue a new one (the old one stops working).</p>' +
      '<pre class="aa-pre" data-tok>' + esc(tok) + '</pre><div class="ui-row" style="margin:10px 0 16px"><button class="ui-btn primary sm" data-copy="[data-tok]">' + UI.icon('copy') + 'Copy token</button></div>' +
      '<p class="small muted">Give the agent the token as AUTOAGILE_TOKEN and this snippet in its instructions (CLAUDE.md, AGENTS.md, a system prompt):</p>' +
      '<pre class="aa-pre" data-snip>' + esc(snippet(base, crew)) + '</pre><div class="ui-row" style="margin-top:10px"><button class="ui-btn sm" data-copy="[data-snip]">' + UI.icon('copy') + 'Copy snippet</button>' +
      '<span class="ui-spacer"></span><button class="ui-btn" data-close>Done</button></div>', { wide: true });
    return m;
  }

  UI.page('agents', { title: 'AI agents', nav: 'Agents', icon: 'bot', auth: 'user', order: 50 }, function (view, ctx) {
    var d = null, crewRef = null, term = [], consoleAgent = UI.store.get('ag.console', null), hist = [], hi = -1;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';

    function termHtml() {
      return term.map(function (l) { return '<pre class="' + l.cls + '">' + esc(l.text) + '</pre>'; }).join('') ||
        '<pre class="dim">AutoAgile agent console. You are driving an agent through the same API it uses with its token.\nType "help", or try: next</pre>';
    }
    function draw() {
      var base = AA.apiBase(), crew = crewRef;
      var ag = d.agents, cur = ag.filter(function (a) { return a.id === consoleAgent; })[0] || ag.filter(function (a) { return a.active; })[0] || ag[0];
      consoleAgent = cur ? cur.id : null;
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="aa-head"><div><div class="eyebrow">Agents // ' + esc(d.crew.key) + '</div><h1>AI developers</h1><div class="sub">' + UI.plural(ag.length, 'agent') + ' · ' + d.agent_ready + ' Ready cards pass the agent checks · ' + d.review.length + ' agent cards in review</div></div>' +
        '<div class="ui-row"><button class="ui-btn primary" data-new>' + UI.icon('plus') + 'Add an agent</button></div></div>' + AA.demoNote(crew) +
        AA.win('How agents work in a crew', '<div class="ag-flow">' +
          '<div><b>Groom</b>Humans write criteria and run the gates. Cards that gate AGENT SOLO or AGENT + HUMAN and pass the Definition of Ready are fair game.</div>' +
          '<div><b>Pull</b>The agent asks for <code>next</code>: the top Ready card that fits it, with a full markdown brief.</div>' +
          '<div><b>Claim</b>It claims the card (its own WIP limit and the crew\'s Doing limit both apply) and logs as it works.</div>' +
          '<div><b>Hand in</b>It ticks criteria and submits with a summary and PR links. The card moves to Review.</div>' +
          '<div><b>Approve</b>A human reviews and moves it to Done. Agents never do. Review is where the WIP limit bites first.</div></div>', { cls: 'cyan' }) +
        (d.review.length ? '<div style="height:16px"></div>' + AA.win('Agent work waiting for you', '<div class="ag-grid">' + d.review.map(function (c) { return AA.card(c); }).join('') + '</div>', { cls: 'warn', extra: d.review.length }) : '') +
        '<div style="height:16px"></div><div class="ag-grid">' + (ag.map(function (a) {
          var led = { working: 'on blink', waiting: 'warn', idle: '', paused: 'bad' }[a.state];
          return AA.win(esc(a.kind), '<div class="ag-card" data-agent="' + esc(a.id) + '"><div class="hd">' + AA.who({ kind: 'agent', name: a.name, color: a.color }, 'lg') +
            '<div class="grow"><b>' + esc(a.name) + '</b><div class="small muted"><span class="aa-led ' + led + '"></span> ' + esc(a.state) + (a.last_seen ? ' · seen ' + esc(UI.ago(a.last_seen)) : ' · never connected') + '</div></div></div>' +
            '<div class="ag-stats">' + AA.lcd(a.wip + '<small>/' + a.max_wip + '</small>', 'Doing') + AA.lcd(a.in_review, 'Review', 'amber') + AA.lcd(a.done, 'Done', 'cyan') + '</div>' +
            '<div class="ag-cur">' + (a.current.map(function (c) { return '<a href="#card/' + esc(c.key) + '" data-card="' + esc(c.key) + '"><b>' + esc(c.key) + '</b> ' + esc(c.title) + ' <span class="faint">(' + esc(c.status) + ')</span></a>'; }).join('') ||
              '<span class="faint">No card right now.</span>') + '</div>' +
            '<p class="small muted" style="margin:0 0 10px">' + UI.icon('key') + ' ' + (a.has_token ? 'Token …' + esc(a.token_hint) : 'No token yet (demo agents run from the console)') + '</p>' +
            '<div class="ui-row"><button class="ui-btn sm" data-toggle>' + UI.icon(a.active ? 'pause' : 'play') + (a.active ? 'Pause' : 'Resume') + '</button>' +
            '<button class="ui-btn sm" data-token>' + UI.icon('key') + (a.has_token ? 'New token' : 'Get token') + '</button>' +
            '<button class="ui-btn sm" data-use>' + UI.icon('terminal') + 'Console</button>' +
            '<button class="ui-btn ghost icon" data-edit aria-label="Edit ' + esc(a.name) + '">' + UI.icon('edit') + '</button></div></div>', { cls: a.active ? '' : 'warn', extra: a.state });
        }).join('') || '<div class="ui-empty">' + UI.icon('bot') + '<h3>No agents yet</h3><p>Add Claude Code, Codex or your own bot. Each gets a token and a WIP limit.</p></div>') + '</div>' +
        '<div class="ag-two"><div>' +
          AA.win('Agent console', (cur ? '<div class="ag-chips"><select data-cagent aria-label="Drive which agent">' + ag.map(function (a) { return '<option value="' + esc(a.id) + '"' + (a.id === consoleAgent ? ' selected' : '') + '>' + esc(a.name) + '</option>'; }).join('') + '</select>' +
              ['help', 'whoami', 'next', 'cards ready', 'cards review'].map(function (c) { return '<button type="button" data-cmd="' + c + '">' + c + '</button>'; }).join('') + '<button type="button" data-cmd="__clear">clear</button></div>' +
              '<div class="ag-term" data-term aria-live="polite">' + termHtml() + '</div>' +
              '<form class="ag-prompt" data-prompt autocomplete="off"><label for="ag-in">' + esc(cur.name.replace(/\s+/g, '').toLowerCase()) + '@' + esc(d.crew.key.toLowerCase()) + ' $</label>' +
              '<input id="ag-in" type="text" name="cmd" maxlength="2000" placeholder="next · claim ' + esc(d.crew.key) + '-12 · log ' + esc(d.crew.key) + '-12 text · submit ' + esc(d.crew.key) + '-12 summary" spellcheck="false"></form>'
            : '<p class="muted" style="padding:16px">Add an agent to try the console.</p>'), { flush: true, extra: 'live' }) +
          '<div style="height:16px"></div>' +
          AA.win('House rules (in every brief)', '<form data-rules class="ui-stack"><textarea name="rules" rows="5" maxlength="3000">' + esc(d.rules) + '</textarea>' +
            '<div class="ui-row end"><button class="ui-btn sm primary" type="submit">Save rules</button></div></form>', { cls: 'lime' }) +
        '</div><div>' +
          AA.win('HTTP API', '<p class="small" style="margin-top:0">Base: <code>' + esc(base) + '/agent/&lt;op&gt;</code><br>Auth: <code>Authorization: Bearer aa_…</code> (or <code>?token=</code>). JSON in, JSON out. ' +
              '<a href="' + esc(base) + '/agent/manifest" target="_blank" rel="noopener">Manifest</a></p><table class="ag-ops">' + d.ops.map(function (o) {
                return '<tr><td><span class="m">' + o.method + '</span> ' + esc(o.op) + '</td><td>' + esc(o.doc) + '</td></tr>';
              }).join('') + '</table><p class="small muted">Errors come back with a reason the agent can act on: 409 when a WIP limit or a claim conflicts, 423 when the agent is paused, 401 for a bad token.</p>' +
              '<pre class="aa-pre" style="margin-top:8px" data-curl>curl -s -H "Authorization: Bearer $AUTOAGILE_TOKEN" \\\n  ' + esc(base) + '/agent/next\n\ncurl -s -X POST -H "Authorization: Bearer $AUTOAGILE_TOKEN" \\\n  -d \'{"key":"' + esc(d.crew.key) + '-12"}\' ' + esc(base) + '/agent/claim</pre>', { cls: 'cyan' }) +
          '<div style="height:16px"></div>' +
          AA.win('CLAUDE.md snippet', '<p class="small muted" style="margin-top:0">Paste into the repo\'s CLAUDE.md or AGENTS.md so your coding agent knows how to work the board.</p><pre class="aa-pre" data-snip>' + esc(snippet(base, d.crew)) + '</pre>' +
            '<div class="ui-row" style="margin-top:10px"><button class="ui-btn sm" data-copy="[data-snip]">' + UI.icon('copy') + 'Copy snippet</button></div>') +
          '<div style="height:16px"></div>' +
          AA.win('Agent feed', d.feed.length ? d.feed.slice(0, 14).map(function (e) {
              return '<div class="small" style="padding:6px 0;border-bottom:1px dashed var(--c-line)"><b>' + esc(e.who.name) + '</b> ' + (e.card ? '<a href="#card/' + esc(e.card.key) + '" data-card="' + esc(e.card.key) + '">' + esc(e.card.key) + '</a> ' : '') +
                esc(e.text) + ' <span class="faint">' + esc(UI.ago(e.created)) + '</span></div>';
            }).join('') : '<p class="small muted">Nothing from agents yet.</p>') +
        '</div></div></div>';
      var t = view.querySelector('[data-term]'); if (t) t.scrollTop = t.scrollHeight;
    }
    function load() {
      return AA.withCrew(view, function (crew) {
        crewRef = crew;
        return UI.api('get_agents', crew.id).then(function (r) { d = r; draw(); });
      });
    }
    function run(cmd) {
      cmd = (cmd || '').trim();
      if (!cmd || !consoleAgent) return Promise.resolve();
      if (cmd === '__clear' || cmd === 'clear') { term = []; draw(); return Promise.resolve(); }
      hist.unshift(cmd); hi = -1;
      term.push({ cls: 'in', text: '$ ' + cmd });
      return UI.apiQuiet('agent_console', consoleAgent, cmd, AA.apiBase()).then(function (r) {
        if (r.lines) { term.push({ cls: '', text: r.lines.join('\n') }); }
        else {
          var res = r.result, txt;
          if (res.card && res.card.brief) {
            var brief = res.card.brief; delete res.card.brief;
            txt = JSON.stringify(res, null, 1) + '\n--- brief ---\n' + brief;
          } else txt = JSON.stringify(res, null, 1);
          term.push({ cls: res.ok ? 'ok' : 'err', text: txt });
        }
        if (term.length > 60) term = term.slice(-60);
        var focus = document.activeElement && document.activeElement.id === 'ag-in';
        return UI.apiQuiet('get_agents', crewRef.id).then(function (r2) { d = r2; draw(); if (focus) { var i = view.querySelector('#ag-in'); if (i) i.focus(); } });
      });
    }

    view.addEventListener('submit', function (e) {
      e.preventDefault();
      if (e.target.matches('[data-prompt]')) { var i = e.target.querySelector('input'); var v = i.value; i.value = ''; run(v); }
      if (e.target.matches('[data-rules]')) UI.busy(e.target.querySelector('[type=submit]'), UI.api('update_crew', crewRef.id, { agent_rules: UI.formData(e.target).rules })).then(function () { UI.toast('House rules saved', 'ok'); });
    });
    view.addEventListener('keydown', function (e) {
      if (e.target.id !== 'ag-in') return;
      if (e.key === 'ArrowUp' && hist.length) { hi = Math.min(hist.length - 1, hi + 1); e.target.value = hist[hi]; e.preventDefault(); }
      if (e.key === 'ArrowDown') { hi = Math.max(-1, hi - 1); e.target.value = hi < 0 ? '' : hist[hi]; e.preventDefault(); }
    });
    view.addEventListener('change', function (e) {
      if (e.target.matches('[data-cagent]')) { consoleAgent = e.target.value; UI.store.set('ag.console', consoleAgent); draw(); }
    });
    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-cmd]'))) { run(t.getAttribute('data-cmd')); return; }
      var box = e.target.closest('[data-agent]'), a = box && d.agents.filter(function (x) { return x.id === box.getAttribute('data-agent'); })[0];
      if (a && e.target.closest('[data-toggle]')) { UI.api('update_agent', a.id, { active: !a.active }).then(function () { UI.toast(a.name + (a.active ? ' paused' : ' resumed'), 'ok'); load(); }); return; }
      if (a && e.target.closest('[data-use]')) { consoleAgent = a.id; UI.store.set('ag.console', a.id); draw(); var i = view.querySelector('#ag-in'); if (i) { i.focus(); i.scrollIntoView({ block: 'center' }); } return; }
      if (a && e.target.closest('[data-token]')) {
        UI.confirm({ title: (a.has_token ? 'New token for ' : 'Token for ') + a.name + '?', text: a.has_token ? 'The old token stops working right away.' : 'The token is shown once.', ok: 'Issue token' }).then(function (y) {
          if (y) UI.api('rotate_token', a.id).then(function (r) { tokenModal(r.token, a, AA.apiBase(), d.crew); load(); });
        });
        return;
      }
      if (a && e.target.closest('[data-edit]')) {
        var m = UI.modal('<h2>Edit ' + esc(a.name) + '</h2><form class="ui-stack"><label class="ui-field"><span>Name</span><input type="text" name="name" maxlength="30" value="' + esc(a.name) + '" required></label>' +
          '<label class="ui-field"><span>Kind</span><select name="kind">' + d.kinds.map(function (k) { return '<option' + (k === a.kind ? ' selected' : '') + '>' + esc(k) + '</option>'; }).join('') + '</select></label>' +
          '<label class="ui-field"><span>Its own WIP limit</span><select name="max_wip">' + [1, 2, 3, 4, 5].map(function (n) { return '<option' + (n === a.max_wip ? ' selected' : '') + '>' + n + '</option>'; }).join('') + '</select></label>' +
          '<div class="ui-row end"><button type="button" class="ui-btn danger" data-remove>' + UI.icon('trash') + 'Remove</button><span class="ui-spacer"></span><button class="ui-btn primary" type="submit">Save</button></div></form>');
        m.el.querySelector('form').addEventListener('submit', function (ev) {
          ev.preventDefault();
          var v = UI.formData(ev.target); v.max_wip = +v.max_wip;
          UI.api('update_agent', a.id, v).then(function () { m.close(); load(); });
        });
        m.el.querySelector('[data-remove]').onclick = function () {
          UI.confirm({ title: 'Remove ' + a.name + '?', text: 'Its cards in Doing go back to Ready. Its log stays on the cards.', ok: 'Remove', danger: true }).then(function (y) {
            if (y) UI.api('delete_agent', a.id).then(function () { m.close(); load(); });
          });
        };
        return;
      }
      if (e.target.closest('[data-new]')) {
        var nm = UI.modal('<h2>Add an AI developer</h2><p class="muted">It joins the crew like a person: it can be assigned cards, it has a WIP limit, and everything it does shows on the cards.</p>' +
          '<form class="ui-stack"><label class="ui-field"><span>Name</span><input type="text" name="name" maxlength="30" required placeholder="Claude, Unit 303, Robo-Rita"></label>' +
          '<label class="ui-field"><span>Kind</span><select name="kind">' + d.kinds.map(function (k) { return '<option>' + esc(k) + '</option>'; }).join('') + '</select></label>' +
          '<label class="ui-field"><span>Its own WIP limit</span><select name="max_wip"><option>1</option><option>2</option><option>3</option></select><p class="ui-hint">One card at a time keeps reviews small. Raise it once reviews keep up.</p></label>' +
          '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('plus') + 'Add agent</button></div></form>');
        nm.el.querySelector('form').addEventListener('submit', function (ev) {
          ev.preventDefault();
          var v = UI.formData(ev.target);
          UI.busy(ev.target.querySelector('[type=submit]'), UI.api('create_agent', crewRef.id, v.name, v.kind, +v.max_wip)).then(function (r) {
            nm.close(); consoleAgent = r.agent.id; UI.store.set('ag.console', r.agent.id);
            tokenModal(r.token, r.agent, AA.apiBase(), d.crew); load();
          });
        });
      }
    });
    return load();
  });
})();

/* ===== auth.html ===== */
(function () {
  var esc = UI.esc;
  function pw(name, auto) {
    return '<div class="au-pw"><input type="password" name="' + name + '" autocomplete="' + auto + '" required minlength="8">' +
      '<button type="button" data-show>Show</button></div>';
  }
  UI.page('auth', { title: 'Sign in', auth: 'guest' }, function (view, ctx) {
    var mode = ['signup', 'reset'].indexOf(ctx.args[0]) >= 0 ? ctx.args[0] : 'login';
    function draw(msg, isErr) {
      var heading = { login: 'Welcome back', signup: 'Create your account', reset: 'Reset your password' }[mode];
      var sub = { login: 'Sign in to continue to ' + esc(UI.config.name) + '.', signup: 'It\'s free and takes a few seconds.',
        reset: 'We\'ll email you a link to choose a new password.' }[mode];
      view.innerHTML = '<div class="au-wrap"><div class="ui-card au-card">' +
        '<h1>' + heading + '</h1><p class="muted">' + sub + '</p>' +
        (mode !== 'reset' ? '<div class="ui-seg" role="tablist"><button type="button" data-mode="login" class="' + (mode === 'login' ? 'on' : '') + '">Sign in</button>' +
          '<button type="button" data-mode="signup" class="' + (mode === 'signup' ? 'on' : '') + '">Create account</button></div>' : '<div style="height:14px"></div>') +
        '<form class="ui-stack" data-form="' + mode + '" novalidate>' +
        (mode === 'signup' ? '<label class="ui-field"><span>Your name</span><input type="text" name="name" autocomplete="name" required maxlength="60"></label>' : '') +
        '<label class="ui-field"><span>Email</span><input type="email" name="email" autocomplete="email" required></label>' +
        (mode === 'login' ? '<label class="ui-field"><span>Password</span>' + pw('password', 'current-password') + '</label>' : '') +
        (mode === 'signup' ? '<label class="ui-field"><span>Password <em>(at least 8 characters)</em></span>' + pw('password', 'new-password') + '</label>' +
          (window.LegalKit ? '<div>' + LegalKit.consentField() + '</div>' : '') : '') +
        '<div data-msg role="alert"' + (msg ? ' class="' + (isErr ? 'ui-error' : 'ui-note') + '">' + esc(msg) : ' hidden>') + '</div>' +
        '<button class="ui-btn primary block" type="submit">' + { login: 'Sign in', signup: 'Create account', reset: 'Send the link' }[mode] + '</button></form>' +
        '<div class="au-links">' + (mode === 'login' ? '<a data-mode="reset">Forgot your password?</a>' : '<a data-mode="login">' + UI.icon('back') + ' Back to sign in</a>') +
        '<a href="#landing" data-go="landing">About ' + esc(UI.config.name) + '</a></div></div></div>';
      var first = view.querySelector('input');
      if (first && !msg) first.focus();
    }
    view.addEventListener('click', function (e) {
      var m = e.target.closest('[data-mode]');
      if (m) { e.preventDefault(); mode = m.getAttribute('data-mode'); history.replaceState(null, '', '#auth' + (mode === 'login' ? '' : '/' + mode)); draw(); return; }
      var s = e.target.closest('[data-show]');
      if (s) { var i = s.parentNode.querySelector('input'); i.type = i.type === 'password' ? 'text' : 'password'; s.textContent = i.type === 'password' ? 'Show' : 'Hide'; }
    });
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target, v = UI.formData(form);
      var problem = !/^\S+@\S+\.\S+$/.test(v.email || '') ? 'Please enter a valid email address.'
        : mode !== 'reset' && (v.password || '').length < (mode === 'signup' ? 8 : 1) ? (mode === 'signup' ? 'Please choose a password of at least 8 characters.' : 'Please enter your password.')
        : mode === 'signup' && (v.name || '').trim().length < 2 ? 'Please tell us your name.' : null;
      if (problem) { say(problem, true); return; }
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;  // the kit shows its own message
      UI.busy(form.querySelector('[type=submit]'), UI.auth(mode, v)).then(function (r) {
        if (mode === 'reset' || (r && !r.me)) { mode = 'login'; draw(r && r.message, false); restore({ email: v.email }); }
        else UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    });
    function say(msg, isErr) {
      var box = view.querySelector('[data-msg]');
      box.className = isErr ? 'ui-error' : 'ui-note'; box.textContent = msg; box.hidden = false;
    }
    function restore(v) {
      ['name', 'email'].forEach(function (k) { var i = view.querySelector('[name=' + k + ']'); if (i && v[k]) i.value = v[k]; });
    }
    draw();
  });
})();

/* ===== backlog.html ===== */
(function () {
  var esc = UI.esc;

  function row(c, i, d, firstPlanned) {
    return '<div class="bl-row" data-id="' + esc(c.id) + '"><span class="rk">' + (i + 1) + '</span><span class="ky">' + esc(c.key) + '</span>' +
      '<div class="tt"><a href="#card/' + esc(c.key) + '" data-card="' + esc(c.key) + '">' + (c.blocked ? '⛔ ' : '') + esc(c.title) + '</a>' +
      '<div class="meta">' + AA.type(c.type) + AA.prio(c.priority) + (c.epic ? '<span class="aa-dot" style="background:' + esc(c.epic.color) + '"></span>' + esc(c.epic.title) : '') +
      (c.labels || []).map(AA.label).join('') + (c.status === 'ready' ? '<span class="ui-badge good">ready</span>' : '') + '</div></div>' +
      '<span class="pt">' + AA.pts(c.points) + '</span>' +
      '<span class="ft">' + (c.fit ? AA.fit(c.fit) : (c.points == null ? '<button class="ui-btn sm" data-gate="' + esc(c.id) + '">' + UI.icon('gate') + 'Gates</button>' : '<span class="faint small">set by hand</span>')) +
      ' <span class="bl-ready" title="Definition of Ready for agents">' + c.ready + '/' + c.ready_total + '</span></span>' +
      '<span class="wh">' + AA.who(c.assignee) + '</span>' +
      '<span class="acts">' + (firstPlanned ? '<button class="ui-btn ghost" data-tosprint="' + esc(firstPlanned.id) + '" title="Add to ' + esc(firstPlanned.name) + '" aria-label="Add to ' + esc(firstPlanned.name) + '">' + UI.icon('arrow') + '</button>' : '') +
      '<button class="ui-btn ghost" data-rank="top" title="Move to the top" aria-label="Move to the top">' + UI.icon('top') + '</button>' +
      '<button class="ui-btn ghost" data-rank="up" title="Move up" aria-label="Move up">' + UI.icon('up') + '</button>' +
      '<button class="ui-btn ghost" data-rank="down" title="Move down" aria-label="Move down">' + UI.icon('down') + '</button></span></div>';
  }

  function sprintPanel(s, d) {
    var vel = d.velocity || 0, pts = s.cards_list.reduce(function (a, c) { return a + (c.points || 0); }, 0);
    var unest = s.cards_list.filter(function (c) { return c.points == null; }).length;
    var max = Math.max(pts, vel * 1.3, 1), over = vel && pts > vel * 1.1;
    var body = '<div class="bl-cap' + (over ? ' over' : '') + '"><span>' + pts + ' pts planned</span><span>velocity ' + (vel || '?') + '</span></div>' +
      '<div class="bl-capbar" title="Planned points against average velocity"><i class="' + (over ? 'over' : '') + '" style="width:' + Math.min(100, 100 * pts / max) + '%"></i>' +
      (vel ? '<b style="left:' + (100 * vel / max) + '%"></b>' : '') + '</div>' +
      (over ? '<p class="small" style="color:var(--c-bad);margin:6px 0 0">Over your velocity. Commit less, finish more.</p>' : '') +
      (unest ? '<p class="small muted" style="margin:6px 0 0">' + UI.plural(unest, 'card') + ' not estimated.</p>' : '') +
      '<div class="bl-sp-cards">' + (s.cards_list.map(function (c) {
        return '<div class="bl-sp-row" data-id="' + esc(c.id) + '"><span class="ky">' + esc(c.key) + '</span><a href="#card/' + esc(c.key) + '" data-card="' + esc(c.key) + '">' + esc(c.title) + '</a>' + AA.pts(c.points) +
          (s.state === 'planned' ? '<button class="ui-btn ghost icon" style="width:28px;min-height:28px" data-outsprint title="Back to the backlog" aria-label="Back to the backlog">' + UI.icon('x') + '</button>' : '') + '</div>';
      }).join('') || '<p class="small muted">Empty. Use the arrow on a backlog card to add it here.</p>') + '</div>' +
      (s.state === 'planned' ? '<div class="ui-row"><button class="ui-btn primary sm" data-start="' + esc(s.id) + '"' + (d.sprints.some(function (x) { return x.state === 'active'; }) ? ' disabled title="Close the running sprint first"' : '') + '>' +
        UI.icon('play') + 'Start sprint</button><button class="ui-btn sm danger" data-delsprint="' + esc(s.id) + '">Remove</button></div>'
        : '<a class="ui-btn sm" href="#plan" data-go="plan">Running · see the burndown</a>');
    return AA.win(esc(s.name) + (s.state === 'active' ? ' · running' : ' · planned'), (s.goal ? '<p style="margin:0 0 8px"><b>' + esc(s.goal) + '</b></p>' : '') + body,
      { cls: s.state === 'active' ? 'lime' : '', extra: AA.shortDate(s.start) + '–' + AA.shortDate(s.end) });
  }

  function party(view, crew) {
    return UI.api('get_backlog', crew.id).then(function (d) {
      var all = d.cards.concat([].concat.apply([], d.sprints.map(function (s) { return s.cards_list; })));
      var queue = all.filter(function (c) { return c.points == null && c.status !== 'done'; }), i = 0, done = 0, widget = null;
      function show() {
        if (i >= queue.length) {
          view.innerHTML = '<div class="ui-wrap"><div class="ui-empty" style="padding:56px 20px">' + AA.smiley(90) + '<h2>Backlog groomed</h2><p>' +
            (done ? UI.plural(done, 'card') + ' estimated. ' : '') + 'Nothing left without points.</p><div class="ui-row" style="justify-content:center">' +
            '<a class="ui-btn primary" href="#backlog" data-go="backlog">Back to the backlog</a></div></div></div>';
          if (done) AA.rave('GROOMED!', UI.plural(done, 'card') + ' through the gates');
          return;
        }
        var c = queue[i];
        view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Estimation party // ' + esc(crew.key) + '</div><h1>Through the gates</h1>' +
          '<div class="sub">Answer six questions; the ladder picks the points. No arguing about 3 versus 5.</div></div>' +
          '<div class="ui-row"><span class="pt-count">' + (i + 1) + ' / ' + queue.length + '</span><a class="ui-btn" href="#backlog" data-go="backlog">Done for now</a></div></div>' +
          '<div class="pt-stage">' + AA.win(esc(c.key), '<div class="pt-card">' + AA.type(c.type) + ' ' + AA.prio(c.priority) + '<h2>' + esc(c.title) + '</h2>' +
            (c.epic ? '<p class="small"><span class="aa-dot" style="background:' + esc(c.epic.color) + '"></span> ' + esc(c.epic.title) + '</p>' : '') +
            '<p class="small muted">' + UI.plural(c.acc_total, 'acceptance criterion', 'acceptance criteria') + '. <a href="#card/' + esc(c.key) + '" data-card="' + esc(c.key) + '">Open the card</a> to read or edit it.</p>' +
            '<p class="pt-keys">KEYS: 1-4 answer the next gate · ENTER save · S skip</p>' +
            '<div class="ui-row"><button class="ui-btn primary" data-save disabled>' + UI.icon('check') + 'Save &amp; next</button><button class="ui-btn" data-skip>Skip</button></div></div>', { cls: 'lime' }) +
            AA.win('Complexity gates', '<div data-gates></div>') + '</div></div>';
        var save = view.querySelector('[data-save]');
        widget = AA.gateWidget(view.querySelector('[data-gates]'), d.gates, c.gates || {}, function (a, s) { save.disabled = !s.complete; });
      }
      function saveIt() {
        if (!widget || !widget.score().complete) return;
        var c = queue[i];
        UI.busy(view.querySelector('[data-save]'), UI.api('estimate_card', c.id, widget.answers())).then(function (r) {
          done++; UI.toast(c.key + ': ' + r.gate.points + ' pts (' + r.gate.rung + ')', 'ok'); i++; show();
        });
      }
      view.addEventListener('click', function (e) {
        if (e.target.closest('[data-save]')) saveIt();
        if (e.target.closest('[data-skip]')) { i++; show(); }
      });
      function key(e) {
        if (!view.isConnected) { document.removeEventListener('keydown', key); return; }
        if (e.target.matches && e.target.matches('input, textarea, select') || document.querySelector('.ui-modal-wrap')) return;
        if (/^[1-4]$/.test(e.key) && widget) { widget.key(+e.key); e.preventDefault(); }
        else if (e.key === 'Enter') { e.preventDefault(); saveIt(); }
        else if (e.key === 's' || e.key === 'S') { i++; show(); }
      }
      document.addEventListener('keydown', key);
      show();
    });
  }

  UI.page('backlog', { title: 'Backlog', nav: 'Backlog', icon: 'list', auth: 'user', order: 30 }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';
    var filter = UI.store.get('bl.filter', 'all'), data = null, crewRef = null, q = '';
    if (ctx.args[0] === 'party') return AA.withCrew(view, function (crew) { return party(view, crew); });

    function draw() {
      var d = data, crew = crewRef;
      var cards = d.cards.filter(function (c) {
        if (filter === 'unest') return c.points == null;
        if (filter === 'agent') return c.agent_ready;
        if (filter === 'bugs') return c.type === 'bug';
        return true;
      }).filter(function (c) { return AA.match(c, q, UI.me && UI.me.id); });
      var unest = d.cards.filter(function (c) { return c.points == null; }).length;
      var est = d.cards.length - unest;
      var planned = d.sprints.filter(function (s) { return s.state === 'planned'; })[0] || null;
      var sprintOpts = d.sprints.map(function (s) { return '<option value="' + esc(s.id) + '">' + esc(s.name) + '</option>'; }).join('');
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="aa-head"><div><div class="eyebrow">Backlog // ' + esc(d.crew.key) + '</div><h1>Backlog</h1>' +
        '<div class="sub">' + UI.plural(d.cards.length, 'card') + ' · ' + est + ' estimated · ' + d.cards.filter(function (c) { return c.agent_ready; }).length + ' agent-ready</div></div>' +
        '<div class="ui-row"><a class="ui-btn" href="#import" data-go="import">' + UI.icon('upload') + 'Import</a><a class="ui-btn' + (unest ? ' primary' : '') + '" href="#backlog/party" data-go="backlog/party">' + UI.icon('gate') + 'Estimation party' + (unest ? ' (' + unest + ')' : '') + '</a></div></div>' +
        AA.demoNote(crew) +
        AA.win('Quick add', '<form class="bl-add" data-add autocomplete="off"><input type="text" name="text" maxlength="300" required placeholder="Fix login timeout #bug !1 ~3 @claude +chat" aria-label="New card">' +
          (sprintOpts && d.level >= 2 ? '<select name="sprint" aria-label="Add to"><option value="">To the backlog</option>' + sprintOpts + '</select>' : '') +
          '<button class="ui-btn primary" type="submit">' + UI.icon('plus') + 'Add</button></form>' +
          '<p class="bl-syntax"><code>#bug</code> type (story bug task spike chore) · <code>!0</code>-<code>!3</code> priority · <code>~5</code> points by hand · <code>@name</code> assign a person or agent · <code>+epic</code> link an epic · other <code>#words</code> become labels</p>',
          { cls: 'cyan' }) +
        (d.level >= 2 ? '<div class="bl-sprints">' + d.sprints.map(function (s) { return sprintPanel(s, d); }).join('') +
          (d.sprints.filter(function (s) { return s.state === 'planned'; }).length < 3 ? AA.win('Next sprint', '<p class="small muted">Velocity: <b>' + (d.velocity != null ? d.velocity + ' pts' : 'unknown yet') + '</b>' +
            (d.velocity_range ? ' (range ' + d.velocity_range[0] + '–' + d.velocity_range[2] + ')' : '') + '. Plan to it, not to hope.</p>' +
            '<form data-newsprint class="ui-stack"><input type="text" name="goal" maxlength="200" placeholder="Sprint goal (one sentence)"><button class="ui-btn sm" type="submit">' + UI.icon('plus') + 'Plan a sprint</button></form>') : '') +
          '</div>' : '') +
        '<div class="bl-bar"><div class="ui-seg" role="group" aria-label="Filter">' + [['all', 'All'], ['unest', 'Unestimated'], ['agent', 'Agent-ready'], ['bugs', 'Bugs']].map(function (f) {
          return '<button type="button" data-filter="' + f[0] + '" class="' + (filter === f[0] ? 'on' : '') + '">' + f[1] + '</button>';
        }).join('') + '</div><input type="search" data-q value="' + esc(q) + '" placeholder="Filter: @name #label !1 ~5 +epic is:blocked" aria-label="Filter cards" title="' + esc(AA.queryHelp) + '" style="max-width:320px;min-height:38px;padding:6px 10px">' +
        '<span class="faint small">Ranked: the top is next. ' + (planned ? 'The arrow adds a card to ' + esc(planned.name) + '.' : '') + '</span></div>' +
        (cards.length ? '<div class="bl-list"><div class="bl-row hd"><span>#</span><span>Key</span><span>Card</span><span>Pts</span><span>Fit · Ready</span><span>Who</span><span></span></div>' +
          cards.map(function (c, i) { return row(c, i, d, planned); }).join('') + '</div>'
          : '<div class="ui-empty">' + UI.icon('list') + '<h3>' + (d.cards.length ? 'Nothing matches' : 'The backlog is empty') + '</h3><p>Type a card in Quick add above.</p></div>') + '</div>';
    }
    function load() {
      return AA.withCrew(view, function (crew) {
        crewRef = crew;
        return UI.api('get_backlog', crew.id).then(function (d) { data = d; draw(); });
      });
    }
    view.addEventListener('input', function (e) {
      if (!e.target.matches('[data-q]')) return;
      q = e.target.value;
      var pos = e.target.selectionStart; draw();
      var qi = view.querySelector('[data-q]'); qi.focus(); qi.setSelectionRange(pos, pos);
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-add]')) {
        e.preventDefault();
        var v = UI.formData(e.target), btn = e.target.querySelector('[type=submit]');
        UI.busy(btn, UI.api('quick_add', crewRef.id, v.text, v.sprint || null)).then(function (r) {
          UI.toast(r.card.key + ' added', 'ok');
          return load().then(function () { var i = view.querySelector('[data-add] input'); if (i) i.focus(); });
        });
      }
      if (e.target.matches('[data-newsprint]')) {
        e.preventDefault();
        UI.busy(e.target.querySelector('[type=submit]'), UI.api('create_sprint', crewRef.id, UI.formData(e.target).goal)).then(function (r) { UI.toast(r.sprint.name + ' planned', 'ok'); load(); });
      }
    });
    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-filter]'))) { filter = t.getAttribute('data-filter'); UI.store.set('bl.filter', filter); draw(); return; }
      if ((t = e.target.closest('[data-rank]'))) {
        var id = t.closest('[data-id]').getAttribute('data-id'), how = t.getAttribute('data-rank');
        var list = data.cards, i = list.map(function (c) { return c.id; }).indexOf(id), before = null;
        if (how === 'top') before = list[0] && list[0].id !== id ? list[0].id : null;
        else if (how === 'up') before = i > 0 ? list[i - 1].id : null;
        else before = i + 2 < list.length ? list[i + 2].id : null;
        if ((how === 'top' || how === 'up') && !before) return;
        if (how === 'down' && i === list.length - 1) return;
        UI.api('rank_card', id, before).then(load);
        return;
      }
      if ((t = e.target.closest('[data-tosprint]'))) {
        UI.api('update_card', t.closest('[data-id]').getAttribute('data-id'), { sprint_id: t.getAttribute('data-tosprint') }).then(load);
        return;
      }
      if ((t = e.target.closest('[data-outsprint]'))) { UI.api('update_card', t.closest('[data-id]').getAttribute('data-id'), { sprint_id: null }).then(load); return; }
      if ((t = e.target.closest('[data-start]'))) {
        var sid = t.getAttribute('data-start');
        UI.busy(t, UI.api('start_sprint', sid)).then(function (r) {
          AA.rave('SPRINT ON', r.sprint.name + ': ' + r.sprint.points + ' points' + (r.unestimated ? ', ' + r.unestimated + ' unestimated' : ''));
          load();
        });
        return;
      }
      if ((t = e.target.closest('[data-delsprint]'))) {
        var did = t.getAttribute('data-delsprint');
        UI.confirm({ title: 'Remove this planned sprint?', text: 'Its cards go back to the backlog.', ok: 'Remove', danger: true }).then(function (y) { if (y) UI.api('delete_sprint', did).then(load); });
        return;
      }
      if ((t = e.target.closest('[data-gate]'))) {
        var cid = t.getAttribute('data-gate'), card = data.cards.filter(function (c) { return c.id === cid; })[0];
        var m = UI.modal('<h2>' + esc(card.key) + '</h2><p class="muted">' + esc(card.title) + '</p><div data-g></div><div class="ui-row end" style="margin-top:14px"><button class="ui-btn ghost" data-close>Cancel</button>' +
          '<button class="ui-btn primary" data-savegate disabled>Save points</button></div>', { wide: true });
        var sv = m.el.querySelector('[data-savegate]');
        var w = AA.gateWidget(m.el.querySelector('[data-g]'), data.gates, card.gates || {}, function (a, s) { sv.disabled = !s.complete; });
        sv.onclick = function () { UI.busy(sv, UI.api('estimate_card', cid, w.answers())).then(function (r) { m.close(); UI.toast(card.key + ': ' + r.gate.points + ' pts', 'ok'); load(); }); };
      }
    });
    return load();
  });
})();

/* ===== board.html ===== */
(function () {
  var esc = UI.esc;
  var LANES = [['none', 'No lanes'], ['people', 'Lanes: people'], ['epic', 'Lanes: epics'], ['priority', 'Lanes: priority'], ['type', 'Lanes: type']];
  var PRIO = ['P0 · critical', 'P1 · high', 'P2 · normal', 'P3 · low'];

  /* columns from the server; older replies only have stage columns */
  function boardColumns(d) {
    if (d.board_columns) return d.board_columns;
    return ['ready', 'doing', 'review', 'done'].map(function (s) { return { id: s, name: AA.STATUS[s], stage: s, limit: d.wip[s] || null, split: false, cards: d.columns[s] }; });
  }
  function laneOf(mode, c) {
    if (mode === 'people') return c.assignee ? (c.assignee.kind === 'agent' ? 'a:' : 'u:') + c.assignee.id : 'none';
    if (mode === 'epic') return c.epic ? c.epic.id : 'none';
    if (mode === 'priority') return String(c.priority);
    if (mode === 'type') return c.type;
    return 'all';
  }
  function lanesFor(mode, d, cards) {
    if (mode === 'none') return [{ key: 'all', name: null }];
    var out = [];
    if (mode === 'people') {
      d.people.forEach(function (p) { out.push({ key: (p.kind === 'agent' ? 'a:' : 'u:') + p.id, name: p.name, who: p }); });
      out.push({ key: 'none', name: 'Unassigned' });
    } else if (mode === 'epic') {
      d.epics.forEach(function (e) { out.push({ key: e.id, name: e.title, color: e.color }); });
      out.push({ key: 'none', name: 'No epic' });
    } else if (mode === 'priority') [0, 1, 2, 3].forEach(function (p) { out.push({ key: String(p), name: PRIO[p] }); });
    else AA.TYPES.forEach(function (t) { out.push({ key: t, name: t }); });
    var used = {};
    cards.forEach(function (c) { used[laneOf(mode, c)] = true; });
    return out.filter(function (l) { return used[l.key]; });
  }
  function laneFields(mode, key) {
    if (mode === 'people') return { assignee: key === 'none' ? null : { kind: key[0] === 'a' ? 'agent' : 'user', id: key.slice(2) } };
    if (mode === 'epic') return { epic_id: key === 'none' ? null : key };
    if (mode === 'priority') return { priority: +key };
    if (mode === 'type') return { type: key };
    return null;
  }

  UI.page('board', { title: 'Board', nav: 'Board', icon: 'board', auth: 'user', order: 20 }, function (view, ctx) {
    var data = null, filter = UI.store.get('bd.filter', 'all'), q = '', lanes = UI.store.get('bd.lanes', 'none'), phoneCol = UI.store.get('bd.pcol', null), crewRef = null;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';

    function visible(c) {
      if (filter === 'mine' && !(c.assignee && c.assignee.kind === 'user' && c.assignee.id === data.me)) return false;
      if (filter === 'agents' && !(c.assignee && c.assignee.kind === 'agent')) return false;
      if (filter === 'humans' && c.assignee && c.assignee.kind === 'agent') return false;
      return AA.match(c, q, data.me);
    }
    function draw() {
      var d = data, crew = crewRef, cols = boardColumns(d);
      if (!cols.some(function (c) { return c.id === phoneCol; })) phoneCol = (cols.filter(function (c) { return c.stage === 'doing'; })[0] || cols[0]).id;
      var all = [];
      cols.forEach(function (c) { c.cards.forEach(function (x) { all.push(x); }); });
      var shown = all.filter(visible), ls = lanesFor(lanes, d, shown);
      var head = d.sprint ? esc(d.sprint.name) + ' · ' + d.sprint.done_points + '/' + d.sprint.points + ' pts · ends ' + esc(AA.shortDate(d.sprint.end))
        : (d.level >= 2 ? 'No sprint running' : 'Kanban flow · pull, don\'t push');
      var banner = '';
      if (d.level >= 2 && !d.sprint) banner = '<div class="bd-banner"><span class="aa-led warn blink"></span><div class="grow"><b>No sprint is running.</b> <span class="muted">Showing everything in flow. Plan a sprint from the backlog to focus the board.</span></div><a class="ui-btn sm primary" href="#backlog" data-go="backlog">Plan a sprint</a></div>';
      else if (d.sprint && d.sprint.goal) banner = '<div class="bd-banner"><span class="aa-led on"></span><div class="grow"><span class="faint small">SPRINT GOAL</span><br><b>' + esc(d.sprint.goal) + '</b></div><a class="ui-btn sm" href="#reports/burnup" data-go="reports/burnup">Burn-up</a></div>';
      else if (d.level === 1) banner = '<div class="bd-banner"><span class="aa-led pink"></span><div class="grow small"><b>Level 1: KANBAN.</b> Pull the top Ready card, keep Doing under its limit, finish before you start. Sprints unlock when your flow is steady.</div><a class="ui-btn sm" href="#plan" data-go="plan">Level checks</a></div>';
      var colHead = function (c) {
        var over = c.limit && c.cards.length > c.limit;
        return '<header class="bd-col-head' + (over ? ' over' : '') + (phoneCol === c.id ? ' show' : '') + '"><span class="aa-led ' + (over ? 'bad blink' : c.cards.length ? 'on' : '') + '"></span>' +
          '<b>' + (c.split ? '<small>' + esc(AA.STATUS[c.stage]) + ' ›</small>' : '') + esc(c.name) + '</b><span class="n">' + c.cards.length + (c.limit ? '/' + c.limit : '') + '</span></header>';
      };
      var body = function (c, lane) {
        var cards = c.cards.filter(function (x) { return visible(x) && (lane.key === 'all' || laneOf(lanes, x) === lane.key); });
        return '<div class="bd-body' + (phoneCol === c.id ? ' show' : '') + '" data-drop="' + esc(c.id) + '" data-lane="' + esc(lane.key) + '" aria-label="' + esc(c.name) + '">' +
          (cards.map(function (x) { return AA.card(x, { drag: true }); }).join('') ||
            (lane.key === 'all' ? '<div class="bd-empty">' + (c.stage === 'ready' ? 'Nothing Ready. Groom the <a href="#backlog" data-go="backlog">backlog</a>.' : 'Empty') + '</div>' : '')) + '</div>';
      };
      var grid = '<div class="bd-scroll"><div class="bd-grid" style="--n:' + cols.length + '">' + cols.map(colHead).join('') + '</div>' +
        ls.map(function (lane) {
          var n = shown.filter(function (x) { return lane.key === 'all' || laneOf(lanes, x) === lane.key; }).length;
          return '<section class="' + (lane.name ? 'bd-lane' : '') + '">' + (lane.name ? '<h3 class="bd-lane-head">' + (lane.who ? AA.who(lane.who) : lane.color ? '<span class="aa-dot" style="background:' + esc(lane.color) + '"></span>' : '') +
            esc(lane.name) + ' <span class="c">' + n + '</span></h3>' : '') + '<div class="bd-grid" style="--n:' + cols.length + '">' + cols.map(function (c) { return body(c, lane); }).join('') + '</div></section>';
        }).join('') + (ls.length ? '' : '<div class="bd-empty" style="margin-top:12px">No cards match the filter.</div>') + '</div>';
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="aa-head"><div><div class="eyebrow">Board // ' + esc(d.crew.key) + '</div><h1>' + esc(d.crew.name) + '</h1><div class="sub">' + head + '</div></div>' +
        '<div class="ui-row"><a class="ui-btn" href="#crew" data-go="crew" title="Columns and WIP limits">' + UI.icon('settings') + 'Columns</a><a class="ui-btn" href="#backlog" data-go="backlog">' + UI.icon('list') + 'Backlog</a></div></div>' + AA.demoNote(crew) + banner +
        '<div class="bd-tools"><div class="ui-seg" role="group" aria-label="Show">' + [['all', 'All'], ['mine', 'Mine'], ['humans', 'Humans'], ['agents', 'Agents']].map(function (f) {
          return '<button type="button" data-filter="' + f[0] + '" class="' + (filter === f[0] ? 'on' : '') + '">' + f[1] + '</button>';
        }).join('') + '</div><input type="search" data-q placeholder="Filter: words @name #bug !1 ~5 +epic is:blocked" value="' + esc(q) + '" aria-label="Filter cards" title="' + esc(AA.queryHelp) + '">' +
        '<select data-lanes aria-label="Swimlanes">' + LANES.map(function (l) { return '<option value="' + l[0] + '"' + (lanes === l[0] ? ' selected' : '') + '>' + l[1] + '</option>'; }).join('') + '</select>' +
        '<span class="bd-hint">' + (q ? shown.length + ' of ' + all.length + ' cards match' : 'Ctrl K jumps anywhere · ' + (lanes !== 'none' ? 'drop a card in another lane to re-assign it' : 'lanes group the board by person, epic, priority or type')) + '</span></div>' +
        '<div class="ui-seg bd-phonetabs" role="tablist">' + cols.map(function (c) {
          return '<button type="button" data-pcol="' + esc(c.id) + '" class="' + (phoneCol === c.id ? 'on' : '') + '">' + esc(c.name) + ' ' + c.cards.length + '</button>';
        }).join('') + '</div>' + grid + '</div>';
    }
    function load() {
      return AA.withCrew(view, function (crew) {
        crewRef = crew;
        return UI.api('get_board', crew.id).then(function (d) { data = d; draw(); });
      });
    }

    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { filter = f.getAttribute('data-filter'); UI.store.set('bd.filter', filter); draw(); return; }
      var p = e.target.closest('[data-pcol]');
      if (p) { phoneCol = p.getAttribute('data-pcol'); UI.store.set('bd.pcol', phoneCol); draw(); }
    });
    view.addEventListener('change', function (e) {
      if (e.target.matches('[data-lanes]')) { lanes = e.target.value; UI.store.set('bd.lanes', lanes); draw(); }
    });
    view.addEventListener('input', function (e) {
      if (e.target.matches('[data-q]')) {
        q = e.target.value;
        var pos = e.target.selectionStart; draw();
        var qi = view.querySelector('[data-q]'); qi.focus(); qi.setSelectionRange(pos, pos);
      }
    });

    /* drag and drop: columns, and lanes (a different lane changes the lane's field) */
    var dragId = null, ph = document.createElement('div');
    ph.className = 'bd-ph';
    view.addEventListener('dragstart', function (e) {
      var c = e.target.closest('.aa-card');
      if (!c) return;
      dragId = c.getAttribute('data-id');
      c.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', dragId); } catch (err) {}
    });
    view.addEventListener('dragend', function (e) {
      var c = e.target.closest('.aa-card'); if (c) c.classList.remove('dragging');
      ph.remove(); view.querySelectorAll('.drop').forEach(function (x) { x.classList.remove('drop'); });
    });
    function beforeCard(body, y) {
      var cards = Array.prototype.slice.call(body.querySelectorAll('.aa-card:not(.dragging)'));
      for (var i = 0; i < cards.length; i++) { var r = cards[i].getBoundingClientRect(); if (y < r.top + r.height / 2) return cards[i]; }
      return null;
    }
    view.addEventListener('dragover', function (e) {
      var body = e.target.closest('[data-drop]');
      if (!body || !dragId) return;
      e.preventDefault();
      view.querySelectorAll('.drop').forEach(function (x) { if (x !== body) x.classList.remove('drop'); });
      body.classList.add('drop');
      var b = beforeCard(body, e.clientY);
      if (b) body.insertBefore(ph, b); else body.appendChild(ph);
    });
    view.addEventListener('drop', function (e) {
      var body = e.target.closest('[data-drop]');
      if (!body || !dragId) return;
      e.preventDefault();
      var to = body.getAttribute('data-drop'), lane = body.getAttribute('data-lane'), b = beforeCard(body, e.clientY), id = dragId;
      dragId = null; ph.remove();
      var cols = boardColumns(data), card = null, from = null;
      cols.forEach(function (c) { c.cards.forEach(function (x) { if (x.id === id) { card = x; from = c; } }); });
      if (!card) return;
      var target = cols.filter(function (c) { return c.id === to; })[0];
      var count = target.cards.length + (from.id === to ? 0 : 1);
      var ask = (from.id !== to && target.limit && count > target.limit) ? UI.confirm({ title: 'Over the WIP limit', text: target.name + ' allows ' + target.limit + ' cards. Stop starting, start finishing: are you sure?', ok: 'Move it anyway', danger: true }) : Promise.resolve(true);
      var fields = lane !== 'all' && lane !== laneOf(lanes, card) ? laneFields(lanes, lane) : null;
      ask.then(function (yes) {
        if (!yes) { draw(); return; }
        UI.api('move_card', id, to, b ? b.getAttribute('data-id') : null).then(function () {
          if (from.id !== to) UI.toast(card.key + ' → ' + target.name + (target.stage === 'done' && from.stage === 'review' ? ' (approved)' : ''), 'ok');
          return fields ? UI.api('update_card', id, fields).then(function () { UI.toast(card.key + ' moved to another lane', 'ok'); }) : null;
        }).then(load, load);
      });
    });
    return load();
  });
})();

/* ===== card.html ===== */
(function () {
  var esc = UI.esc;
  var PRIOS = [[0, 'P0 · drop everything'], [1, 'P1 · high'], [2, 'P2 · normal'], [3, 'P3 · someday']];

  UI.page('card', { title: function (a) { return a[0] || 'Card'; }, auth: 'user' }, function (view, ctx) {
    var key = (ctx.args[0] || '').toUpperCase(), st = null, crewRef = null, editing = false, gw = null, briefOpen = false;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';

    function evRow(e) {
      var agent = e.who.kind === 'agent';
      return '<div class="cd-ev ' + (agent ? 'agent ' : '') + esc(e.kind) + '">' + AA.who(e.who.kind === 'system' ? null : e.who) + '<div>' +
        '<div class="t">' + (e.kind === 'comment' || e.kind === 'agent_log' || e.kind === 'submit' ? '<b style="font-family:var(--font-body);font-size:.88rem">' + esc(e.who.name) +
          (e.kind === 'submit' ? ' handed in for review' : '') + '</b>\n' : '') + esc(e.text) + '</div>' +
        '<div class="m">' + esc(UI.fmtDateTime(e.created)) + ' · ' + esc(e.kind.replace('_', ' ')) + '</div></div></div>';
    }
    function draw() {
      var c = st.card, d = st, lvl = st.level;
      var peopleOpts = '<option value="">Nobody</option>' + d.people.map(function (p) {
        var v = p.kind + ':' + p.id, sel = c.assignee && c.assignee.kind === p.kind && c.assignee.id === p.id;
        return '<option value="' + esc(v) + '"' + (sel ? ' selected' : '') + '>' + (p.kind === 'agent' ? '🤖 ' : '') + esc(p.name) + (p.kind === 'agent' && p.active === false ? ' (paused)' : '') + '</option>';
      }).join('');
      var sel = function (name, opts, cur) {
        return '<select data-f="' + name + '">' + opts.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(cur) ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select>';
      };
      var ready = c.readiness;
      var g = c.gate || {};
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="cd-top"><a class="ui-btn ghost sm" href="#board" data-go="board">' + UI.icon('back') + 'Board</a><span class="cd-key">' + esc(c.key) + '</span>' + AA.type(c.type) + AA.prio(c.priority) +
        (c.fit ? AA.fit(c.fit) : '') + (c.blocked ? '<span class="ui-badge bad">⛔ blocked</span>' : '') + (c.demo ? '<span class="ui-badge">demo</span>' : '') + '<span class="ui-spacer"></span>' + AA.pts(c.points) + '</div>' +
        '<form data-titleform style="margin:10px 0 14px"><input class="cd-title" type="text" name="title" value="' + esc(c.title) + '" maxlength="200" aria-label="Title"></form>' +
        '<div class="cd-grid"><div class="cd-main">' +
          AA.win('Description', editing ? '<form data-bodyform class="ui-stack"><textarea name="body" rows="8" maxlength="8000" placeholder="What and why. Markdown-ish: # heading, - list, **bold**, `code`, [link](https://...)">' + esc(c.body) + '</textarea>' +
              '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-canceledit>Cancel</button><button class="ui-btn primary" type="submit">Save</button></div></form>'
            : (c.body ? AA.md(c.body) : '<p class="muted">No description yet. Agents need context: say what, why, and where in the code.</p>') +
              '<button class="ui-btn sm" data-edit>' + UI.icon('edit') + 'Edit</button>', { extra: c.body.length + ' chars' }) +
          AA.win('Acceptance criteria', '<div class="cd-acc">' + c.acceptance.map(function (a, i) {
              return '<label class="' + (a.done ? 'done' : '') + '"><input type="checkbox" data-acc="' + i + '"' + (a.done ? ' checked' : '') + '><span>' + esc(a.text) + '</span>' +
                '<button type="button" class="ui-btn ghost icon x" data-accdel="' + i + '" aria-label="Remove">' + UI.icon('x') + '</button></label>';
            }).join('') + '</div><form data-accform class="ui-row" style="margin-top:8px"><input type="text" name="text" maxlength="200" placeholder="Add a criterion: observable, testable" style="flex:1;min-width:180px">' +
            '<button class="ui-btn sm" type="submit">' + UI.icon('plus') + 'Add</button></form>', { cls: 'lime', extra: c.acc_done + '/' + c.acc_total }) +
          AA.win('Complexity gates', '<div data-gates></div><div class="ui-row end" style="margin-top:12px"><span class="small muted" style="flex:1">' +
              (c.points_src === 'manual' ? 'Points were set by hand. Running the gates replaces them.' : c.points_src === 'gates' ? 'Estimated with the gates.' : 'Not estimated yet.') + '</span>' +
              '<button class="ui-btn primary" data-savegates disabled>' + UI.icon('gate') + 'Save estimate</button></div>', { extra: c.points != null ? c.points + ' pts' + (g.rung ? ' // ' + g.rung : '') : 'unestimated' }) +
          AA.win('Agent brief', '<p class="small muted" style="margin-top:0">One markdown spec with the goal, criteria, gates, your Definition of Done and the crew\'s house rules. Paste it into any AI coding tool, or let an agent fetch it with its token.</p>' +
              '<div class="ui-row"><button class="ui-btn primary sm" data-brief="copy">' + UI.icon('copy') + 'Copy brief</button><button class="ui-btn sm" data-brief="show">' + (briefOpen ? 'Hide' : 'Preview') + '</button></div>' +
              '<div data-briefbox style="margin-top:10px"' + (briefOpen ? '' : ' hidden') + '></div>', { cls: 'cyan', extra: c.agent_ready ? '⚡ agent-ready' : ready.passed + '/' + ready.total + ' ready' }) +
          AA.win('Activity', '<form data-comment class="ui-stack" style="margin-bottom:10px"><textarea name="text" rows="2" maxlength="2000" placeholder="Comment, answer an agent\'s question, leave a review note"></textarea>' +
              '<div class="ui-row end"><button class="ui-btn sm primary" type="submit">' + UI.icon('chat') + 'Comment</button></div></form>' +
              '<div class="cd-tl">' + (d.events.map(evRow).join('') || '<p class="muted small">No activity yet.</p>') + '</div>', { extra: d.events.length }) +
        '</div><div class="cd-side">' +
          AA.win('Status', '<div class="cd-status" role="group" aria-label="Status">' + ['backlog', 'ready', 'doing', 'review', 'done'].map(function (s) {
              return '<button type="button" data-move="' + s + '" class="' + (c.status === s ? 'on' : '') + '">' + AA.STATUS[s] + '</button>';
            }).join('') + '</div>' + (c.status === 'review' ? '<button class="ui-btn primary block" style="margin-top:10px" data-move="done">' + UI.icon('check') + 'Approve → Done</button>' +
              '<button class="ui-btn block" style="margin-top:8px" data-move="doing">Send back to Doing</button>' : '') +
            '<dl class="aa-kv" style="margin-top:12px"><dt>Created</dt><dd>' + esc(UI.fmtDate(c.created)) + ' by ' + esc(c.created_by) + '</dd>' +
            (c.started ? '<dt>Started</dt><dd>' + esc(UI.fmtDateTime(c.started)) + '</dd>' : '') + (c.done_at ? '<dt>Done</dt><dd>' + esc(UI.fmtDateTime(c.done_at)) + '</dd>' : '') +
            (c.age != null && c.status !== 'done' ? '<dt>In column</dt><dd>' + (c.age < 1 ? Math.round(c.age * 24) + ' hours' : c.age + ' days') + '</dd>' : '') + '</dl>', { cls: 'lime' }) +
          AA.win('Details', '<div class="ui-stack">' +
            '<label class="ui-field"><span>Assignee</span><select data-f="assignee">' + peopleOpts + '</select></label>' +
            '<label class="ui-field"><span>Type</span>' + sel('type', AA.TYPES.map(function (t) { return [t, t[0].toUpperCase() + t.slice(1)]; }), c.type) + '</label>' +
            '<label class="ui-field"><span>Priority</span>' + sel('priority', PRIOS, c.priority) + '</label>' +
            '<label class="ui-field"><span>Epic</span>' + sel('epic_id', [['', 'None']].concat(d.epics.filter(function (e) { return e.status !== 'done' || (c.epic && c.epic.id === e.id); }).map(function (e) { return [e.id, e.title]; })), c.epic ? c.epic.id : '') + '</label>' +
            (lvl >= 2 ? '<label class="ui-field"><span>Sprint</span>' + sel('sprint_id', [['', 'Not in a sprint']].concat(d.sprints.map(function (s) { return [s.id, s.name + (s.state === 'active' ? ' (running)' : '')]; }))
              .concat(c.sprint && c.sprint.state === 'closed' ? [[c.sprint.id, c.sprint.name + ' (closed)']] : []), c.sprint ? c.sprint.id : '') + '</label>' : '') +
            '<label class="ui-field"><span>Points by hand</span>' + sel('points', [['', c.points_src === 'gates' ? 'From the gates (' + c.points + ')' : 'Not set']].concat([1, 2, 3, 5, 8, 13, 21].map(function (p) { return [p, p + ' pts']; })), c.points_src === 'manual' ? c.points : '') + '</label>' +
            '<label class="ui-field"><span>Labels <em>(comma separated)</em></span><input type="text" data-f="labels" value="' + esc(c.labels.join(', ')) + '" maxlength="160"></label>' +
            '<label class="ui-check"><input type="checkbox" data-f="blocked"' + (c.blocked ? ' checked' : '') + '> Blocked</label>' +
            (c.blocked ? '<input type="text" data-f="blocked_reason" value="' + esc(c.blocked_reason) + '" maxlength="200" placeholder="Blocked by what?">' : '') + '</div>') +
          AA.win('Agent readiness', '<div class="cd-ready">' + ready.checks.map(function (k) {
              return '<div><span class="aa-led ' + (k.ok ? 'on' : 'bad') + '"></span>' + esc(k.label) + '</div>';
            }).join('') + '</div><p class="small muted" style="margin:10px 0 0">' + (c.agent_ready ? '⚡ An agent can pick this up with <code>next</code>.' :
              'Agents only pull cards that pass every check and gate as AGENT SOLO or AGENT + HUMAN.') + '</p>', { cls: 'cyan', extra: ready.passed + '/' + ready.total }) +
          AA.win('Links', '<div class="cd-links">' + (c.links.map(function (l, i) {
              return '<span><a href="' + esc(l.url) + '" target="_blank" rel="noopener">' + UI.icon('link') + esc(l.label) + '</a><button class="ui-btn ghost icon" style="width:26px;min-height:26px" data-linkdel="' + i + '" aria-label="Remove link">' + UI.icon('x') + '</button></span>';
            }).join('') || '<p class="small muted" style="margin-top:0">PRs, designs, docs. Agents add their PRs when they hand in.</p>') + '</div>' +
            '<form data-linkform class="ui-stack"><input type="text" name="label" placeholder="Label (PR #12)" maxlength="60"><input type="text" name="url" placeholder="https://..." maxlength="400">' +
            '<button class="ui-btn sm" type="submit">' + UI.icon('plus') + 'Add link</button></form>') +
          '<button class="ui-btn danger" data-delete>' + UI.icon('trash') + 'Delete card</button>' +
        '</div></div></div>';
      var sv = view.querySelector('[data-savegates]');
      gw = AA.gateWidget(view.querySelector('[data-gates]'), d.gates, c.gates || {}, function (a, s) { sv.disabled = !s.complete; });
      if (briefOpen) showBrief();
    }
    function showBrief() {
      var box = view.querySelector('[data-briefbox]');
      return UI.api('agent_brief', st.card.id, AA.apiBase()).then(function (r) { box.innerHTML = '<pre class="aa-pre" data-brieftext>' + esc(r.markdown) + '</pre>'; box.hidden = false; return r.markdown; });
    }
    function setCard(r) { st.card = r.card; draw(); }
    function save(fields) { return UI.api('update_card', st.card.id, fields).then(function (r) { setCard(r); return reloadEvents(); }); }
    function reloadEvents() { return UI.api('get_card', crewRef.id, st.card.key).then(function (r) { st = r; draw(); }); }
    function load() {
      return AA.loadCrews().then(function (crews) {
        var prefix = key.split('-').slice(0, -1).join('-');
        var cur = AA.current(), match = (crews || []).filter(function (c) { return c.key === prefix; });
        if (match.length && (!cur || cur.key !== prefix)) { AA.setCrew(match[0].id); cur = match[0]; }
        if (!cur) { UI.go('crew', 'new'); return; }
        crewRef = cur;
        return UI.api('get_card', cur.id, key).then(function (r) { st = r; draw(); }, function (err) {
          view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('search') + '<h3>No card ' + esc(key) + '</h3><p>' + esc(err.message) + '</p><a class="ui-btn" href="#board" data-go="board">Back to the board</a></div></div>';
        });
      });
    }

    view.addEventListener('submit', function (e) {
      var f = e.target; e.preventDefault();
      if (f.matches('[data-titleform]')) { var t = f.querySelector('input').value.trim(); if (t !== st.card.title) save({ title: t }).then(function () { UI.toast('Saved', 'ok'); }); }
      if (f.matches('[data-bodyform]')) { editing = false; save({ body: f.querySelector('textarea').value }); }
      if (f.matches('[data-accform]')) {
        var txt = f.querySelector('input').value.trim(); if (!txt) return;
        save({ acceptance: st.card.acceptance.concat([{ text: txt, done: false }]) }).then(function () { var i = view.querySelector('[data-accform] input'); if (i) i.focus(); });
      }
      if (f.matches('[data-comment]')) {
        var v = f.querySelector('textarea').value.trim(); if (!v) return;
        UI.busy(f.querySelector('[type=submit]'), UI.api('add_comment', st.card.id, v)).then(reloadEvents);
      }
      if (f.matches('[data-linkform]')) {
        var lv = UI.formData(f);
        if (!/^https?:\/\//.test(lv.url)) { UI.toast('Links start with https://', 'error'); return; }
        save({ links: st.card.links.concat([{ label: lv.label, url: lv.url }]) });
      }
    });
    view.addEventListener('focusout', function (e) {
      if (e.target.matches('.cd-title') && e.target.value.trim() && e.target.value.trim() !== st.card.title) save({ title: e.target.value.trim() });
    });
    view.addEventListener('change', function (e) {
      var t = e.target;
      if (t.matches('[data-acc]')) {
        var acc = st.card.acceptance.map(function (a, i) { return i === +t.getAttribute('data-acc') ? { text: a.text, done: t.checked } : a; });
        save({ acceptance: acc }); return;
      }
      var f = t.getAttribute('data-f');
      if (!f) return;
      if (f === 'assignee') { var p = t.value.split(':'); save({ assignee: t.value ? { kind: p[0], id: p.slice(1).join(':') } : null }); }
      else if (f === 'priority') save({ priority: +t.value });
      else if (f === 'points') save({ points: t.value ? +t.value : null });
      else if (f === 'labels') save({ labels: t.value.split(',').map(function (x) { return x.trim(); }).filter(Boolean) });
      else if (f === 'blocked') save({ blocked: t.checked, blocked_reason: '' });
      else if (f === 'blocked_reason') save({ blocked: true, blocked_reason: t.value });
      else { var o = {}; o[f] = t.value || null; save(o); }
    });
    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-edit]')) { editing = true; draw(); var ta = view.querySelector('[data-bodyform] textarea'); if (ta) ta.focus(); return; }
      if (e.target.closest('[data-canceledit]')) { editing = false; draw(); return; }
      if ((t = e.target.closest('[data-accdel]'))) { e.preventDefault(); var i = +t.getAttribute('data-accdel'); save({ acceptance: st.card.acceptance.filter(function (_, k) { return k !== i; }) }); return; }
      if ((t = e.target.closest('[data-linkdel]'))) { var li = +t.getAttribute('data-linkdel'); save({ links: st.card.links.filter(function (_, k) { return k !== li; }) }); return; }
      if ((t = e.target.closest('[data-move]'))) {
        var to = t.getAttribute('data-move'); if (to === st.card.status) return;
        UI.api('move_card', st.card.id, to, false).then(function (r) {
          UI.toast(st.card.key + ' → ' + AA.STATUS[to] + (r.over_wip ? ' (over the WIP limit!)' : ''), r.over_wip ? 'error' : 'ok');
          return reloadEvents();
        });
        return;
      }
      if (e.target.closest('[data-savegates]')) {
        UI.busy(e.target.closest('[data-savegates]'), UI.api('estimate_card', st.card.id, gw.answers())).then(function (r) {
          UI.toast(r.gate.points + ' points // ' + r.gate.rung, 'ok'); return reloadEvents();
        });
        return;
      }
      if ((t = e.target.closest('[data-brief]'))) {
        if (t.getAttribute('data-brief') === 'show') { briefOpen = !briefOpen; if (briefOpen) showBrief(); else view.querySelector('[data-briefbox]').hidden = true; t.textContent = briefOpen ? 'Hide' : 'Preview'; }
        else UI.api('agent_brief', st.card.id, AA.apiBase()).then(function (r) { AA.copy(r.markdown, 'Brief copied: paste it into your AI tool'); });
        return;
      }
      if (e.target.closest('[data-delete]')) {
        UI.confirm({ title: 'Delete ' + st.card.key + '?', text: 'The card and its activity are deleted for the whole crew.', ok: 'Delete', danger: true }).then(function (y) {
          if (y) UI.api('delete_card', st.card.id).then(function () { UI.toast('Deleted', 'ok'); UI.go('backlog'); });
        });
      }
    });
    return load();
  });
})();

/* ===== crew.html ===== */
(function () {
  var esc = UI.esc;

  function startPage(view, mode) {
    var join = mode === 'join';
    view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Crew // ' + (join ? 'join' : 'new') + '</div><h1>' + (join ? 'Join a crew' : 'Start a crew') + '</h1>' +
      '<div class="sub">' + (join ? 'Ask a crew member for the 6-character code on their Crew page.' : 'A crew is one team with one board, humans and AI agents together.') + '</div></div>' +
      '<div class="ui-row"><a class="ui-btn" href="#crew/' + (join ? 'new' : 'join') + '" data-go="crew/' + (join ? 'new' : 'join') + '">' + (join ? 'Start a crew instead' : 'I have a code') + '</a></div></div>' +
      '<div class="cr-start">' + (join ? AA.win('Join with a code', '<form data-join class="ui-stack"><label class="ui-field"><span>Crew code</span><input type="text" name="code" maxlength="8" required placeholder="K7Q2XM" autocomplete="off" style="font:400 2rem/1 var(--font-lcd);letter-spacing:.3em;text-transform:uppercase"></label>' +
          '<button class="ui-btn primary" type="submit">' + UI.icon('key') + 'Join</button></form>', { cls: 'lime' })
        : AA.win('New crew', '<form data-create class="ui-stack">' +
          '<label class="ui-field"><span>Crew name</span><input type="text" name="name" maxlength="60" required placeholder="Nova FM, Pixel Bakery, Team Rocket"></label>' +
          '<label class="ui-field"><span>Card prefix <em>(2-5 letters: cards become PREFIX-1, PREFIX-2...)</em></span><input type="text" name="key" maxlength="5" placeholder="NOVA" style="text-transform:uppercase;font:400 1.4rem/1 var(--font-lcd);letter-spacing:.12em"></label>' +
          '<label class="ui-field"><span>Mission <em>(optional)</em></span><textarea name="mission" rows="2" maxlength="300" placeholder="What are you building, for whom?"></textarea></label>' +
          '<div class="ui-field cr-levelpick"><span>Where do you start?</span><div class="ui-choices">' +
            '<label class="ui-choice"><input type="radio" name="level" value="1" checked><span><b>LVL 1 · KANBAN</b><small>New crew, or new to agile. Recommended.</small></span></label>' +
            '<label class="ui-choice"><input type="radio" name="level" value="2"><span><b>LVL 2 · SCRUM</b><small>We already run sprints together.</small></span></label></div>' +
            '<p class="ui-hint">Quarter and year planning unlock from your own data, whatever you pick.</p></div>' +
          '<button class="ui-btn primary lg" type="submit">' + UI.icon('zap') + 'Start the crew</button></form>', { cls: 'lime' })) +
        AA.win('The four levels', '<div class="ui-stack">' +
          '<p style="margin:0"><b>1 · KANBAN.</b> <span class="muted">Young crews start here: a ranked backlog, a board, WIP limits. You learn your rhythm before you promise anything.</span></p>' +
          '<p style="margin:0"><b>2 · SCRUM.</b> <span class="muted">When 25 cards and 6 steady weeks are done: sprints with goals, planned against real velocity, and retros.</span></p>' +
          '<p style="margin:0"><b>3 · QUARTER.</b> <span class="muted">After 3 steady sprints: a 3-month forecast of epics with a confidence range.</span></p>' +
          '<p style="margin:0"><b>4 · YEAR.</b> <span class="muted">After 6 predictable sprints: a year roadmap in quarters, estimated from measured capacity.</span></p>' +
          '<p class="small" style="margin:0">' + AA.smiley(22) + ' Complexity gates estimate every card the same way, so points mean something by the time you plan a year.</p></div>', { cls: 'cyan' }) +
      '</div></div>';
    var nameI = view.querySelector('[name=name]'), keyI = view.querySelector('[name=key]'), touched = false;
    if (keyI) {
      keyI.addEventListener('input', function () { touched = true; });
      nameI.addEventListener('input', function () { if (!touched) keyI.value = nameI.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 4); });
    }
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target), btn = e.target.querySelector('[type=submit]');
      var p = e.target.matches('[data-create]') ? UI.api('create_crew', v.name, v.key, v.mission, +v.level) : UI.api('join_crew', v.code);
      UI.busy(btn, p).then(function (r) {
        return AA.loadCrews(true).then(function () {
          AA.setCrew(r.crew.id);
          AA.rave(join ? 'WELCOME IN' : 'CREW ONLINE', r.crew.key + ' // ' + r.crew.name);
          UI.go(join ? 'deck' : 'backlog');
        });
      });
    });
    return Promise.resolve();
  }

  function settings(view) {
    return AA.withCrew(view, function (crewSum) {
      return UI.api('get_crew', crewSum.id).then(function (r) {
        var c = r.crew;
        view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Crew // ' + esc(c.key) + '</div><h1>' + esc(c.name) + '</h1><div class="sub">Level ' + c.level + ' // ' +
          esc(c.level_info.name) + ' · you are ' + esc(c.role === 'sandbox' ? 'a guest in this demo crew' : 'the ' + c.role) + '</div></div>' +
          '<div class="ui-row"><a class="ui-btn" href="#crew/new" data-go="crew/new">' + UI.icon('plus') + 'New crew</a><a class="ui-btn" href="#crew/join" data-go="crew/join">' + UI.icon('key') + 'Join</a></div></div>' + AA.demoNote(c) +
          '<div class="cr-grid"><div class="ui-stack">' +
          AA.win('Crew', '<form data-basic class="ui-stack"><label class="ui-field"><span>Name</span><input type="text" name="name" maxlength="60" value="' + esc(c.name) + '"' + (c.can_admin ? '' : ' disabled') + '></label>' +
            '<label class="ui-field"><span>Mission</span><textarea name="mission" rows="2" maxlength="300"' + (c.can_admin ? '' : ' disabled') + '>' + esc(c.mission) + '</textarea></label>' +
            '<p class="small muted" style="margin:0">Card prefix: <b>' + esc(c.key) + '</b> (fixed once cards exist).</p>' +
            (c.can_admin ? '<div class="ui-row end"><button class="ui-btn primary sm" type="submit">Save</button></div>' : '<p class="small muted" style="margin:0">Only the owner changes these.</p>') + '</form>', { cls: 'lime' }) +
          (c.join_code ? AA.win('Invite people', '<p class="small muted" style="margin-top:0">Share this code. Anyone signed in can join with it on the Join page.</p><div class="ui-row"><span class="cr-code" data-code>' + esc(c.join_code) + '</span>' +
            '<button class="ui-btn sm" data-copy="[data-code]">' + UI.icon('copy') + 'Copy</button>' + (c.can_admin ? '<button class="ui-btn sm" data-newcode>' + UI.icon('refresh') + 'New code</button>' : '') + '</div>', { cls: 'cyan' }) : '') +
          AA.win('People', c.members.map(function (m) {
            return '<div class="cr-mem">' + AA.who({ kind: 'user', name: m.name }) + '<div class="grow"><b>' + esc(m.name) + '</b>' + (m.me ? ' <span class="faint small">(you)</span>' : '') +
              '<div class="small muted">' + esc(m.role) + (m.joined ? ' · joined ' + esc(UI.fmtDate(m.joined)) : '') + '</div></div>' +
              (c.can_admin && !m.me && !c.demo ? '<button class="ui-btn sm" data-owner="' + esc(m.id) + '">Make owner</button><button class="ui-btn sm danger" data-remove="' + esc(m.id) + '">Remove</button>' : '') + '</div>';
          }).join('') + c.agents.map(function (a) {
            return '<div class="cr-mem">' + AA.who({ kind: 'agent', name: a.name, color: a.color }) + '<div class="grow"><b>' + esc(a.name) + '</b> <span class="ui-badge">AI</span><div class="small muted">' + esc(a.kind) + ' · WIP ' + a.max_wip + '</div></div>' +
              '<a class="ui-btn sm" href="#agents" data-go="agents">Manage</a></div>';
          }).join(''), { extra: (c.members.length + c.agents.length) + ' total' }) +
          '</div><div class="ui-stack">' +
          AA.win('Flow rules', '<form data-flow class="ui-stack"><div class="ui-field"><span>WIP limits <em>(cards allowed per stage; agents respect these)</em></span><div class="cr-wip">' + ['ready', 'doing', 'review'].map(function (k) {
              return '<label class="ui-field"><span class="small">' + AA.STATUS[k] + '</span><input type="number" min="1" max="50" name="' + k + '" value="' + c.wip[k] + '"></label>';
            }).join('') + '</div></div>' +
            '<label class="ui-field"><span>Sprint length</span><select name="sprint_days">' + [[7, '1 week'], [14, '2 weeks'], [21, '3 weeks'], [28, '4 weeks']].map(function (o) {
              return '<option value="' + o[0] + '"' + (o[0] === c.sprint_days ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select></label>' +
            '<label class="ui-field"><span>Definition of Done <em>(one rule per line; every agent brief includes it)</em></span><textarea name="dod" rows="5" maxlength="1600">' + esc(c.dod.join('\n')) + '</textarea></label>' +
            '<div class="ui-row end"><button class="ui-btn primary sm" type="submit">Save flow rules</button></div></form>', { cls: 'cyan' }) +
          AA.win('Board columns', '<div data-cols></div>', { cls: 'lime', extra: c.columns.length + ' columns' }) +
          AA.win('Alerts', '<div data-alerts><div class="ui-skel" style="height:140px"></div></div>', { cls: 'warn' }) +
          AA.win('Requests, import, export', '<p class="small" style="margin-top:0">Give people outside the crew a link to ask for things, with an answer promise. ' +
            'Bring your Jira or Trello history in, and take everything out whenever you like.</p><div class="ui-row"><a class="ui-btn sm" href="#requests" data-go="requests">' + UI.icon('megaphone') + 'Request desk</a>' +
            '<a class="ui-btn sm" href="#import" data-go="import">' + UI.icon('upload') + 'Import and export</a></div>') +
          AA.win('Leave or delete', c.demo ? '<p class="small muted" style="margin:0">Demo crews are shared sandboxes. An admin can reset them from Admin → Demo data.</p>'
            : (c.role === 'owner' ? '<p class="small" style="margin-top:0">Deleting removes every card, sprint, epic, agent and log of this crew. Type <b>' + esc(c.key) + '</b> to confirm.</p>' +
              '<form data-delete class="ui-row"><input type="text" name="confirm" maxlength="5" placeholder="' + esc(c.key) + '" style="max-width:140px"><button class="ui-btn danger solid sm" type="submit">' + UI.icon('trash') + 'Delete crew</button></form>'
              : '<button class="ui-btn danger" data-leave>' + UI.icon('logout') + 'Leave this crew</button>'), { cls: 'warn' }) +
          '</div></div></div>';
        columnsEditor(view.querySelector('[data-cols]'), c);
        alertsPanel(view.querySelector('[data-alerts]'), c);
        view.addEventListener('submit', function (e) {
          e.preventDefault();
          var f = e.target, v = UI.formData(f), btn = f.querySelector('[type=submit]');
          if (f.matches('[data-basic]')) UI.busy(btn, UI.api('update_crew', c.id, { name: v.name, mission: v.mission })).then(function () { UI.toast('Saved', 'ok'); AA.loadCrews(true); });
          if (f.matches('[data-flow]')) UI.busy(btn, UI.api('update_crew', c.id, { wip: { ready: v.ready, doing: v.doing, review: v.review }, sprint_days: +v.sprint_days,
            dod: v.dod.split('\n').map(function (x) { return x.trim(); }).filter(Boolean) })).then(function () { UI.toast('Flow rules saved', 'ok'); });
          if (f.matches('[data-delete]')) {
            UI.confirm({ title: 'Delete ' + c.name + ' for good?', text: 'This cannot be undone.', ok: 'Delete', danger: true }).then(function (y) {
              if (y) UI.api('delete_crew', c.id, v.confirm).then(function () { UI.store.set('crew', null); return AA.loadCrews(true); }).then(function () { UI.toast('Crew deleted', 'ok'); UI.go('deck'); });
            });
          }
        });
        view.addEventListener('click', function (e) {
          var t;
          if (e.target.closest('[data-newcode]')) UI.confirm({ title: 'New join code?', text: 'The old code stops working.', ok: 'New code' }).then(function (y) { if (y) UI.api('new_join_code', c.id).then(function () { UI.refresh(); }); });
          if ((t = e.target.closest('[data-remove]'))) UI.confirm({ title: 'Remove this person?', text: 'Their cards become unassigned.', ok: 'Remove', danger: true }).then(function (y) { if (y) UI.api('remove_member', c.id, t.getAttribute('data-remove')).then(function () { UI.refresh(); }); });
          if ((t = e.target.closest('[data-owner]'))) UI.confirm({ title: 'Hand over the crew?', text: 'They become the owner and you become a member.', ok: 'Hand over' }).then(function (y) { if (y) UI.api('make_owner', c.id, t.getAttribute('data-owner')).then(function () { return AA.loadCrews(true); }).then(function () { UI.refresh(); }); });
          if (e.target.closest('[data-leave]')) UI.confirm({ title: 'Leave ' + c.name + '?', ok: 'Leave', danger: true }).then(function (y) {
            if (y) UI.api('leave_crew', c.id).then(function () { UI.store.set('crew', null); return AA.loadCrews(true); }).then(function () { UI.go('deck'); });
          });
        });
      });
    });
  }

  /* Board columns: a stage can have several columns; the server keeps stage order and at least one per stage. */
  function columnsEditor(el, c) {
    var cols = c.columns.map(function (x) { return Object.assign({}, x); }), STG = ['ready', 'doing', 'review', 'done'];
    function sortCols() { cols = STG.reduce(function (a, s) { return a.concat(cols.filter(function (x) { return x.stage === s; })); }, []); }
    function draw() {
      sortCols();
      el.innerHTML = '<p class="small muted" style="margin-top:0">Split a stage into steps, like Doing → Build and Test. Agents, level checks and reports keep working on the stage. ' +
        'A column\'s WIP limit counts only that column; the Flow rules limit counts the whole stage.</p>' + cols.map(function (x, i) {
          var sub = cols.filter(function (y) { return y.stage === x.stage; }).length > 1;
          return '<div class="cr-colrow' + (sub ? ' sub' : '') + '" data-i="' + i + '"><input type="text" data-cf="name" value="' + esc(x.name) + '" maxlength="20" aria-label="Column name">' +
            '<select data-cf="stage" aria-label="Stage">' + STG.map(function (s) { return '<option value="' + s + '"' + (x.stage === s ? ' selected' : '') + '>' + AA.STATUS[s] + ' stage</option>'; }).join('') + '</select>' +
            '<input type="number" data-cf="wip" min="1" max="50" value="' + (x.wip || '') + '" placeholder="WIP" aria-label="WIP limit for this column">' +
            '<button type="button" class="ui-btn sm ghost icon" data-cup aria-label="Move up"' + (i > 0 && cols[i - 1].stage === x.stage ? '' : ' disabled') + '>' + UI.icon('up') + '</button>' +
            '<button type="button" class="ui-btn sm ghost icon" data-cdel aria-label="Remove column"' + (sub ? '' : ' disabled') + '>' + UI.icon('x') + '</button></div>';
        }).join('') + '<div class="ui-row" style="margin-top:10px"><button type="button" class="ui-btn sm" data-cadd>' + UI.icon('plus') + 'Add a column</button>' +
        '<span class="ui-spacer"></span><button type="button" class="ui-btn sm primary" data-csave>Save columns</button></div>';
    }
    el.addEventListener('change', function (e) {
      var row = e.target.closest('[data-i]'), f = e.target.getAttribute('data-cf');
      if (!row || !f) return;
      var x = cols[+row.getAttribute('data-i')];
      x[f] = f === 'wip' ? (e.target.value ? +e.target.value : null) : e.target.value;
      if (f === 'stage') draw();
    });
    el.addEventListener('click', function (e) {
      var row = e.target.closest('[data-i]'), i = row ? +row.getAttribute('data-i') : -1, t;
      if (e.target.closest('[data-cadd]')) { cols.push({ id: '', name: 'Test', stage: 'doing', wip: null }); draw(); }
      else if (e.target.closest('[data-cup]') && i > 0) { t = cols[i - 1]; cols[i - 1] = cols[i]; cols[i] = t; draw(); }
      else if (e.target.closest('[data-cdel]') && i >= 0) { cols.splice(i, 1); draw(); }
      else if ((t = e.target.closest('[data-csave]'))) UI.busy(t, UI.api('save_columns', c.id, cols)).then(function (r) { cols = r.columns; draw(); UI.toast('Columns saved. The board follows.', 'ok'); });
    });
    draw();
  }

  /* Alerts: owner sets the webhook and what to send; every member can switch on an email digest for themselves. */
  function alertsPanel(el, c) {
    var KIND = { test: 'test' };
    function draw(a) {
      var s = a.settings;
      a.kinds.forEach(function (k) { KIND[k.id] = k.label; });
      el.innerHTML = (a.can_edit && !a.demo ? '<form data-alform class="ui-stack"><label class="ui-field"><span>Webhook <em>(Slack, Teams, Mattermost, Discord or your own server; https only)</em></span>' +
          '<input type="url" name="webhook" maxlength="500" value="' + esc(s.webhook) + '" placeholder="https://hooks.slack.com/services/..."></label>' +
          '<div class="cr-wip" style="grid-template-columns:repeat(2,minmax(0,1fr))"><label class="ui-field"><span class="small">Format</span><select name="format">' + a.formats.map(function (f) {
            return '<option value="' + f.id + '"' + (f.id === s.format ? ' selected' : '') + '>' + esc(f.label) + '</option>'; }).join('') + '</select></label>' +
          '<label class="ui-field"><span class="small">Review waits over (hours)</span><input type="number" name="review_hours" min="1" max="168" value="' + s.review_hours + '"></label></div>' +
          '<div class="ui-field"><span>Send an alert when</span><div class="cr-kinds">' + a.kinds.map(function (k) {
            return '<label class="ui-check"><input type="checkbox" name="k_' + k.id + '"' + (s.kinds[k.id] ? ' checked' : '') + '> ' + esc(k.label) + '</label>'; }).join('') + '</div></div>' +
          '<div class="ui-row end"><button type="button" class="ui-btn sm" data-altest>Send a test</button><button class="ui-btn sm primary" type="submit">Save alerts</button></div></form>'
        : '<p class="small muted" style="margin-top:0">' + (a.demo ? 'Demo crews keep an alert history but never send anything.' : 'The owner connects a webhook' + (s.webhook ? ' (one is connected).' : ' (none yet).')) + '</p>') +
        (a.member && !a.demo ? '<label class="ui-check" style="margin-top:12px"><input type="checkbox" data-notify' + (a.notify ? ' checked' : '') + '> Email me when something needs a human (one digest, never a flood)</label>' : '') +
        '<h3 style="margin:16px 0 4px;font-size:.8rem">Recent alerts</h3>' + (a.history.length ? a.history.slice(0, 8).map(function (h) {
          var sent = h.sent || {}, st = sent.skipped ? 'not sent: ' + sent.skipped : [sent.webhook ? 'webhook ' + sent.webhook : '', sent.email ? sent.email + ' email' + (sent.email === 1 ? '' : 's') : ''].filter(Boolean).join(' · ') || 'recorded';
          return '<div class="cr-al"><span class="when">' + esc(UI.ago(h.created)) + '</span><span>' + esc(h.text) + '</span><span class="st">' + esc(KIND[h.kind] || h.kind) + ' · ' + esc(st) + '</span></div>';
        }).join('') : '<p class="small muted">Nothing yet. Quiet is good.</p>');
    }
    function load() { return UI.api('get_alerts', c.id).then(draw); }
    el.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-alform]')) return;
      e.preventDefault(); e.stopPropagation();
      var f = e.target, v = UI.formData(f), kinds = {};
      f.querySelectorAll('input[name^=k_]').forEach(function (x) { kinds[x.name.slice(2)] = x.checked; });
      UI.busy(f.querySelector('[type=submit]'), UI.api('save_alerts', c.id, { webhook: v.webhook, format: v.format, review_hours: +v.review_hours, kinds: kinds }))
        .then(function () { UI.toast('Alert settings saved', 'ok'); load(); });
    });
    el.addEventListener('click', function (e) {
      var t = e.target.closest('[data-altest]');
      if (t) UI.busy(t, UI.api('test_alerts', c.id)).then(function () { UI.toast('Test sent. Check your channel.', 'ok'); load(); });
    });
    el.addEventListener('change', function (e) {
      if (e.target.matches('[data-notify]')) UI.api('set_notify', c.id, e.target.checked).then(function (r) { UI.toast(r.notify ? 'You will get alert emails for ' + c.key : 'Alert emails off', 'ok'); });
    });
    load();
  }

  UI.page('crew', { title: 'Crew', auth: 'user' }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:320px"></div></div>';
    if (ctx.args[0] === 'new' || ctx.args[0] === 'join') return startPage(view, ctx.args[0]);
    return settings(view);
  });
})();

/* ===== deck.html ===== */
(function () {
  var esc = UI.esc;
  function evRow(e) {
    return '<div class="dk-ev">' + AA.who(e.who.kind === 'system' ? null : e.who) + '<div><div class="t">' +
      (e.kind === 'comment' ? '<b>' + esc(e.who.name) + ':</b> ' : e.kind === 'agent_log' || e.kind === 'submit' ? '<b>' + esc(e.who.name) + (e.kind === 'submit' ? ' handed in' : ' logged') + ':</b> ' : '') +
      esc(e.text) + '</div><div class="m">' + esc(UI.ago(e.created)) + (e.card ? ' · <a href="#card/' + esc(e.card.key) + '" data-card="' + esc(e.card.key) + '">' + esc(e.card.key) + '</a>' : '') + '</div></div></div>';
  }
  function agentRow(a) {
    var led = { working: 'on blink', waiting: 'warn', idle: '', paused: 'bad' }[a.state] || '';
    return '<div class="dk-agent">' + AA.who({ kind: 'agent', name: a.name, color: a.color }, 'lg') + '<div class="grow"><b>' + esc(a.name) + '</b> <span class="faint small">' + esc(a.kind) + '</span>' +
      '<div class="cur">' + (a.current.length ? a.current.map(function (c) { return esc(c.key) + ' ' + esc(c.title); }).join(' · ') : (a.state === 'paused' ? 'Paused by the crew' : 'Waiting for a Ready card')) + '</div></div>' +
      '<span class="st"><span class="aa-led ' + led + '"></span> ' + esc(a.state) + '</span></div>';
  }

  UI.page('deck', { title: 'Deck', nav: 'Deck', icon: 'deck', auth: 'user', order: 10 }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:90px"></div><div class="ui-skel" style="height:320px;margin-top:16px"></div></div>';
    view.addEventListener('click', function (e) {
      var a = e.target.closest('[data-alert]');
      if (a) UI.go.apply(null, a.getAttribute('data-alert').split('/'));
    });
    return AA.withCrew(view, function (crew) {
      return UI.api('get_deck', crew.id).then(function (d) {
        var st = d.stats, mat = d.maturity, nx = mat.next;
        var first = ctx.me.name.split(' ')[0];
        var sub = 'LVL ' + d.level.n + ' // ' + d.level.name + (d.sprint ? ' · ' + esc(d.sprint.name) + ' ends ' + esc(AA.shortDate(d.sprint.end)) : '');
        var tick = d.ticker.map(function (e) { return e.who.name.toUpperCase() + ': ' + (e.card ? e.card.key + ' ' : '') + e.text; });
        var needs = d.review.concat(d.blocked.filter(function (b) { return !d.review.some(function (r) { return r.id === b.id; }); }));
        var lvl = '<div class="dk-lvl"><div class="now">' + AA.smiley(44) + '<div><span class="faint small">YOU ARE AT</span><br><b>LVL ' + d.level.n + ' ' + esc(d.level.name) + '</b></div></div>' +
          '<p class="small muted" style="margin:0">' + esc(d.level.blurb) + '</p>' +
          (nx ? '<div><div class="ui-row between small"><span>Next: <b>' + esc(nx.name) + '</b> (' + esc(nx.title) + ')</span><span class="muted">' + nx.passed + '/' + nx.total + ' checks</span></div>' +
            AA.meter(nx.pct, nx.total) + '</div>' + (nx.eligible ? '<a class="ui-btn primary sm" href="#plan" data-go="plan">' + UI.icon('zap') + 'Level up</a>' : '<a class="ui-btn sm" href="#plan" data-go="plan">See the checks</a>')
            : '<p class="small" style="margin:0"><span class="aa-led on"></span> Top level. Your crew plans a year ahead.</p><a class="ui-btn sm" href="#plan/year" data-go="plan/year">Open the roadmap</a>') + '</div>';
        view.innerHTML = '<div class="ui-wrap">' +
          '<div class="aa-head"><div><div class="eyebrow">Deck // ' + esc(crew.key) + '</div><h1>Hi ' + esc(first) + ', welcome to ' + esc(d.crew.name) + '</h1><div class="sub">' + sub + '</div></div>' +
          '<div class="ui-row"><a class="ui-btn" href="#backlog" data-go="backlog">' + UI.icon('plus') + 'Add cards</a><a class="ui-btn primary" href="#board" data-go="board">' + UI.icon('board') + 'Open the board</a></div></div>' +
          AA.demoNote(d.crew) + AA.ticker(tick) +
          '<div class="aa-lcds dk-lcds" style="margin-top:14px">' +
            '<div class="aa-lcd"><div class="dk-lcd-spark"><b>' + st.this_week + '</b>' + AA.spark(st.spark) + '</div><span>Cards done this week</span></div>' +
            AA.lcd(st.per_week, 'Avg per week (6 wk)', 'cyan') +
            AA.lcd(st.cycle == null ? '--' : st.cycle + '<small>d</small>', 'Cycle time (median)', 'pink') +
            AA.lcd(st.doing + '<small>/' + st.doing_limit + '</small>', 'In Doing (WIP)', st.doing > st.doing_limit ? 'red' : '') +
            AA.lcd(st.review + '<small>/' + st.review_limit + '</small>', 'Waiting for review', st.review > st.review_limit ? 'red' : 'amber') +
          '</div>' +
          '<div class="dk-grid"><div class="dk-col">' +
            AA.win('Needs a human', needs.length ? '<div class="dk-cards">' + needs.map(function (c) { return AA.card(c); }).join('') + '</div>'
              : '<div class="ui-empty" style="padding:24px">' + AA.smiley(40) + '<h3>All clear</h3><p class="small">Nothing waiting for review and nothing blocked.</p></div>',
              { cls: 'warn', extra: needs.length + ' waiting' }) +
            AA.win('Your cards', d.mine.length ? '<div class="dk-cards">' + d.mine.map(function (c) { return AA.card(c); }).join('') + '</div>'
              : '<div class="ui-empty" style="padding:24px">' + UI.icon('board') + '<h3>Nothing on your plate</h3><p class="small">Grab a Ready card from the board, or leave the small ones to the agents.</p>' +
                '<a class="ui-btn sm" href="#board" data-go="board">Go to the board</a></div>', { extra: d.mine.length }) +
            AA.win('Alerts', d.alerts.length ? d.alerts.map(function (a) {
              return '<button type="button" class="dk-alert" data-alert="' + esc(a.go) + '"><span class="aa-led ' + ({ bad: 'bad blink', warn: 'warn', good: 'on', info: 'pink' }[a.level] || '') + '"></span><span>' + esc(a.text) + '</span></button>';
            }).join('') : '<p class="muted small" style="margin:0"><span class="aa-led on"></span> No alerts. Smooth flow.</p>', { cls: 'cyan', extra: d.alerts.length }) +
          '</div><div class="dk-col">' +
            AA.win('Maturity', lvl, { cls: 'lime' }) +
            (d.requests ? AA.win('Requests', (d.requests.top.length ? d.requests.top.map(function (r) {
              return '<a class="dk-req" href="#requests" data-go="requests"><b>' + r.votes + '</b><span>' + esc(r.title) + '</span><em class="' + (r.overdue ? 'late' : '') + '">' +
                (r.overdue ? 'overdue' : r.due_in + 'd left') + '</em></a>';
            }).join('') : '<p class="muted small" style="margin:0">No open requests. Share your ask link so people outside the crew can ask.</p>') +
              '<a class="ui-btn sm" style="margin-top:10px" href="#requests" data-go="requests">' + UI.icon('megaphone') + 'Request desk</a>',
              { cls: d.requests.late ? 'warn' : '', extra: d.requests.open + ' open' + (d.requests.late ? ' · ' + d.requests.late + ' late' : '') }) : '') +
            (d.sprint ? AA.win(esc(d.sprint.name), '<div class="dk-sprint"><div class="goal">' + esc(d.sprint.goal || 'No goal set') + '</div>' +
              '<div class="pts">' + d.sprint.done_points + ' / ' + d.sprint.points + ' pts done · ends ' + esc(AA.shortDate(d.sprint.end)) + '</div><div data-burn style="margin-top:8px"></div></div>', { extra: 'burndown' }) : '') +
            AA.win('Agents', d.agents.length ? d.agents.map(agentRow).join('') + '<a class="ui-btn sm" style="margin-top:10px" href="#agents" data-go="agents">' + UI.icon('terminal') + 'Agent console</a>'
              : '<p class="muted small">No AI developers yet. Add one and give it a token.</p><a class="ui-btn sm" href="#agents" data-go="agents">' + UI.icon('plus') + 'Add an agent</a>', { cls: 'cyan', extra: d.agents.length }) +
            AA.win('Live feed', '<div class="dk-feed">' + (d.feed.map(evRow).join('') || '<p class="muted small">Quiet so far.</p>') + '</div>') +
          '</div></div></div>';
        if (d.sprint) {
          var b = d.sprint.burndown, el = view.querySelector('[data-burn]');
          var draw = function () {
            if (!el.isConnected) return false;
            AA.chart.lines(el, { height: 150, title: 'Sprint burndown', x: b.map(function (p) { return AA.shortDate(p.day); }),
              series: [{ name: 'Ideal', color: 'var(--c-faint)', values: b.map(function (p) { return p.ideal; }), dashed: true },
                       { name: 'Points left', color: 'var(--ch-1)', values: b.map(function (p) { return p.remaining; }), area: true }] });
          };
          draw(); AA.onResize(draw);
        }
      });
    });
  });
})();

/* ===== import.html ===== */
(function () {
  var esc = UI.esc;
  var SOURCES = [['jira', 'Jira CSV'], ['trello', 'Trello JSON'], ['csv', 'Any CSV'], ['autoagile', 'AutoAgile JSON']];
  var FIELDS = [['title', 'Title *'], ['body', 'Description'], ['status', 'Status'], ['type', 'Type'], ['priority', 'Priority'], ['points', 'Points'],
    ['labels', 'Labels'], ['assignee', 'Assignee'], ['epic', 'Epic'], ['created', 'Created'], ['started', 'Started'], ['done_at', 'Finished'], ['key', 'Key / ID'], ['url', 'Link']];
  var GUESS = {
    title: /^(summary|title|name|card name|task|task name|subject)$/i, body: /^(description|desc|body|details|notes|card description)$/i,
    status: /^(status|state|list|list name|column|stage|section)$/i, type: /^(type|issue type|kind|category|work item type)$/i, priority: /^priority$/i,
    points: /story ?points?|story point estimate|^points$|^estimate$|^effort$/i, labels: /^(labels?|tags?)$/i, assignee: /^(assignee|owner|assigned to|members|responsible)$/i,
    epic: /^(parent summary|epic|epic name|epic link summary|custom field \(epic name\))$/i, created: /^(created|created at|date created|creation date)$/i,
    started: /^(started|start date|started at|custom field \(start date\))$/i, done_at: /^(resolved|completed|completed at|done|date completed|closed|resolution date)$/i,
    key: /^(issue key|key|card id|id|task id)$/i, url: /^(url|link|card url|short url)$/i
  };
  var MON = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };

  function when(s) {
    s = String(s || '').trim();
    if (!s) return null;
    var m = s.match(/^(\d{1,2})\/([A-Za-z]{3})\/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})\s*(AM|PM)?)?/i);  // Jira: 12/Mar/24 3:14 PM
    if (m && MON[m[2].toLowerCase()] != null) {
      var y = +m[3] < 100 ? 2000 + (+m[3]) : +m[3], h = +(m[4] || 0);
      if (m[6]) { h = h % 12 + (m[6].toUpperCase() === 'PM' ? 12 : 0); }
      return new Date(Date.UTC(y, MON[m[2].toLowerCase()], +m[1], h, +(m[5] || 0))).toISOString();
    }
    var t = Date.parse(s.replace(' ', 'T'));
    if (isNaN(t)) t = Date.parse(s);
    return isNaN(t) ? null : new Date(t).toISOString();
  }
  function stageGuess(s) {
    s = String(s || '').toLowerCase();
    if (/done|closed|resolved|complete|shipped|released|fixed|finished|live/.test(s)) return 'done';
    if (/review|qa|test|verif|approv|accept/.test(s)) return 'review';
    if (/progress|doing|develop|\bdev\b|started|building|wip|active|working/.test(s)) return 'doing';
    if (/ready|selected|next|to ?do|planned|committed|up next|sprint/.test(s)) return 'ready';
    return 'backlog';
  }
  function prioGuess(s) {
    s = String(s || '').toLowerCase();
    if (/highest|blocker|urgent|p0/.test(s)) return 0;
    if (/high|critical|p1/.test(s)) return 1;
    if (/low|minor|trivial|p3|p4/.test(s)) return 3;
    return 2;
  }

  /* ---------------------------------------------------------------- readers: each returns {kind, headers?, rows?, items?, note} */
  function readCSV(text, kind) {
    var all = AA.parseCSV(text);
    if (all.length < 2) throw new Error('That file has no rows under the header line.');
    var headers = all[0].map(function (h) { return h.trim(); });
    return { kind: kind, headers: headers, rows: all.slice(1) };
  }
  function readTrello(text) {
    var b = JSON.parse(text);
    if (!b || !Array.isArray(b.cards) || !Array.isArray(b.lists)) throw new Error('This is not a Trello board export (Menu → Print, export and share → Export as JSON).');
    var lists = {}, members = {}, comments = {};
    b.lists.forEach(function (l) { lists[l.id] = l.name; });
    (b.members || []).forEach(function (m) { members[m.id] = m.fullName || m.username; });
    (b.actions || []).forEach(function (a) {
      if (a.type === 'commentCard' && a.data && a.data.card) (comments[a.data.card.id] = comments[a.data.card.id] || []).push({ who: a.memberCreator && a.memberCreator.fullName, text: a.data.text, created: a.date });
    });
    var items = b.cards.filter(function (c) { return !c.closed || stageGuess(lists[c.idList]) === 'done'; }).map(function (c) {
      var made = new Date(parseInt(String(c.id).slice(0, 8), 16) * 1000).toISOString(), list = lists[c.idList] || 'Unknown list';
      return { title: c.name, body: c.desc || '', src: list, type: (c.labels || []).some(function (l) { return /bug/i.test(l.name || ''); }) ? 'bug' : 'story',
        labels: (c.labels || []).map(function (l) { return l.name || l.color; }).filter(Boolean), assignee: (c.idMembers || []).map(function (id) { return members[id]; })[0] || '',
        created: made, done_at: stageGuess(list) === 'done' ? (c.dateLastActivity || null) : null, source: 'trello:' + c.id, url: c.shortUrl || c.url || '',
        comments: (comments[c.id] || []).reverse(), priority: 2 };
    });
    return { kind: 'trello', items: items, note: (b.name ? 'Board "' + b.name + '": ' : '') + items.length + ' cards (archived ones skipped unless in a done list).' };
  }
  function readAutoAgile(text) {
    var x = JSON.parse(text);
    if (!x || x.format !== 'autoagile-export') throw new Error('This is not an AutoAgile export.');
    var items = x.cards.map(function (c) {
      return { title: c.title, body: c.body, src: c.column || c.status, stage: c.status, type: c.type, priority: c.priority, points: c.points, gates: c.gates, acceptance: c.acceptance,
        labels: c.labels, epic: c.epic, assignee: c.assignee_kind === 'user' ? c.assignee : (c.assignee || ''), created: c.created, started: c.started, review_at: c.review_at,
        done_at: c.done_at, source: 'autoagile:' + c.key, comments: (c.comments || []).filter(function (m) { return m.kind === 'comment'; }) };
    });
    return { kind: 'autoagile', items: items, note: 'Export of ' + x.crew.name + ' (' + x.crew.key + '), ' + items.length + ' cards, made ' + UI.fmtDate(x.exported) + '.' };
  }

  /* CSV rows -> items with the person's field mapping (Jira extras: several Labels / Comment columns, epics by key) */
  function csvItems(p, map, linkBase) {
    var H = p.headers.map(function (h) { return h.toLowerCase(); });
    var idx = function (name) { var out = []; H.forEach(function (h, i) { if (name && h === name.toLowerCase()) out.push(i); }); return out; };
    var one = function (row, name) { var v = ''; idx(name).some(function (i) { if ((row[i] || '').trim()) { v = row[i].trim(); return true; } return false; }); return v; };
    var many = function (row, name) { var out = []; idx(name).forEach(function (i) { String(row[i] || '').split(p.kind === 'jira' ? /\s+/ : /[,;]/).forEach(function (x) { x = x.replace(/\s*\([a-z_]+\)$/, '').trim(); if (x) out.push(x); }); }); return out; };
    var epicByKey = {}, typeI = idx(map.type || 'Issue Type')[0], keyI = idx(map.key || 'Issue key')[0];
    if (p.kind === 'jira' && typeI != null) p.rows.forEach(function (r) { if (/^epic$/i.test(r[typeI] || '')) epicByKey[(r[keyI] || '').trim()] = one(r, map.title || 'Summary'); });
    return p.rows.filter(function (r) { return !(p.kind === 'jira' && typeI != null && /^epic$/i.test(r[typeI] || '')); }).map(function (r) {
      var key = one(r, map.key), epic = one(r, map.epic);
      if (!epic && p.kind === 'jira') { var link = one(r, 'Custom field (Epic Link)') || one(r, 'Parent'); epic = epicByKey[link] || ''; }
      var comments = p.kind === 'jira' ? idx('Comment').map(function (i) { return r[i]; }).filter(Boolean).map(function (c) {
        var parts = c.split(';'); return parts.length >= 3 ? { created: when(parts[0]), who: parts[1].length > 20 ? 'Jira user' : parts[1], text: parts.slice(2).join(';') } : { text: c };
      }) : [];
      return { title: one(r, map.title), body: one(r, map.body), src: one(r, map.status) || '(no status)', type: one(r, map.type), priority: map.priority ? prioGuess(one(r, map.priority)) : 2,
        points: one(r, map.points), labels: many(r, map.labels), assignee: one(r, map.assignee), epic: epic, created: when(one(r, map.created)), started: when(one(r, map.started)),
        done_at: when(one(r, map.done_at)), updated: when(one(r, 'Updated')), source: key ? (p.kind === 'jira' ? 'jira:' : 'csv:') + key : '',
        url: one(r, map.url) || (key && linkBase ? linkBase.replace(/\/?$/, '/') + key : ''), comments: comments };
    });
  }

  UI.page('import', { title: 'Import and export', auth: 'user' }, function (view, ctx) {
    var S = { src: UI.store.get('im.src', 'jira'), parsed: null, map: {}, smap: {}, history: true, epics: true, link: '', busy: false, result: null };
    var crew = null, cols = [];
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';

    function items() {
      if (!S.parsed) return [];
      var list = S.parsed.items || csvItems(S.parsed, S.map, S.link);
      return list.map(function (it) { return Object.assign({}, it, { status: S.smap[it.src] || 'backlog' }); });
    }
    function sources() {
      var c = {};
      (S.parsed.items || csvItems(S.parsed, S.map, S.link)).forEach(function (it) { c[it.src] = (c[it.src] || 0) + 1; });
      return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).map(function (k) { return [k, c[k]]; });
    }
    function guessStatuses() {
      var known = {};
      (S.parsed.items || []).forEach(function (it) { if (it.stage) known[it.src] = it.stage; });
      sources().forEach(function (s) {
        if (S.smap[s[0]]) return;
        var named = cols.filter(function (c) { return c.name.toLowerCase() === String(s[0]).toLowerCase(); })[0];
        var g = known[s[0]] || stageGuess(s[0]), byStage = cols.filter(function (c) { return c.stage === g; })[0];
        S.smap[s[0]] = named ? named.id : g === 'backlog' ? 'backlog' : (byStage ? byStage.id : g);
      });
    }
    function targetOptions(cur) {
      return '<option value="backlog"' + (cur === 'backlog' ? ' selected' : '') + '>Backlog</option>' + cols.map(function (c) {
        return '<option value="' + esc(c.id) + '"' + (cur === c.id ? ' selected' : '') + '>' + esc(c.name) + (c.name.toLowerCase() !== c.stage ? ' (' + esc(AA.STATUS[c.stage]) + ')' : '') + '</option>';
      }).join('');
    }
    function exportWin() {
      return AA.win('Take everything with you', '<p class="small" style="margin-top:0">No lock-in. Any member can download the whole crew at any time: cards with their history and comments, epics, sprints and retros, requests, settings. Import the JSON into another AutoAgile crew, or open the CSV in a spreadsheet or another tracker.</p>' +
        '<div class="ui-stack"><button class="ui-btn primary" data-exp="json">' + UI.icon('download') + 'Everything (JSON)</button><button class="ui-btn" data-exp="csv">' + UI.icon('download') + 'Cards as CSV</button><p class="small muted" style="margin:0">The CSV uses Jira-style column names, so other trackers read it too.</p></div>', { cls: 'cyan' });
    }
    function draw() {
      var p = S.parsed, its = p ? items() : [];
      var head = '<div class="aa-head"><div><div class="eyebrow">Import // ' + esc(crew.key) + '</div><h1>Import and export</h1><div class="sub">Bring your history. Leave whenever you like.</div></div>' +
        '<div class="ui-row"><a class="ui-btn" href="#backlog" data-go="backlog">' + UI.icon('list') + 'Backlog</a></div></div>';
      var demo = crew.demo ? '<div class="aa-demo-note"><b>DEMO CREW</b> // imports go into your own crews. <a href="#crew/new" data-go="crew/new">Start one</a>, then come back. You can still try reading a file here and export the demo.</div>' : '';
      var step1 = AA.win('1 · Pick a file', '<div class="ui-seg im-src" role="group" aria-label="Source" style="margin-bottom:12px">' + SOURCES.map(function (s) {
          return '<button type="button" data-src="' + s[0] + '" class="' + (S.src === s[0] ? 'on' : '') + '">' + s[1] + '</button>'; }).join('') + '</div>' +
        '<p class="small muted" style="margin-top:0">' + ({ jira: 'In Jira: Filters → your issues → Export → <b>Export CSV (all fields)</b>. Dates, labels, comments, epics and story points come along.',
          trello: 'In Trello: board Menu → Print, export and share → <b>Export as JSON</b>. Lists become columns; comments and labels come along.',
          csv: 'Any spreadsheet saved as CSV: Asana, monday.com, Linear, GitHub Projects, Podio, Notion. You choose which column is what.',
          autoagile: 'A file from Export below, from this or another AutoAgile crew.' })[S.src] + '</p>' +
        '<label class="im-drop" data-dropzone><input type="file" data-file accept=".csv,.json,.txt,text/csv,application/json" style="max-width:100%"><br><span class="small muted">or drop the file here</span></label>' +
        '<details style="margin-top:10px"><summary class="small">Paste instead</summary><textarea data-paste rows="5" placeholder="Paste CSV or JSON here" style="margin-top:8px"></textarea><button class="ui-btn sm" data-readpaste style="margin-top:8px">Read it</button></details>', { cls: 'lime' });
      var body = '';
      if (p) {
        var srcs = sources();
        body += AA.win('2 · Check what is what', (p.note ? '<p class="small" style="margin-top:0">' + esc(p.note) + '</p>' : '<p class="small" style="margin-top:0">' + its.length + ' cards found' + (p.kind === 'jira' ? ' (epics become AutoAgile epics)' : '') + '.</p>') +
          (p.headers ? '<div class="im-map">' + FIELDS.map(function (f) {
            return '<label for="im-' + f[0] + '">' + f[1] + '</label><select id="im-' + f[0] + '" data-map="' + f[0] + '"><option value="">(none)</option>' + p.headers.filter(function (h, i) { return h && p.headers.indexOf(h) === i; }).map(function (h) {
              return '<option' + (S.map[f[0]] === h ? ' selected' : '') + '>' + esc(h) + '</option>'; }).join('') + '</select>';
          }).join('') + '</div>' : '') +
          '<h3 style="margin:16px 0 8px">Statuses → columns</h3><div class="im-st">' + srcs.map(function (s) {
            return '<span class="from">' + esc(s[0]) + '</span><span class="n">' + s[1] + '</span><select data-smap="' + esc(s[0]) + '" aria-label="Column for ' + esc(s[0]) + '">' + targetOptions(S.smap[s[0]]) + '</select>';
          }).join('') + '</div>' +
          '<div class="ui-stack" style="margin-top:14px"><label class="ui-check"><input type="checkbox" data-opt="history"' + (S.history ? ' checked' : '') + '> Keep dates (created, finished), so throughput, cycle times and level checks count your past</label>' +
          '<label class="ui-check"><input type="checkbox" data-opt="epics"' + (S.epics ? ' checked' : '') + '> Create epics that don\'t exist yet</label>' +
          (p.kind === 'jira' ? '<label class="ui-field"><span>Link back to Jira <em>(optional: https://yourcompany.atlassian.net/browse/)</em></span><input type="url" data-link value="' + esc(S.link) + '" placeholder="https://yourcompany.atlassian.net/browse/"></label>' : '') + '</div>',
          { extra: its.length + ' cards' });
        var prev = its.slice(0, 6);
        body += AA.win('3 · Preview and import', '<div class="im-prev"><table class="aa-table"><thead><tr><th>Title</th><th>Column</th><th>Type</th><th>Pts</th><th>Who</th><th>Epic</th><th>Created</th></tr></thead><tbody>' +
          prev.map(function (it) {
            var col = it.status === 'backlog' ? 'Backlog' : (cols.filter(function (c) { return c.id === it.status; })[0] || {}).name;
            return '<tr><td>' + esc((it.title || '').slice(0, 60)) + '</td><td>' + esc(col || it.status) + '</td><td>' + esc(it.type || '') + '</td><td>' + esc(it.points == null ? '' : it.points) + '</td><td>' +
              esc(it.assignee || '') + '</td><td>' + esc(it.epic || '') + '</td><td>' + esc(it.created ? it.created.slice(0, 10) : '') + '</td></tr>';
          }).join('') + '</tbody></table></div>' +
          (S.map.title || p.items ? '' : '<p style="color:var(--c-bad)">Pick the column that holds the title.</p>') +
          '<div class="ui-row" style="margin-top:12px"><button class="ui-btn primary lg" data-go-import' + (crew.demo || S.busy || !(S.map.title || p.items) ? ' disabled' : '') + '>' + UI.icon('upload') + 'Import ' + its.length + ' cards into ' + esc(crew.key) + '</button></div>' +
          '<div class="im-bar" data-bar style="margin-top:12px;display:' + (S.busy ? 'block' : 'none') + '"><i></i></div>' +
          (S.result ? '<div class="aa-lcds" style="margin-top:14px">' + AA.lcd(S.result.created, 'cards imported') + AA.lcd(S.result.duplicates, 'already there, skipped', 'cyan') +
            AA.lcd(S.result.epics_created, 'new epics', 'pink') + AA.lcd(S.result.comments, 'comments', 'amber') + '</div>' +
            (S.result.unmatched.length ? '<p class="small">Not in this crew, so left unassigned (their name is in the card): ' + esc(S.result.unmatched.join(', ')) + '. Invite them, then assign.</p>' : '') +
            (S.result.invalid ? '<p class="small muted">' + S.result.invalid + ' rows had no title and were skipped.</p>' : '') +
            '<div class="ui-row"><a class="ui-btn" href="#backlog" data-go="backlog">Open the backlog</a><a class="ui-btn" href="#reports/flow" data-go="reports/flow">See the history in Reports</a><a class="ui-btn" href="#plan" data-go="plan">Level checks</a></div>' : ''),
          { cls: 'lime' });
      }
      view.innerHTML = '<div class="ui-wrap">' + head + demo + '<div class="im-grid"><div class="ui-stack">' + step1 + body + '</div><div class="ui-stack">' + exportWin() +
        AA.win('What comes along', '<dl class="aa-kv"><dt>Kept</dt><dd>Titles, descriptions, types, priorities, points, labels, epics, comments, links back, and the dates that make your history count.</dd>' +
          '<dt>People</dt><dd>Matched to crew members by email or name. Anyone else stays in the card text.</dd><dt>Twice?</dt><dd>Safe. Cards already imported (same key) are skipped.</dd>' +
          '<dt>Points</dt><dd>Snapped to the nearest rung (1, 2, 3, 5, 8, 13, 21). Run the gates later to make them comparable.</dd></dl>') + '</div></div></div>';
    }
    function setParsed(p) {
      S.parsed = p; S.map = {}; S.smap = {}; S.result = null;
      if (p.headers) {
        FIELDS.forEach(function (f) { var h = p.headers.filter(function (x) { return GUESS[f[0]].test(x.trim()); })[0]; if (h) S.map[f[0]] = h; });
        if (p.kind === 'jira') { if (p.headers.indexOf('Summary') >= 0) S.map.title = 'Summary'; ['Custom field (Story Points)', 'Custom field (Story point estimate)'].forEach(function (h) { if (p.headers.indexOf(h) >= 0) S.map.points = h; }); }
      }
      guessStatuses(); draw();
    }
    function readText(text, name) {
      try {
        var t = String(text || '').trim(), json = t[0] === '{' || t[0] === '[';
        var kind = json ? (t.indexOf('"autoagile-export"') >= 0 ? 'autoagile' : 'trello') : (S.src === 'jira' || /issue key|issue type/i.test(t.split('\n')[0]) ? 'jira' : 'csv');
        if (kind !== S.src) { S.src = kind; UI.store.set('im.src', kind); }
        setParsed(kind === 'autoagile' ? readAutoAgile(t) : kind === 'trello' ? readTrello(t) : readCSV(t, kind));
        UI.toast('Read ' + (name || 'the text') + ': ' + items().length + ' cards', 'ok');
      } catch (e) { UI.toast(e.message || 'Could not read that file.', 'error'); }
    }
    function readFile(f) {
      if (!f) return;
      if (f.size > 15 * 1024 * 1024) { UI.toast('That file is over 15 MB. Export fewer issues at a time.', 'error'); return; }
      var r = new FileReader();
      r.onload = function () { readText(r.result, f.name); };
      r.readAsText(f);
    }
    function runImport() {
      var all = items().map(function (it) {
        var o = Object.assign({}, it); delete o.src; delete o.stage;
        return o;
      }), done = 0, total = { created: 0, duplicates: 0, invalid: 0, epics_created: 0, comments: 0, unmatched: [] };
      S.busy = true; S.result = null; draw();
      var bar = function () { var b = view.querySelector('[data-bar] i'); if (b) b.style.width = Math.round(100 * done / all.length) + '%'; };
      var opts = { history: S.history, epics: S.epics, from: { jira: 'Jira', trello: 'Trello', csv: 'CSV', autoagile: 'AutoAgile' }[S.parsed.kind] };
      var chain = Promise.resolve();
      for (var i = 0; i < all.length; i += 200) {
        (function (batch) {
          chain = chain.then(function () {
            return UI.api('import_cards', crew.id, batch, opts).then(function (r) {
              ['created', 'duplicates', 'invalid', 'epics_created', 'comments'].forEach(function (k) { total[k] += r[k]; });
              r.unmatched.forEach(function (u) { if (total.unmatched.indexOf(u) < 0) total.unmatched.push(u); });
              done += batch.length; bar();
            });
          });
        })(all.slice(i, i + 200));
      }
      chain.then(function () {
        S.busy = false; S.result = total; draw();
        if (total.created) AA.rave('IMPORTED', total.created + ' cards into ' + crew.key);
      }, function () { S.busy = false; draw(); });
    }
    function doExport(kind) {
      return UI.api('export_crew', crew.id).then(function (r) {
        var x = r.export, day = x.exported.slice(0, 10);
        if (kind === 'json') { AA.download(crew.key + '-autoagile-' + day + '.json', JSON.stringify(x, null, 1), 'application/json'); return; }
        var rows = [['Issue key', 'Summary', 'Description', 'Issue Type', 'Status', 'Column', 'Priority', 'Story Points', 'Labels', 'Assignee', 'Epic', 'Sprint', 'Created', 'Started', 'Resolved', 'Source']];
        x.cards.forEach(function (c) {
          rows.push([c.key, c.title, c.body, c.type, AA.STATUS[c.status], c.column, 'P' + c.priority, c.points == null ? '' : c.points, (c.labels || []).join(' '), c.assignee || '', c.epic || '',
            c.sprint || '', c.created || '', c.started || '', c.done_at || '', c.source || '']);
        });
        AA.download(crew.key + '-cards-' + day + '.csv', AA.toCSV(rows), 'text/csv');
      });
    }

    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-src]'))) { S.src = t.getAttribute('data-src'); UI.store.set('im.src', S.src); S.parsed = null; S.result = null; draw(); }
      else if (e.target.closest('[data-readpaste]')) readText(view.querySelector('[data-paste]').value, 'the pasted text');
      else if (e.target.closest('[data-go-import]')) runImport();
      else if ((t = e.target.closest('[data-exp]'))) UI.busy(t, doExport(t.getAttribute('data-exp')));
    });
    view.addEventListener('change', function (e) {
      var t = e.target;
      if (t.matches('[data-file]')) readFile(t.files[0]);
      else if (t.matches('[data-map]')) { S.map[t.getAttribute('data-map')] = t.value; if (t.getAttribute('data-map') === 'status') guessStatuses(); draw(); }
      else if (t.matches('[data-smap]')) { S.smap[t.getAttribute('data-smap')] = t.value; draw(); }
      else if (t.matches('[data-opt]')) { S[t.getAttribute('data-opt')] = t.checked; }
      else if (t.matches('[data-link]')) { S.link = t.value.trim(); draw(); }
    });
    view.addEventListener('dragover', function (e) { var z = e.target.closest('[data-dropzone]'); if (z) { e.preventDefault(); z.classList.add('over'); } });
    view.addEventListener('dragleave', function (e) { var z = e.target.closest('[data-dropzone]'); if (z) z.classList.remove('over'); });
    view.addEventListener('drop', function (e) { var z = e.target.closest('[data-dropzone]'); if (z) { e.preventDefault(); z.classList.remove('over'); readFile(e.dataTransfer.files[0]); } });

    return AA.withCrew(view, function (c) {
      crew = c;
      return UI.api('get_crew', c.id).then(function (r) { cols = r.crew.columns; draw(); });
    });
  });
})();

/* ===== insights.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('insights', { title: 'Insights', auth: 'user' }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';
    return AA.withCrew(view, function (crew) {
      return UI.api('get_insights', crew.id).then(function (d) {
        var sp = d.split, tot = sp.agent_points + sp.human_points;
        var g = d.gates;
        view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Insights // ' + esc(crew.key) + '</div><h1>Insights</h1><div class="sub">' +
          d.done_total + ' cards finished · flow measured from card timestamps</div></div></div>' + AA.demoNote(crew) +
          '<div class="aa-lcds">' + AA.lcd(d.p50 == null ? '--' : d.p50 + '<small>d</small>', 'Cycle time, median') + AA.lcd(d.p85 == null ? '--' : d.p85 + '<small>d</small>', '85% finish within', 'pink') +
            AA.lcd(d.predictability == null ? '--' : d.predictability + '<small>%</small>', 'Commitments finished', 'cyan') +
            AA.lcd(d.velocity_range ? d.velocity_range[0] + '–' + d.velocity_range[2] : '--', 'Velocity range (pts)', 'amber') + '</div>' +
          '<div class="in-grid">' +
            AA.win('Throughput', '<p class="in-note">Cards finished per week. Steady beats spiky: it is what makes forecasts work.</p><div data-c="tp"></div>' +
              AA.table(['Week of', 'Cards', 'Points'], d.throughput.map(function (w) { return [w.week, w.count, w.points]; })), { cls: 'lime', extra: '12 weeks' }) +
            AA.win('Cycle time', '<p class="in-note">Each dot is a finished card: days from start to done. Dashed lines: half finish within ' + (d.p50 || '?') + ' days, 85% within ' + (d.p85 || '?') + '.</p><div data-c="cy"></div>' +
              AA.table(['Card', 'Days', 'Points', 'By'], d.cycle.map(function (c) { return [c.key, c.days, c.points == null ? '' : c.points, c.agent ? 'agent' : 'human']; })), { extra: '90 days' }) +
            AA.win('Cumulative flow', '<p class="in-note">Bands that stay parallel mean smooth flow. A widening Doing band means you are starting more than you finish.</p><div data-c="cfd"></div>' +
              AA.table(['Week ending', 'To do', 'Doing', 'Done'], d.cfd.map(function (p) { return [p.date, p.todo, p.doing, p.done]; })), { cls: 'cyan' }) +
            AA.win('Velocity', d.velocity.length ? '<p class="in-note">Points committed and finished per sprint.</p><div data-c="vel"></div>' +
              AA.table(['Sprint', 'Committed', 'Done'], d.velocity.map(function (v) { return [v.name, v.committed, v.done]; }))
              : '<p class="in-note">Velocity appears once your crew runs sprints (level 2). Until then, throughput is your rhythm.</p>' + AA.smiley(60)) +
            AA.win('Gate accuracy', '<p class="in-note">Median days from start to done for each points value. If the gates work, bigger cards take longer.' +
              (g.score != null ? ' <b>Bigger took longer in ' + g.score + '% of steps.</b>' : '') + '</p><div data-c="gate"></div>' +
              AA.table(['Points', 'Cards', 'Median days'], g.rows.map(function (r) { return [r.points, r.n, r.median]; })), { cls: 'warn', extra: g.score != null ? g.score + '%' : '' }) +
            AA.win('Agents and humans', '<p class="in-note">Points finished in the last 8 weeks, and how long finished work waited in Review.</p>' +
              '<div class="aa-lcds">' + AA.lcd(sp.agent_points + '<small>pts</small>', 'By agents', 'cyan') + AA.lcd(sp.human_points + '<small>pts</small>', 'By humans', 'pink') + '</div>' +
              (tot ? '<div class="in-split" role="img" aria-label="Agents ' + Math.round(100 * sp.agent_points / tot) + '%, humans ' + Math.round(100 * sp.human_points / tot) + '%"><i style="width:' + (100 * sp.agent_points / tot) + '%;background:var(--ch-3)"></i><i style="flex:1;background:var(--ch-2)"></i></div>' +
                '<div class="aa-legend"><span><i style="background:var(--ch-3)"></i>Agents ' + Math.round(100 * sp.agent_points / tot) + '%</span><span><i style="background:var(--ch-2)"></i>Humans ' + Math.round(100 * sp.human_points / tot) + '%</span></div>' : '') +
              '<dl class="aa-kv" style="margin-top:10px"><dt>Agent work in review</dt><dd>' + (sp.agent_review_hours == null ? 'n/a' : sp.agent_review_hours + ' hours on average') + '</dd>' +
              '<dt>Human work in review</dt><dd>' + (sp.human_review_hours == null ? 'n/a' : sp.human_review_hours + ' hours on average') + '</dd></dl>' +
              (sp.agent_review_hours != null && sp.human_review_hours != null && sp.agent_review_hours > sp.human_review_hours * 1.5 ?
                '<p class="small" style="color:var(--c-warn);margin:10px 0 0">Agent work waits longer for review than human work. Agents are fast; reviews are the bottleneck. Set a daily review slot.</p>' : ''), { cls: 'cyan' }) +
          '</div><div style="height:16px"></div>' +
          AA.win('Aging work in progress', d.aging.length ? d.aging.map(function (a) {
            var cls = a.age > 5 ? 'bad' : a.age > 2.5 ? 'warn' : '';
            return '<div class="in-age"><span class="k">' + esc(a.key) + '</span><a href="#card/' + esc(a.key) + '" data-card="' + esc(a.key) + '">' + (a.agent ? '🤖 ' : '') + esc(a.title) + '</a><span class="ui-badge">' + esc(a.status) + '</span>' +
              '<span class="d ' + cls + '">' + (a.age < 1 ? Math.round(a.age * 24) + 'h' : a.age + 'd') + '</span></div>';
          }).join('') : '<p class="muted small">Nothing in progress.</p>', { extra: 'oldest first' }) + '</div>';

        function charts() {
          if (!view.isConnected) return false;
          var q = function (k) { return view.querySelector('[data-c="' + k + '"]'); };
          AA.chart.bars(q('tp'), { title: 'Throughput per week', unit: 'cards', color: 'var(--ch-1)', labelEvery: 2,
            data: d.throughput.map(function (w) { return { label: AA.shortDate(w.week), head: 'Week of ' + AA.shortDate(w.week), value: w.count }; }) });
          AA.chart.scatter(q('cy'), { title: 'Cycle time', series: [{ name: 'Humans', color: 'var(--ch-2)' }, { name: 'Agents', color: 'var(--ch-3)' }],
            refs: [d.p50 != null ? { y: d.p50, name: '50%' } : null, d.p85 != null ? { y: d.p85, name: '85%' } : null].filter(Boolean),
            points: d.cycle.map(function (c) { return { x: new Date(c.done).getTime(), y: c.days, s: c.agent ? 1 : 0, head: c.key + ' · ' + (c.points == null ? '?' : c.points) + ' pts', label: c.title }; }) });
          AA.chart.stack(q('cfd'), { title: 'Cumulative flow', x: d.cfd.map(function (p) { return AA.shortDate(p.date); }),
            series: [{ name: 'Done', color: 'var(--ch-1)', values: d.cfd.map(function (p) { return p.done; }) },
                     { name: 'Doing', color: 'var(--ch-3)', values: d.cfd.map(function (p) { return p.doing; }) },
                     { name: 'To do', color: 'var(--ch-4)', values: d.cfd.map(function (p) { return p.todo; }) }] });
          if (q('vel')) AA.chart.grouped(q('vel'), { title: 'Velocity', data: d.velocity.map(function (v) { return { label: 'S' + v.number, head: v.name, values: [v.committed, v.done] }; }),
            series: [{ name: 'Committed', color: 'var(--ch-3)' }, { name: 'Done', color: 'var(--ch-1)' }] });
          AA.chart.bars(q('gate'), { title: 'Median days per points value', unit: 'days (median)', color: 'var(--ch-2)',
            data: g.rows.map(function (r) { return { label: r.points + ' pt', head: r.points + ' points · ' + r.n + ' cards', value: r.median }; }) });
        }
        charts(); AA.onResize(charts);
      });
    });
  });
})();

/* ===== landing.html ===== */
(function () {
  var esc = UI.esc;
  var COPY = {
    eyebrow: 'AutoAgile // agile for humans + AI',
    title: 'Agile that <em>levels up</em> with your crew.',
    lead: 'Start in Kanban. Unlock sprints, then a 3-month plan, then a year roadmap, when your own data says you\'re ready. Estimate with complexity gates instead of guesswork, and let AI developers pull cards, log their work and hand it in for review on the same board.',
    cta: 'Start a crew, free',
    proof: ['Kanban → Scrum → Quarter → Year', 'AI agents with an API', 'Works on your phone'],
    levels: [['1', 'Kanban', 'Pull from a ranked backlog, keep WIP limits, learn your rhythm.', 'Unlocks Scrum: 25 cards, 6 steady weeks'],
             ['2', 'Scrum', 'Sprints with a goal, planned against real velocity. Retros: LOUDER, MUTE, REMIX.', 'Unlocks Quarter: 3 steady sprints'],
             ['3', 'Quarter', 'A 3-month forecast of epics, with optimistic and pessimistic finish lines.', 'Unlocks Year: 6 predictable sprints'],
             ['4', 'Year', 'A roadmap in quarters: capacity against load, late epics flagged early.', 'Top level: keep it honest']],
    features: [['gate', 'Complexity gates', 'Six questions (scope, clarity, novelty, dependencies, risk, testing) light a points ladder. Red answers raise the floor. 13 or more says split it; unknown clarity says spike first.'],
               ['bot', 'AI developers on the crew', 'Agents get a name, a token and their own WIP limit. They pull the next agent-ready card, claim it, log, tick criteria and submit. Only humans approve.'],
               ['copy', 'One-click agent briefs', 'Every card exports a markdown spec: goal, acceptance criteria, gates, your Definition of Done and the house rules. Paste it into any coding tool.'],
               ['chart', 'Reports that forecast', 'Burn-up with a forecast cone, Monte Carlo "when will it be done?", cumulative flow, a cycle-time control chart, an epic map and the work mix. Every chart has a table and a CSV.'],
               ['upload', 'Bring your history, leave any time', 'Import a Jira CSV, a Trello board or any spreadsheet with its dates, so your past counts from day one. Export everything as JSON or CSV whenever you like.'],
               ['megaphone', 'Requests that get answers', 'Give customers and managers a link to ask and vote. The crew promises an answer within 7, 14 or 30 days: yes, later or no, always with a reason.'],
               ['bell', 'Alerts without the noise', 'One webhook for Slack, Teams or Discord and an opt-in email digest when agent work waits in review, a card is blocked or a sprint runs over. Each thing is said once.'],
               ['board', 'Your columns, your lanes', 'Split Doing into Build and Test, give each column its own WIP limit, and group the board by person, epic, priority or type. Ctrl K jumps anywhere.'],
               ['zap', 'Levels you earn', 'Each level lists the checks to pass. Level up with a little rave, force it if you must (it\'s recorded), step back any time.'],
               ['users', 'Crews, codes, sandbox', 'Invite people with a 6-character code. Two demo crews let you try everything before you start your own.']],
    faq: [['Why start in Kanban?', 'Sprint commitments and roadmaps need history: how much you finish, and how steadily. A young crew doesn\'t have it yet, so it starts by making work visible and limiting WIP. The data it produces unlocks the next level.'],
          ['What are complexity gates?', 'Instead of debating 3 versus 5 points, you answer six short questions about the card. The total picks a Fibonacci rung (1, 2, 3, 5, 8, 13, 21); any red answer sets a minimum. The same questions decide whether an AI agent can take the card alone.'],
          ['How do AI developers connect?', 'Add an agent on the Agents page and copy its token. The agent calls a small HTTP API (next, claim, log, check, submit, release, propose). A console in the app tries every call, and there is a CLAUDE.md snippet to paste into your repo.'],
          ['Can an agent finish work on its own?', 'No. Agents move cards to Review at most; a human approves to Done. Agents also respect their own WIP limit and the crew\'s Doing limit, so they can\'t flood the board.'],
          ['Coming from Jira or Trello?', 'Export a CSV from Jira or a JSON from Trello and drop it on the Import page. You map statuses to columns, see a preview, and the cards arrive with their dates, labels, epics and comments. Importing twice skips what is already there.'],
          ['What if we want to leave?', 'Any member can download the whole crew as JSON or CSV at any time, from Crew settings. No export fees, no support ticket.'],
          ['Is it free? Who sees my data?', 'It\'s free. Your crew\'s cards are visible to your crew members and to agents you give a token. Demo crews are a shared sandbox: don\'t put anything private there. The Privacy & Terms page has the details.']]
  };
  // A copy of server_code/Gates.py (visitors can't call the server). Keep in step.
  var GATES = { gates: [
      { id: 'scope', name: 'Scope', q: 'How much of the system does it touch?', opts: ['One file or setting', 'One module', 'Several modules', 'Across services or teams'] },
      { id: 'clarity', name: 'Clarity', q: 'How clear is what done looks like?', opts: ['Crystal: criteria written', 'Mostly clear', 'Fuzzy: open questions', 'Unknown: needs research'] },
      { id: 'novelty', name: 'Novelty', q: 'Have we done this before?', opts: ['Routine', 'Like past work', 'New to this crew', 'Nobody has done it'] },
      { id: 'deps', name: 'Dependencies', q: 'What must we wait on?', opts: ['Nothing', 'One thing we control', 'Another team or API', 'Several outside parties'] },
      { id: 'risk', name: 'Risk', q: 'What breaks if it goes wrong?', opts: ['Nothing much', 'A small feature', 'User data or money', 'Production or security'] },
      { id: 'verify', name: 'Verify', q: 'How do we prove it works?', opts: ['Quick automated test', 'Tests plus a look', 'Manual QA needed', 'Hard to test'] }],
    ladder: [{ min: 0, points: 1, name: 'TICK' }, { min: 2, points: 2, name: 'PULSE' }, { min: 4, points: 3, name: 'LOOP' }, { min: 7, points: 5, name: 'GROOVE' },
             { min: 10, points: 8, name: 'BUILD' }, { min: 13, points: 13, name: 'DROP' }, { min: 16, points: 21, name: 'RAVE' }],
    floors: { '2': 3, '3': 5 }, split_at: 13 };

  function heroArt() {
    var c = function (t, type, pts, who, ec, cls) {
      return '<div class="lp-hc ' + (cls || '') + '" style="--ec:' + ec + '">' + t + '<div class="r">' + AA.type(type) + '<span class="ui-spacer"></span>' + who + AA.pts(pts) + '</div>' +
        (cls === 'slot' ? '<span class="st"></span>' : '') + '</div>';
    };
    var bot = function (col) { return AA.who({ kind: 'agent', name: 'Agent', color: col }); };
    var hu = function (n) { return AA.who({ kind: 'user', name: n }); };
    var mover = '<div class="lp-hc lp-mover" style="--ec:#b4ff1f">Profanity filter EN/FR<div class="r">' + AA.type('story') + '<span class="ui-spacer"></span>' + bot('#b4ff1f') + AA.pts(3) + '</div>' +
      '<span class="st"><b>&gt; ready</b><b>&gt; working…</b><b>&gt; in review</b><b>&gt; done ✓</b></span></div>';
    var board = '<div class="lp-hcols">' +
      '<div class="lp-hcol"><i>READY</i>' + c('slot', 'story', 3, '', '', 'slot') + c('Pin a message in chat', 'story', 2, bot('#ff7a1a'), '#ff2bd6') + c('Keyboard shortcuts', 'story', 2, hu('Ines Ozola'), '#ffd60a') + '</div>' +
      '<div class="lp-hcol"><i>DOING 3/5</i>' + c('slot', 'story', 3, '', '', 'slot') + c('Live listener graph', 'story', 8, hu('Maya Chen'), '#00e5ff') + '</div>' +
      '<div class="lp-hcol"><i>REVIEW</i>' + c('slot', 'story', 3, '', '', 'slot') + c('Emoji picker overlap', 'bug', 2, hu('Theo Martin'), '#ff2bd6') + '</div>' +
      '<div class="lp-hcol"><i>DONE</i>' + c('slot', 'story', 3, '', '', 'slot') + c('Mute a listener', 'story', 5, bot('#ff7a1a'), '#ff2bd6') + '</div>' + mover + '</div>';
    var log = '<div class="lp-log"><span class="hd">AGENT nova-7 // API LOG</span>' +
      '<p><i>POST</i> /cards/41/pull</p><p><u>200</u> card is yours: 3 pts</p><p><i>POST</i> /cards/41/log "filter + tests"</p>' +
      '<p><i>POST</i> /cards/41/handoff</p><p><u>→</u> Maya Chen to review</p><p><u>✓</u> approved · velocity +3</p></div>';
    return '<div class="lp-hart" aria-hidden="true">' + AA.win('NOVA // Sprint 9', board, { extra: 'LVL 4' }) + log + '</div>';
  }

  UI.page('landing', { title: 'Welcome' }, function (view, ctx) {
    var me = ctx.me, C = COPY;
    var primary = me ? '<a class="ui-btn primary lg" href="#deck" data-go="deck">Open the deck ' + UI.icon('arrow') + '</a>'
      : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + ' ' + UI.icon('arrow') + '</a>' +
        '<a class="ui-btn lg" href="#auth" data-go="auth">I have an account</a>';
    view.innerHTML =
      '<section class="lp-hero"><div class="ui-wrap"><div class="lp-top">' +
        '<div><div class="eyebrow">' + esc(C.eyebrow) + '</div><h1>' + C.title + '</h1></div>' +
        '<div><p class="lp-lead">' + esc(C.lead) + '</p>' +
        '<div class="lp-cta">' + primary + '</div>' +
        '<div class="lp-proof">' + C.proof.map(function (p) { return '<span><span class="aa-led on"></span>' + esc(p) + '</span>'; }).join('') + '</div>' +
      '</div></div>' + heroArt() + '</div></section>' +
      '<div class="aa-checker"></div>' +
      '<section class="lp-section" id="levels"><div class="ui-wrap"><div class="lp-head"><div class="eyebrow">The ladder</div><h2>Four levels. Your data unlocks each one.</h2>' +
        '<p>Young crews don\'t promise sprints or roadmaps on day one. They earn them, and AutoAgile checks the numbers for you.</p></div>' +
        '<div class="lp-levels">' + C.levels.map(function (l) {
          return '<div class="lp-level"><span class="n">0' + l[0] + '</span><h3>' + esc(l[1]) + '</h3><p>' + esc(l[2]) + '</p><div class="gate">▶ ' + esc(l[3]) + '</div></div>';
        }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap lp-gatedemo"><div><div class="eyebrow">Complexity gates</div><h2>Stop arguing about 3 versus 5.</h2>' +
        '<p class="muted">Answer six questions and the ladder lights up. Try it: the same widget estimates every card in the app, and tells you when a card is a job for an AI agent.</p>' +
        '<p class="small muted">Red answers raise the floor. 13 or more: split it. Unknown clarity: spike first.</p></div>' +
        AA.win('Try the gates', '<div data-gates></div>', { cls: 'lime' }) + '</div></section>' +
      '<section class="lp-section"><div class="ui-wrap lp-ai"><div>' + AA.win('agent@nova $', '<pre class="aa-pre">$ curl -H "Authorization: Bearer $AUTOAGILE_TOKEN" \\\n    https://&lt;your app&gt;/_/api/agent/next\n{\n "ok": true,\n "card": {\n  "key": "NOVA-87",\n  "title": "Pin a message to the top of chat",\n  "points": 2, "fit": "solo",\n  "brief": "# NOVA-87: Pin a message ..."\n },\n "hint": "POST claim with {\\"key\\": \\"NOVA-87\\"} to start."\n}</pre>', { cls: 'cyan', flush: true }) +
        '</div><div><div class="eyebrow">Built for AI developers</div><h2>Your agents work the board like teammates.</h2><ul>' +
        '<li><b>Pull, don\'t push.</b> Agents ask for <code>next</code> and get the top card that fits them, with a full markdown brief.</li>' +
        '<li><b>Guard rails.</b> Their own WIP limit, the crew\'s Doing limit, a Definition of Ready, and house rules in every brief.</li>' +
        '<li><b>Humans approve.</b> Agents hand in to Review with a summary and PR links; only people move cards to Done.</li>' +
        '<li><b>Ask on the card.</b> Agents log questions on the card\'s timeline; humans answer in comments.</li></ul></div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Everything in the box</h2></div>' +
        '<div class="ui-grid">' + C.features.map(function (f) { return '<div class="ui-card lp-feature">' + UI.icon(f[0]) + '<h3>' + esc(f[1]) + '</h3><p>' + esc(f[2]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Questions</h2></div><div class="lp-faq">' +
        C.faq.map(function (q) { return '<details><summary>' + esc(q[0]) + '</summary><p>' + esc(q[1]) + '</p></details>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-band"><div><h2>Drop the beat on your backlog.</h2><p>Two demo crews are waiting: a veteran radio crew at level 4 and a bakery crew still in Kanban.</p></div>' +
        (me ? '<a class="ui-btn primary lg" href="#deck" data-go="deck">Open the deck</a>' : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + '</a>') +
      '</div></div></section>';
    AA.gateWidget(view.querySelector('[data-gates]'), GATES, { scope: 1, clarity: 0, novelty: 1, deps: 0, risk: 1 });
  });
})();

/* ===== plan.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['level', 'Level', 'zap', 1], ['sprints', 'Sprints', 'refresh', 2], ['quarter', '3 months', 'calendar', 3], ['year', 'Year', 'layers', 4], ['epics', 'Epics', 'flag', 1]];
  var CONF = { safe: 'SAFE', likely: 'LIKELY', stretch: 'STRETCH', nofit: "WON'T FIT" };

  UI.page('plan', { title: 'Plan', nav: 'Plan', icon: 'calendar', auth: 'user', order: 40 }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'level', d = null, crewRef = null;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';

    function locked(need, html) {
      if (d.level >= need) return html;
      var L = d.levels[need - 1];
      return '<div class="pl-locked"><div class="pl-lockbox">' + AA.win('Locked // level ' + need, '<p style="margin-top:0"><b>' + esc(L.name) + ': ' + esc(L.title) + '.</b> ' + esc(L.blurb) + '</p>' +
        '<p class="small muted">Your crew is at level ' + d.level + '. Forecasts built on too little history are guesses dressed as plans, so this unlocks with your data.</p>' +
        '<a class="ui-btn primary sm" href="#plan/level" data-go="plan/level">' + UI.icon('zap') + 'See the level checks</a>', { cls: 'warn' }) +
        '</div><div class="pl-preview" aria-hidden="true">' + html + '</div></div>';
    }
    function levelTab() {
      var m = d.maturity, nx = m.next;
      var log = d.level_log.slice().reverse().map(function (l) {
        return '<div class="pl-sprint" style="grid-template-columns:70px minmax(0,1fr) auto"><span class="n">LVL ' + l.level + '</span><span>' + esc(d.levels[l.level - 1].name) + ' · by ' + esc(l.by) +
          (l.forced ? ' <span class="ui-badge warn">forced</span>' : '') + '</span><span class="faint small">' + esc(UI.fmtDate(l.at)) + '</span></div>';
      }).join('');
      return AA.levels(d.levels, d.level) +
        '<div class="pl-two"><div>' + (nx ? AA.win('Checks for level ' + nx.n + ': ' + esc(nx.name), '<p style="margin-top:0">' + esc(nx.blurb) + '</p>' + AA.meter(nx.pct, nx.total) +
          '<div class="pl-checks" style="margin-top:12px">' + nx.checks.map(function (c) {
            return '<div class="pl-check ' + (c.ok ? 'ok' : 'no') + '"><span class="aa-led ' + (c.ok ? 'on' : 'bad') + '"></span><div><b>' + esc(c.label) + '</b><div class="h">' + esc(c.hint) + '</div></div>' +
              '<span class="v">' + esc(c.shown) + '<br><small>' + (c.id === 'wip' || c.id === 'stale' ? 'need 0' : 'need ' + esc(String(c.target))) + '</small></span></div>';
          }).join('') + '</div><div class="ui-row" style="margin-top:14px">' +
          (nx.eligible ? '<button class="ui-btn primary lg" data-levelup="' + nx.n + '">' + UI.icon('zap') + 'Level up to ' + esc(nx.name) + '</button>'
            : '<button class="ui-btn" data-force="' + nx.n + '">Force level ' + nx.n + ' anyway</button><span class="small muted">' + nx.passed + ' of ' + nx.total + ' checks pass.</span>') + '</div>',
          { cls: nx.eligible ? 'lime' : '', extra: nx.passed + '/' + nx.total })
          : AA.win('Top level', '<div class="ui-row">' + AA.smiley(64) + '<div style="flex:1"><h3 style="margin:0">YEAR // Roadmap</h3><p class="muted" style="margin:0">Your crew plans and estimates a year ahead from measured capacity. Keep the sprints honest and the forecast stays honest.</p></div></div>', { cls: 'lime' })) +
        '</div><div>' + AA.win('What each level adds', d.levels.map(function (l) {
          return '<p style="margin:0 0 10px"><span class="aa-led ' + (l.n <= d.level ? 'on' : '') + '"></span> <b>' + l.n + '. ' + esc(l.name) + '</b> <span class="muted small">' + esc(l.blurb) + '</span></p>';
        }).join('') + (d.level > 1 ? '<button class="ui-btn sm" data-down="' + (d.level - 1) + '">Step back to level ' + (d.level - 1) + '</button>' : ''), { cls: 'cyan' }) +
        '<div style="height:16px"></div>' + AA.win('Level history', log || '<p class="small muted">No changes yet.</p>', { flush: true }) + '</div></div>';
    }
    function sprintsTab() {
      var a = d.active, closed = d.sprints.filter(function (s) { return s.state === 'closed'; });
      var html = (a ? AA.win(esc(a.name) + ' · running', '<div class="ui-row between" style="margin-bottom:8px"><div><b>' + esc(a.goal || 'No goal set') + '</b><div class="small muted">' + esc(AA.shortDate(a.start)) + ' – ' + esc(AA.shortDate(a.end)) +
            ' · ' + a.done_points + ' of ' + a.points + ' pts done · ' + UI.plural(a.cards, 'card') + '</div></div>' +
            '<div class="ui-row"><button class="ui-btn sm" data-goal="' + esc(a.id) + '">' + UI.icon('edit') + 'Goal</button><button class="ui-btn primary sm" data-closesprint="' + esc(a.id) + '">' + UI.icon('check') + 'Close sprint</button></div></div>' +
            '<div data-burn></div>' + AA.table(['Day', 'Ideal', 'Points left'], a.burndown.map(function (p) { return [p.day, p.ideal, p.remaining == null ? '' : p.remaining]; })), { cls: 'lime', extra: 'burndown' })
          : AA.win('No sprint running', '<p style="margin-top:0">Plan the next sprint on the backlog: pick cards up to your velocity, set a goal, start it.</p><a class="ui-btn primary sm" href="#backlog" data-go="backlog">' + UI.icon('list') + 'Plan from the backlog</a>', { cls: 'warn' })) +
        '<div class="pl-two"><div>' + AA.win('Velocity', d.velocity.length ? '<div data-vel></div>' + AA.table(['Sprint', 'Committed', 'Done'], d.velocity.map(function (v) { return [v.name, v.committed, v.done]; }))
            : '<p class="small muted">Close your first sprint to see velocity.</p>', { extra: d.predictability != null ? d.predictability + '% predictable' : '' }) + '</div><div>' +
          AA.win('Past sprints', closed.length ? closed.map(function (s) {
            var pct = s.committed ? Math.round(100 * (s.done_final || 0) / s.committed) : null, r = s.retro || {};
            var n = (r.louder || []).length + (r.mute || []).length + (r.remix || []).length;
            return '<div class="pl-sprint"><span class="n">' + esc(s.name) + '</span><span class="small">' + esc(s.goal || '') + '<br><span class="faint">' + esc(AA.shortDate(s.start)) + ' – ' + esc(AA.shortDate(s.end)) + '</span></span>' +
              '<span class="pts">' + (s.done_final || 0) + '/' + s.committed + (pct != null ? ' · ' + pct + '%' : '') + '</span><button class="ui-btn sm" data-retro="' + esc(s.id) + '">Retro' + (n ? ' (' + n + ')' : '') + '</button></div>';
          }).join('') : '<p class="small muted">None yet.</p>', { flush: closed.length > 0 }) + '</div></div>';
      return locked(2, html);
    }
    function quarterTab() {
      var q = d.quarter, slots = q.slots, n = slots.length, cap = d.capacity;
      var gantt = '<div class="pl-gantt" style="--n:' + n + '"><div class="pl-slots"><span class="faint small">EPIC</span><div class="lab">' + slots.map(function (s) {
          return '<span class="' + (s.current ? 'cur' : '') + '" title="' + esc(s.start) + ' to ' + esc(s.end) + '">' + esc(s.label) + '</span>';
        }).join('') + '</div><span class="faint small">CONFIDENCE</span></div>' +
        (q.epics.map(function (e) {
          var pct = function (v) { return Math.min(100, 100 * v / n); };
          var left = pct(e.start), w = Math.max(2, pct(Math.min(e.finish_avg, n + 0.5)) - left);
          return '<div class="pl-grow"><div class="pl-gname"><b><span class="aa-dot" style="background:' + esc(e.color) + '"></span> ' + esc(e.title) + '</b><span>' + e.remaining + ' pts left · ' + e.progress + '% done</span></div>' +
            '<div class="pl-track" style="--slot:' + (100 / n) + '%" title="Optimistic sprint ' + e.finish_opt + ', likely ' + e.finish_avg + ', pessimistic ' + e.finish_pes + '">' +
            '<span class="pl-whisk" style="left:' + pct(e.finish_opt) + '%;width:' + Math.max(0.5, pct(Math.min(e.finish_pes, n)) - pct(e.finish_opt)) + '%"></span>' +
            '<span class="pl-bar" style="left:' + left + '%;width:' + w + '%;background:' + esc(e.color) + '"></span></div>' +
            '<span class="pl-conf ' + e.confidence + '">' + CONF[e.confidence] + '</span></div>';
        }).join('') || '<p class="muted">No epics in the next three months. Give epics a quarter on the Epics tab.</p>') + '</div>';
      var html = '<div class="aa-lcds">' + AA.lcd(cap[0] + '–' + cap[2], 'Points per sprint (range)', 'cyan') + AA.lcd(cap[1], 'Average velocity') +
          AA.lcd(q.capacity[1] + '<small>pts</small>', 'Capacity, next ' + n + ' sprints', 'amber') + AA.lcd(q.load + '<small>pts</small>', 'Planned epic work', q.load > q.capacity[1] ? 'red' : 'pink') + '</div>' +
        '<div style="height:16px"></div>' + AA.win('Three-month forecast', '<p class="small muted" style="margin-top:0">Epics in rank order, filled into sprints at your measured velocity (' + esc(d.capacity_source) + '). ' +
          'Bars end at the likely sprint; whiskers run from the optimistic to the pessimistic finish. SAFE = done even at your slowest pace.</p>' + gantt, { cls: 'lime', extra: n + ' sprints' });
      return locked(3, html);
    }
    function yearTab() {
      var y = d.year;
      var html = '<div class="aa-lcds">' + AA.lcd(y.total_capacity[1] + '<small>pts</small>', 'Capacity this year (avg)', 'cyan') + AA.lcd(y.total_capacity[0] + '–' + y.total_capacity[2], 'Capacity range') +
          AA.lcd(y.total_load + '<small>pts</small>', 'Booked epic work', y.total_load > y.total_capacity[1] ? 'red' : 'pink') + AA.lcd(y.later.length, 'Epics not scheduled', 'amber') + '</div><div style="height:16px"></div>' +
        '<div class="pl-year">' + y.quarters.map(function (q, qi) {
          var pct = q.capacity[1] ? Math.min(100, 100 * q.load / q.capacity[1]) : 0;
          return '<section class="pl-q' + (q.over ? ' over' : '') + '"><div class="pl-qhead"><b>' + esc(q.label) + (qi === 0 ? ' · NOW' : '') + '</b>' +
            '<div class="cap">' + q.load + ' / ' + q.capacity[1] + ' pts' + (q.over ? ' OVERBOOKED' : '') + '</div><div class="pl-loadbar"><i class="' + (q.over ? 'over' : '') + '" style="width:' + pct + '%"></i></div></div>' +
            '<div class="pl-qbody">' + (q.epics.map(function (e) { return epicCard(e, qi); }).join('') || '<p class="small faint" style="margin:6px">Free capacity.</p>') + '</div></section>';
        }).join('') + '</div><div style="height:16px"></div>' +
        AA.win('Later / unscheduled', y.later.length ? '<div class="pl-year" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">' + y.later.map(function (e) { return epicCard(e, -1); }).join('') + '</div>'
          : '<p class="small muted">Everything has a quarter.</p>');
      return locked(4, html);
    }
    function epicCard(e, qi) {
      return '<div class="pl-epic" style="--ec:' + esc(e.color) + '" data-epic="' + esc(e.id) + '"><b>' + esc(e.title) + '</b><div class="m"><span>' + esc(e.size) + '</span><span>' + e.remaining + ' pts</span>' +
        '<span>' + esc(e.status) + '</span>' + (e.forecast_q ? (e.late ? '<span class="pl-late">LATE → ' + esc(e.forecast_q) + '</span>' : e.risky ? '<span style="color:var(--c-warn)">at risk</span>' : '<span style="color:var(--c-good)">on track</span>') : '') + '</div>' +
        '<div class="acts"><button class="ui-btn ghost" data-qmove="-1" title="Earlier quarter" aria-label="Earlier quarter">' + UI.icon('back') + '</button>' +
        '<button class="ui-btn ghost" data-qmove="1" title="Later quarter" aria-label="Later quarter">' + UI.icon('arrow') + '</button>' +
        '<button class="ui-btn ghost" data-editepic="' + esc(e.id) + '" title="Edit" aria-label="Edit">' + UI.icon('edit') + '</button></div></div>';
    }
    function epicsTab() {
      return AA.win('Epics', '<div class="ui-row" style="padding:12px 12px 0"><button class="ui-btn primary sm" data-editepic="">' + UI.icon('plus') + 'New epic</button>' +
        '<span class="small muted">Big goals that hold many cards. Size them S/M/L/XL until they are broken down.</span></div>' +
        (d.epics.map(function (e) {
          return '<div class="pl-epicrow" style="--ec:' + esc(e.color) + '" data-epic="' + esc(e.id) + '"><span class="aa-dot" style="background:' + esc(e.color) + ';width:14px;height:14px"></span>' +
            '<div style="min-width:0"><b>' + esc(e.title) + '</b> <span class="ui-badge">' + esc(e.status) + '</span><div class="small muted">' + e.cards + ' cards · ' + e.done_points + ' pts done · ' + e.remaining + ' left (' + esc(e.sized_by === 'size' ? 'from size ' + e.size : 'from cards') + ')</div></div>' +
            '<div class="pl-prog" title="' + e.progress + '% done"><i style="width:' + e.progress + '%"></i></div><span class="q small">' + esc(e.quarter || 'unscheduled') + '</span>' +
            '<span class="ui-row" style="gap:2px"><button class="ui-btn ghost icon" data-erank="up" aria-label="Rank up">' + UI.icon('up') + '</button><button class="ui-btn ghost icon" data-erank="down" aria-label="Rank down">' + UI.icon('down') + '</button>' +
            '<button class="ui-btn ghost icon" data-editepic="' + esc(e.id) + '" aria-label="Edit">' + UI.icon('edit') + '</button></span></div>';
        }).join('') || '<p class="muted" style="padding:12px">No epics yet.</p>'), { flush: true, extra: d.epics.length });
    }
    function draw() {
      var body = { level: levelTab, sprints: sprintsTab, quarter: quarterTab, year: yearTab, epics: epicsTab }[tab]();
      view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Plan // ' + esc(d.crew.key) + '</div><h1>Plan</h1><div class="sub">Level ' + d.level + ' // ' + esc(d.levels[d.level - 1].name) +
        (d.predictability != null ? ' · ' + d.predictability + '% of commitments finished' : '') + '</div></div></div>' + AA.demoNote(crewRef) +
        '<nav class="ui-tabs">' + TABS.map(function (t) {
          return '<a href="#plan/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + (d.level < t[3] ? ' 🔒' : '') + '</a>';
        }).join('') + '</nav>' + body + '</div>';
      if (tab === 'sprints' && d.level >= 2) {
        var be = view.querySelector('[data-burn]'), ve = view.querySelector('[data-vel]');
        var drawCharts = function () {
          if (!view.isConnected) return false;
          if (be && d.active) AA.chart.lines(be, { height: 220, title: 'Burndown', x: d.active.burndown.map(function (p) { return AA.shortDate(p.day); }),
            series: [{ name: 'Ideal', color: 'var(--c-faint)', values: d.active.burndown.map(function (p) { return p.ideal; }), dashed: true },
                     { name: 'Points left', color: 'var(--ch-1)', values: d.active.burndown.map(function (p) { return p.remaining; }), area: true }] });
          if (ve) AA.chart.grouped(ve, { height: 210, title: 'Velocity', data: d.velocity.map(function (v) { return { label: 'S' + v.number, head: v.name, values: [v.committed, v.done] }; }),
            series: [{ name: 'Committed', color: 'var(--ch-3)' }, { name: 'Done', color: 'var(--ch-1)' }] });
        };
        drawCharts(); AA.onResize(drawCharts);
      }
    }
    function load() {
      return AA.withCrew(view, function (crew) {
        crewRef = crew;
        return UI.api('get_plan', crew.id).then(function (r) { d = r; draw(); });
      });
    }
    function setLevel(n, force) {
      return UI.api('set_level', crewRef.id, n, !!force).then(function (r) {
        if (n > d.level) AA.rave('LEVEL UP!', 'Level ' + r.level + ': ' + r.info.name + (r.forced ? ' (forced)' : ''));
        else UI.toast('Back to level ' + r.level, 'ok');
        return AA.loadCrews(true).then(load);
      });
    }
    function retroModal(sid) {
      var s = d.sprints.filter(function (x) { return x.id === sid; })[0], r = s.retro || {};
      var col = function (k, label, hint) {
        return '<div class="' + k + '"><h4>' + label + '</h4><textarea name="' + k + '" placeholder="' + esc(hint) + '">' + esc((r[k] || []).join('\n')) + '</textarea></div>';
      };
      var m = UI.modal('<h2>Retro: ' + esc(s.name) + '</h2><p class="muted">One line per note. Turn the music up on what worked, mute what didn\'t, remix something new.</p>' +
        '<form data-retroform class="ui-stack"><div class="pl-retro">' + col('louder', 'LOUDER', 'Keep doing') + col('mute', 'MUTE', 'Stop doing') + col('remix', 'REMIX', 'Try next') + '</div>' +
        '<label class="ui-field"><span>Action items <em>(one per line; start with [x] when done)</em></span><textarea name="actions" rows="3">' +
        esc((r.actions || []).map(function (a) { return (a.done ? '[x] ' : '') + a.text; }).join('\n')) + '</textarea></label>' +
        '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">Save retro</button></div></form>', { wide: true });
      m.el.querySelector('form').addEventListener('submit', function (e) {
        e.preventDefault();
        var v = UI.formData(e.target), lines = function (t) { return t.split('\n').map(function (x) { return x.trim(); }).filter(Boolean); };
        var out = { louder: lines(v.louder), mute: lines(v.mute), remix: lines(v.remix), actions: lines(v.actions).map(function (a) { var done = /^\[x\]\s*/i.test(a); return { text: a.replace(/^\[x\]\s*/i, ''), done: done }; }) };
        UI.busy(e.target.querySelector('[type=submit]'), UI.api('save_retro', sid, out)).then(function () { m.close(); UI.toast('Retro saved', 'ok'); load(); });
      });
    }
    function epicModal(id) {
      var e = d.epics.filter(function (x) { return x.id === id; })[0] || { title: '', body: '', size: 'M', quarter: d.quarters[0], status: 'planned', color: d.colors[d.epics.length % d.colors.length] };
      var m = UI.modal('<h2>' + (id ? 'Edit epic' : 'New epic') + '</h2><form class="ui-stack" data-epicform>' +
        '<label class="ui-field"><span>Name</span><input type="text" name="title" required maxlength="80" value="' + esc(e.title) + '"></label>' +
        '<label class="ui-field"><span>What and why</span><textarea name="body" rows="3" maxlength="1000">' + esc(e.body) + '</textarea></label>' +
        '<div class="ui-grid two"><label class="ui-field"><span>Size</span><select name="size">' + Object.keys(d.sizes).map(function (k) { return '<option value="' + k + '"' + (k === e.size ? ' selected' : '') + '>' + k + ' · about ' + d.sizes[k] + ' pts</option>'; }).join('') + '</select></label>' +
        '<label class="ui-field"><span>Quarter</span><select name="quarter"><option value="">Unscheduled</option>' + d.quarters.concat(e.quarter && d.quarters.indexOf(e.quarter) < 0 ? [e.quarter] : []).map(function (q) {
          return '<option' + (q === e.quarter ? ' selected' : '') + '>' + esc(q) + '</option>'; }).join('') + '</select></label>' +
        '<label class="ui-field"><span>Status</span><select name="status">' + ['idea', 'planned', 'active', 'done'].map(function (s) { return '<option' + (s === e.status ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select></label></div>' +
        '<div class="ui-field"><span>Colour</span><div class="pl-colors">' + d.colors.map(function (c) { return '<label><input type="radio" name="color" value="' + c + '"' + (c === e.color ? ' checked' : '') + '><span style="background:' + c + '"></span></label>'; }).join('') + '</div></div>' +
        '<div class="ui-row end">' + (id ? '<button type="button" class="ui-btn danger" data-delepic>Delete</button><span class="ui-spacer"></span>' : '') +
        '<button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">Save</button></div></form>');
      m.el.querySelector('form').addEventListener('submit', function (ev) {
        ev.preventDefault();
        UI.busy(ev.target.querySelector('[type=submit]'), UI.api('save_epic', crewRef.id, id || null, UI.formData(ev.target))).then(function () { m.close(); UI.toast('Epic saved', 'ok'); load(); });
      });
      var del = m.el.querySelector('[data-delepic]');
      if (del) del.onclick = function () { UI.confirm({ title: 'Delete this epic?', text: 'Its cards stay; they just lose the epic.', ok: 'Delete', danger: true }).then(function (y) { if (y) UI.api('delete_epic', id).then(function () { m.close(); load(); }); }); };
    }

    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-levelup]'))) { UI.busy(t, setLevel(+t.getAttribute('data-levelup'))); return; }
      if ((t = e.target.closest('[data-force]'))) {
        var n = +t.getAttribute('data-force');
        UI.confirm({ title: 'Force level ' + n + '?', text: 'Your crew hasn\'t passed every check. You can still try it, but forecasts will be guesswork until the data catches up. It\'s recorded in the level history.', ok: 'Force it' })
          .then(function (y) { if (y) setLevel(n, true); });
        return;
      }
      if ((t = e.target.closest('[data-down]'))) {
        var dn = +t.getAttribute('data-down');
        UI.confirm({ title: 'Step back to level ' + dn + '?', text: 'Nothing is deleted. Planning views above that level lock again until you level up.', ok: 'Step back' }).then(function (y) { if (y) setLevel(dn); });
        return;
      }
      if ((t = e.target.closest('[data-closesprint]'))) {
        var sid = t.getAttribute('data-closesprint'), a = d.active;
        var m = UI.modal('<h2>Close ' + esc(a.name) + '?</h2><p>' + a.done_points + ' of ' + a.points + ' points are done. Unfinished cards go:</p>' +
          '<div class="ui-choices"><label class="ui-choice"><input type="radio" name="carry" value="next" checked><span>To the next sprint</span></label>' +
          '<label class="ui-choice"><input type="radio" name="carry" value="backlog"><span>Back to the backlog</span></label></div>' +
          '<div class="ui-row end" style="margin-top:18px"><button class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" data-doclose>' + UI.icon('check') + 'Close and run the retro</button></div>');
        m.el.querySelector('[data-doclose]').onclick = function () {
          var carry = m.el.querySelector('input[name=carry]:checked').value;
          UI.busy(m.el.querySelector('[data-doclose]'), UI.api('close_sprint', sid, carry)).then(function (r) {
            m.close();
            AA.rave('SPRINT DONE', r.done_points + ' of ' + r.committed + ' points' + (r.carried ? ', ' + r.carried + ' carried' : ''));
            return load().then(function () { tab = 'sprints'; draw(); setTimeout(function () { retroModal(sid); }, 600); });
          });
        };
        return;
      }
      if ((t = e.target.closest('[data-goal]'))) {
        var gid = t.getAttribute('data-goal');
        var gm = UI.modal('<h2>Sprint goal</h2><form class="ui-stack"><input type="text" name="goal" maxlength="200" value="' + esc(d.active.goal) + '"><div class="ui-row end"><button class="ui-btn primary" type="submit">Save</button></div></form>');
        gm.el.querySelector('form').addEventListener('submit', function (ev) { ev.preventDefault(); UI.api('update_sprint', gid, { goal: UI.formData(ev.target).goal }).then(function () { gm.close(); load(); }); });
        return;
      }
      if ((t = e.target.closest('[data-retro]'))) { retroModal(t.getAttribute('data-retro')); return; }
      if ((t = e.target.closest('[data-editepic]'))) { epicModal(t.getAttribute('data-editepic')); return; }
      if ((t = e.target.closest('[data-erank]'))) { UI.api('rank_epic', t.closest('[data-epic]').getAttribute('data-epic'), t.getAttribute('data-erank')).then(load); return; }
      if ((t = e.target.closest('[data-qmove]'))) {
        var eid = t.closest('[data-epic]').getAttribute('data-epic'), ep = d.epics.filter(function (x) { return x.id === eid; })[0];
        var qs = d.quarters, i = qs.indexOf(ep.quarter), dir = +t.getAttribute('data-qmove');
        var ni = i < 0 ? (dir > 0 ? -1 : qs.length - 1) : i + dir;
        var nq = ni >= 0 && ni < qs.length ? qs[ni] : '';
        UI.api('save_epic', crewRef.id, eid, { quarter: nq }).then(function () { UI.toast(ep.title + ' → ' + (nq || 'later'), 'ok'); load(); });
      }
    });
    return load();
  });
})();

/* ===== profile.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('profile', { title: 'Your profile', auth: 'user' }, function (view, ctx) {
    var me = ctx.me;
    view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="pf-head"><span class="ui-avatar">' + esc(UI.initials(me.name)) + '</span>' +
      '<div><h1>' + esc(me.name) + '</h1><div class="muted">' + esc(me.email) + (me.joined ? ' · member since ' + esc(UI.fmtDate(me.joined, { month: 'long', year: 'numeric' })) : '') + '</div></div></div>' +
      '<div class="pf-grid"><form class="ui-card ui-stack" data-name><h3>Your name</h3><label class="ui-field"><span>Shown to other people</span>' +
      '<input type="text" name="name" value="' + esc(me.name) + '" maxlength="60" required></label><button class="ui-btn primary" type="submit">Save</button></form>' +
      '<div class="ui-card ui-stack"><h3>Appearance</h3><p class="muted small">Follow your device, or pick one.</p><div data-theme-box></div>' +
      '<h3 style="margin-top:22px">Password</h3><p class="muted small">We\'ll email you a link to choose a new one.</p>' +
      '<button class="ui-btn" data-reset>' + UI.icon('mail') + 'Email me a reset link</button></div></div>' +
      '<div class="ui-card" style="margin-top:16px"><div class="pf-links">' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<button data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
      '<button data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms, and your data</button>' +
      '<button data-signout-here>' + UI.icon('logout') + 'Sign out</button></div></div></div>';
    function themeBox() {
      var t = UI.theme();
      view.querySelector('[data-theme-box]').innerHTML = '<div class="ui-seg">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
        return '<button type="button" data-theme-pick="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
      }).join('') + '</div>';
    }
    themeBox();
    view.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-pick]');
      if (t) { UI.setTheme(t.getAttribute('data-theme-pick')); themeBox(); UI.renderChrome(); return; }
      if (e.target.closest('[data-reset]')) {
        UI.busy(e.target.closest('[data-reset]'), UI.auth('reset', { email: me.email })).then(function (r) { UI.toast(r.message, 'ok'); });
      }
      if (e.target.closest('[data-signout-here]')) UI.auth('logout');
    });
    view.querySelector('[data-name]').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target);
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('update_profile', v.name)).then(function (r) {
        UI.setMe(r.me); ctx.me = r.me; UI.toast('Saved', 'ok');
        view.querySelector('.pf-head h1').textContent = r.me.name;
      });
    });
  });
})();

/* ===== reports.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['burnup', 'Burn-up'], ['forecast', 'Forecast'], ['flow', 'Flow'], ['cycle', 'Cycle time'], ['epics', 'Epic map'], ['mix', 'Work mix']];
  var DAY = 864e5, WEEK = 7 * DAY;
  var STAGES = [['done', 'Done', 'var(--ch-1)'], ['review', 'Review', 'var(--ch-2)'], ['doing', 'Doing', 'var(--ch-3)'], ['todo', 'To do', 'var(--ch-4)']];

  /* ---------------------------------------------------------------- data helpers */
  function prep(d) {
    var ms = function (s) { return s ? Date.parse(s) : null; };
    d.nowMs = Date.parse(d.now);
    d.cards.forEach(function (c) { c.cM = ms(c.c); c.stM = ms(c.st); c.rvM = ms(c.rv); c.dM = c.s === 'done' ? ms(c.d) : null; });
    d.firstMs = Math.min.apply(null, d.cards.map(function (c) { return c.cM; }).filter(Boolean).concat([d.nowMs - 12 * WEEK]));
    return d;
  }
  function rangeStart(d, range) {
    if (range === 'all') return d.firstMs;
    return d.nowMs - (+range) * WEEK;
  }
  function days(from, to) {
    var out = [], step = (to - from) > 400 * DAY ? WEEK : DAY;
    for (var t = from; t < to; t += step) out.push(t);
    out.push(to);
    return out;
  }
  /* weekly throughput (cards and points) for the last n weeks, oldest first, skipping weeks before the first finish */
  function weekly(cards, nowMs, n) {
    var out = [];
    for (var i = n - 1; i >= 0; i--) {
      var hi = nowMs - i * WEEK, lo = hi - WEEK, k = 0, p = 0;
      cards.forEach(function (c) { if (c.dM && c.dM > lo && c.dM <= hi) { k++; p += c.p || 0; } });
      out.push({ end: hi, cards: k, points: p });
    }
    while (out.length > 3 && out[0].cards === 0) out.shift();
    return out;
  }
  function rng(seed) {  // mulberry32: the same scope gives the same forecast every time you look
    var a = 0; for (var i = 0; i < seed.length; i++) a = (a * 31 + seed.charCodeAt(i)) | 0;
    return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }
  function pct(sorted, p) { return sorted.length ? sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(p * sorted.length) - 1))] : null; }
  function fmt(ms) { return UI.fmtDate(new Date(ms).toISOString(), { day: 'numeric', month: 'short', year: 'numeric' }); }
  function fmtS(ms) { return UI.fmtDate(new Date(ms).toISOString(), { day: 'numeric', month: 'short' }); }

  /* ---------------------------------------------------------------- chart scaffolding */
  function svgFor(d3, el, h, m) {
    el.innerHTML = '';
    el.classList.add('rp-chart');
    var w = Math.max(280, el.clientWidth || 640);
    var svg = d3.select(el).append('svg').attr('viewBox', '0 0 ' + w + ' ' + h).attr('height', h).attr('role', 'img');
    return { svg: svg, w: w, h: h, m: m, iw: w - m.l - m.r, ih: h - m.t - m.b, g: svg.append('g').attr('transform', 'translate(' + m.l + ',' + m.t + ')') };
  }
  function axes(d3, f, x, y, o) {
    o = o || {};
    f.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).ticks(o.yTicks || 5).tickSize(-f.iw).tickFormat(''));
    f.g.append('g').attr('transform', 'translate(0,' + f.ih + ')').attr('class', 'xaxis')
      .call(d3.axisBottom(x).ticks(Math.max(2, Math.floor(f.iw / 90))).tickFormat(o.xFmt || d3.utcFormat('%b %d')).tickSizeOuter(0));
    f.g.append('g').call(d3.axisLeft(y).ticks(o.yTicks || 5).tickFormat(o.yFmt || d3.format('~s')).tickSizeOuter(0));
  }
  function legend(items) {
    return items.length < 2 ? '' : '<div class="aa-legend">' + items.map(function (s) {
      return '<span><i class="' + (s.kind || '') + '" style="background:' + s.color + '"></i>' + esc(s.name) + '</span>';
    }).join('') + '</div>';
  }
  function crosshair(d3, f, x, pts, rowsFor) {
    var line = f.g.append('line').attr('class', 'xh').attr('y1', 0).attr('y2', f.ih).style('display', 'none');
    var bis = d3.bisector(function (p) { return p.t; }).center;
    f.g.append('rect').attr('width', f.iw).attr('height', f.ih).style('fill', 'transparent').style('cursor', 'crosshair')
      .on('pointermove', function (ev) {
        var mx = d3.pointer(ev, this)[0], i = bis(pts, x.invert(mx)), p = pts[i];
        if (!p) return;
        line.attr('x1', x(p.t)).attr('x2', x(p.t)).style('display', null);
        AA.showTip(ev, fmt(p.t), rowsFor(p));
      })
      .on('pointerleave', function () { line.style('display', 'none'); AA.hideTip(); });
  }

  /* ---------------------------------------------------------------- burn-up */
  function scopeCards(d, scope) {
    if (scope === 'crew') return d.cards;
    if (scope.indexOf('s:') === 0) return d.cards.filter(function (c) { return c.sp === scope.slice(2); });
    return d.cards.filter(function (c) { return c.e === scope.slice(2); });
  }
  function scopeOptions(d) {
    var o = [['crew', 'Whole crew']];
    d.sprints.filter(function (s) { return s.state !== 'closed'; }).concat(d.sprints.filter(function (s) { return s.state === 'closed'; }).slice(-3).reverse())
      .forEach(function (s) { o.push(['s:' + s.id, s.name + (s.state === 'active' ? ' (running)' : s.state === 'planned' ? ' (planned)' : '')]); });
    d.epics.forEach(function (e) { o.push(['e:' + e.id, 'Epic: ' + e.title]); });
    return o;
  }
  function burnup(d3, el, d, st) {
    var cards = scopeCards(d, st.scope), unit = st.unit, val = function (c) { return unit === 'points' ? (c.p || 0) : 1; };
    var sprint = st.scope.indexOf('s:') === 0 ? d.sprints.filter(function (s) { return s.id === st.scope.slice(2); })[0] : null;
    var from = sprint ? Date.parse(sprint.start) : Math.max(rangeStart(d, st.range), Math.min.apply(null, cards.map(function (c) { return c.cM; }).filter(Boolean).concat([d.nowMs])) - DAY);
    var to = sprint && sprint.state === 'closed' ? Date.parse(sprint.end) + DAY : d.nowMs;
    var pts = days(from, to).map(function (t) {
      var scope = 0, done = 0;
      cards.forEach(function (c) { if (sprint || (c.cM && c.cM <= t)) { scope += val(c); if (c.dM && c.dM <= t) done += val(c); } });
      return { t: t, scope: scope, done: done };
    });
    var last = pts[pts.length - 1], left = last.scope - last.done;
    var own = weekly(cards, d.nowMs, 8), crewW = weekly(d.cards, d.nowMs, 8);
    var useOwn = own.filter(function (w) { return w.cards > 0; }).length >= 3, wk = (useOwn ? own : crewW).map(function (w) { return unit === 'points' ? w.points : w.cards; }).sort(d3.ascending);
    var fc = null;
    if (left > 0 && wk.length >= 3 && !(sprint && sprint.state === 'closed')) {
      var lo = Math.max(d3.quantile(wk, 0.15), 0.25), mid = Math.max(d3.quantile(wk, 0.5), 0.25), hi = Math.max(d3.quantile(wk, 0.85), 0.5);
      if (!useOwn && st.scope !== 'crew') {  // a part of the crew's work gets a part of its throughput
        var share = Math.max(0.15, Math.min(1, cards.filter(function (c) { return c.dM && c.dM > d.nowMs - 8 * WEEK; }).length / Math.max(1, d.cards.filter(function (c) { return c.dM && c.dM > d.nowMs - 8 * WEEK; }).length)));
        lo *= share; mid *= share; hi *= share;
      }
      var cap = 52 * WEEK;
      fc = { early: d.nowMs + Math.min(cap, left / hi * WEEK), likely: d.nowMs + Math.min(cap, left / mid * WEEK), late: d.nowMs + Math.min(cap, left / lo * WEEK), lo: lo, mid: mid, hi: hi };
    }
    var xMax = fc ? Math.max(to, fc.late) : (sprint ? Math.max(to, Date.parse(sprint.end) + DAY) : to);
    var budget = st.scope.indexOf('e:') === 0 && unit === 'points' ? (d.epics.filter(function (e) { return 'e:' + e.id === st.scope; })[0] || {}).budget : null;
    var f = svgFor(d3, el, innerWidth < 600 ? 250 : 320, { l: 40, r: 70, t: 14, b: 28 });
    var x = d3.scaleUtc().domain([from, xMax]).range([0, f.iw]);
    var y = d3.scaleLinear().domain([0, Math.max(1, last.scope, budget || 0) * 1.08]).nice().range([f.ih, 0]);
    axes(d3, f, x, y);
    f.svg.attr('aria-label', 'Burn-up: ' + last.done + ' of ' + last.scope + ' ' + unit + ' done');
    if (fc) {
      f.g.append('path').datum([{ t: d.nowMs, y0: last.done, y1: last.done }, { t: fc.early, y0: last.done + fc.lo * (fc.early - d.nowMs) / WEEK, y1: last.scope }, { t: fc.late, y0: last.scope, y1: last.scope }])
        .attr('d', d3.area().x(function (p) { return x(p.t); }).y0(function (p) { return y(p.y0); }).y1(function (p) { return y(p.y1); }))
        .style('fill', 'var(--ch-1)').style('opacity', .14);
      f.g.append('line').attr('x1', x(d.nowMs)).attr('y1', y(last.done)).attr('x2', x(fc.likely)).attr('y2', y(last.scope))
        .style('stroke', 'var(--ch-1)').style('stroke-width', 2).style('stroke-dasharray', '6 5');
      f.g.append('text').attr('class', 'lbl').attr('x', x(fc.likely) + 6).attr('y', y(last.scope) + 16).text('likely ' + fmtS(fc.likely));
    }
    if (budget) {
      f.g.append('line').attr('x1', 0).attr('x2', f.iw).attr('y1', y(budget)).attr('y2', y(budget)).style('stroke', 'var(--c-muted)').style('stroke-dasharray', '3 4');
      f.g.append('text').attr('class', 'lbl muted').attr('x', f.iw + 4).attr('y', y(budget) + 4).text('size ' + budget);
    }
    f.g.append('path').datum(pts).attr('d', d3.area().x(function (p) { return x(p.t); }).y0(f.ih).y1(function (p) { return y(p.done); }).curve(d3.curveMonotoneX))
      .style('fill', 'var(--ch-1)').style('opacity', .12);
    f.g.append('path').datum(pts).attr('d', d3.line().x(function (p) { return x(p.t); }).y(function (p) { return y(p.scope); }).curve(d3.curveStepAfter))
      .style('fill', 'none').style('stroke', 'var(--ch-2)').style('stroke-width', 2);
    f.g.append('path').datum(pts).attr('d', d3.line().x(function (p) { return x(p.t); }).y(function (p) { return y(p.done); }).curve(d3.curveMonotoneX))
      .style('fill', 'none').style('stroke', 'var(--ch-1)').style('stroke-width', 2.5);
    f.g.append('line').attr('x1', x(d.nowMs)).attr('x2', x(d.nowMs)).attr('y1', 0).attr('y2', f.ih).style('stroke', 'var(--c-faint)').style('stroke-dasharray', '2 3');
    f.g.append('text').attr('class', 'lbl muted').attr('x', x(d.nowMs) + 4).attr('y', f.ih - 6).text('today');
    f.g.append('text').attr('class', 'lbl').attr('x', Math.min(f.iw + 4, x(to) + 4)).attr('y', y(last.scope) - 6).text('scope ' + last.scope);
    f.g.append('text').attr('class', 'lbl').attr('x', x(to) + 8).attr('y', y(last.done) + 18).text('done ' + last.done);
    f.g.append('circle').attr('cx', x(to)).attr('cy', y(last.done)).attr('r', 5).style('fill', 'var(--ch-1)').style('stroke', 'var(--c-surface)').style('stroke-width', 2);
    crosshair(d3, f, x, pts, function (p) { return [{ value: p.done, label: 'done', color: 'var(--ch-1)' }, { value: p.scope, label: 'scope', color: 'var(--ch-2)' }]; });
    return {
      kpis: [[last.done + '<small>/' + last.scope + '</small>', unit + ' done'], [last.scope ? Math.round(100 * last.done / last.scope) + '<small>%</small>' : '--', 'complete', 'cyan'],
        [fc ? esc(fmtS(fc.likely)) : (left <= 0 ? 'DONE' : '--'), fc ? 'likely finish' : (left <= 0 ? 'all of it' : 'need 3 weeks of finishes'), 'pink'],
        [fc ? esc(fmtS(fc.early)) + '–' + esc(fmtS(fc.late)) : '--', '70% range', 'amber']],
      legend: [{ name: 'Done', color: 'var(--ch-1)', kind: 'line' }, { name: 'Scope', color: 'var(--ch-2)', kind: 'line' }].concat(fc ? [{ name: 'Forecast (dashed: likely; band: 15th–85th percentile weeks)', color: 'var(--ch-1)', kind: 'dash' }] : []),
      note: fc ? 'At your recent pace (' + (Math.round(fc.mid * 10) / 10) + ' ' + unit + ' a week' + (useOwn ? '' : ', a share of the crew\'s') + '), the last ' + left + ' ' + unit + ' land around ' + fmt(fc.likely) +
        '. A slow week pattern says ' + fmt(fc.late) + ', a fast one ' + fmt(fc.early) + '. Scope that grows moves the line up: watch the pink steps.' :
        (left <= 0 ? 'Everything in scope is done.' : 'The forecast appears after three weeks with finished cards.'),
      table: [['Date', 'Scope', 'Done'], pts.filter(function (p, i) { return i % Math.max(1, Math.round(pts.length / 40)) === 0 || i === pts.length - 1; }).map(function (p) { return [new Date(p.t).toISOString().slice(0, 10), p.scope, p.done]; })]
    };
  }

  /* ---------------------------------------------------------------- Monte Carlo */
  function forecast(d3, el, d, st) {
    var samples = weekly(d.cards, d.nowMs, 12).map(function (w) { return w.cards; });
    var open = function (cs) { return cs.filter(function (c) { return c.s !== 'done'; }).length; };
    var n = st.fscope === 'custom' ? Math.max(1, +st.custom || 10) : open(scopeCards(d, st.fscope));
    if (samples.length < 3 || !samples.some(function (s) { return s > 0; })) {
      el.innerHTML = '<div class="rp-err muted">Monte Carlo needs at least three weeks with finished cards. Keep pulling cards to Done.</div>';
      return { kpis: [], note: '', table: [['Week', 'Cards'], []] };
    }
    var r = rng(d.crew.key + st.fscope + n + st.mode + st.date), RUNS = 5000, out = [];
    var target = st.mode === 'howmany' ? Date.parse(st.date) : null, wks = target ? Math.max(1, Math.round((target - d.nowMs) / WEEK)) : 0;
    for (var i = 0; i < RUNS; i++) {
      if (st.mode === 'howmany') {
        var got = 0; for (var k = 0; k < wks; k++) got += samples[Math.floor(r() * samples.length)];
        out.push(got);
      } else {
        var left = n, w = 0;
        while (left > 0 && w < 104) { left -= samples[Math.floor(r() * samples.length)]; w++; }
        out.push(w);
      }
    }
    out.sort(d3.ascending);
    var bins = d3.rollups(out, function (v) { return v.length; }, function (v) { return v; }).sort(function (a, b) { return a[0] - b[0]; });
    var f = svgFor(d3, el, innerWidth < 600 ? 240 : 300, { l: 44, r: 16, t: 26, b: 34 });
    var x = d3.scaleBand().domain(bins.map(function (b) { return b[0]; })).range([0, f.iw]).padding(0.15);
    var y = d3.scaleLinear().domain([0, d3.max(bins, function (b) { return b[1]; }) / RUNS * 100 * 1.12]).nice().range([f.ih, 0]);
    f.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).ticks(4).tickSize(-f.iw).tickFormat(''));
    var every = Math.ceil(bins.length / Math.max(2, Math.floor(f.iw / 46)));
    f.g.append('g').attr('transform', 'translate(0,' + f.ih + ')').call(d3.axisBottom(x).tickValues(x.domain().filter(function (v, i) { return i % every === 0; }))
      .tickFormat(function (v) { return st.mode === 'howmany' ? v : fmtS(d.nowMs + v * WEEK); }).tickSizeOuter(0));
    f.g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(function (v) { return v + '%'; }).tickSizeOuter(0));
    var p50 = pct(out, 0.5), p85 = pct(out, 0.85), p95 = pct(out, 0.95), q15 = pct(out, 0.15), q05 = pct(out, 0.05);
    var good = function (v) { return st.mode === 'howmany' ? v >= q15 : v <= p85; };
    f.g.selectAll('rect.bar').data(bins).join('rect').attr('class', 'bar')
      .attr('x', function (b) { return x(b[0]); }).attr('width', x.bandwidth()).attr('y', function (b) { return y(b[1] / RUNS * 100); })
      .attr('height', function (b) { return f.ih - y(b[1] / RUNS * 100); }).attr('rx', Math.min(4, x.bandwidth() / 3))
      .style('fill', function (b) { return good(b[0]) ? 'var(--ch-1)' : 'var(--ch-3)'; })
      .on('pointermove', function (ev, b) {
        var cum = out.filter(function (v) { return st.mode === 'howmany' ? v >= b[0] : v <= b[0]; }).length / RUNS * 100;
        AA.showTip(ev, st.mode === 'howmany' ? b[0] + ' cards by ' + fmt(target) : 'Done in week ' + b[0] + ' (by ' + fmt(d.nowMs + b[0] * WEEK) + ')',
          [{ value: (b[1] / RUNS * 100).toFixed(1) + '%', label: 'of runs land here', color: good(b[0]) ? 'var(--ch-1)' : 'var(--ch-3)' },
           { value: Math.round(cum) + '%', label: st.mode === 'howmany' ? 'chance of at least this many' : 'chance of being done by then' }]);
      }).on('pointerleave', AA.hideTip);
    var marks = st.mode === 'howmany' ? [[q05, '95%'], [q15, '85%'], [p50, '50%']] : [[p50, '50%'], [p85, '85%'], [p95, '95%']];
    marks.forEach(function (mk) {
      if (x(mk[0]) == null) return;
      var xx = x(mk[0]) + x.bandwidth() / 2;
      f.g.append('line').attr('x1', xx).attr('x2', xx).attr('y1', -6).attr('y2', f.ih).style('stroke', 'var(--c-ink)').style('stroke-dasharray', '3 3').style('opacity', .6);
      f.g.append('text').attr('class', 'lbl').attr('x', xx).attr('y', -10).attr('text-anchor', 'middle').text(mk[1]);
    });
    f.svg.attr('aria-label', 'Monte Carlo forecast histogram');
    if (st.mode === 'howmany') {
      return { kpis: [[q15, '85% sure: at least', 'cyan'], [p50, 'coin flip: at least', 'pink'], [q05, '95% sure: at least'], [wks + '<small>wk</small>', 'until ' + esc(fmtS(target)), 'amber']],
        legend: [{ name: 'At least the 85% number', color: 'var(--ch-1)' }, { name: 'Less likely', color: 'var(--ch-3)' }],
        note: 'By ' + fmt(target) + ' you will very likely (85%) finish at least ' + q15 + ' cards, and at least ' + p50 + ' half the time. ' +
          'Monte Carlo replays your real weeks (' + samples.join(', ') + ' cards) 5,000 times in random order. No estimates needed.',
        table: [['Cards finished', 'Share of runs'], bins.map(function (b) { return [b[0], (b[1] / RUNS * 100).toFixed(1) + '%']; })] };
    }
    return { kpis: [[esc(fmtS(d.nowMs + p85 * WEEK)), '85% sure by', 'cyan'], [esc(fmtS(d.nowMs + p50 * WEEK)), 'coin flip by', 'pink'],
      [esc(fmtS(d.nowMs + p95 * WEEK)), '95% sure by'], [n, 'cards to finish', 'amber']],
      legend: [{ name: 'Done within the 85% date', color: 'var(--ch-1)' }, { name: 'Later than that', color: 'var(--ch-3)' }],
      note: n + ' cards: there is an 85% chance they are all done by ' + fmt(d.nowMs + p85 * WEEK) + ' and a 50% chance by ' + fmt(d.nowMs + p50 * WEEK) + '. ' +
        'Monte Carlo replays your real weeks (' + samples.join(', ') + ' cards) 5,000 times in random order. No estimates needed: it counts cards.',
      table: [['Finished in week', 'By date', 'Share of runs'], bins.map(function (b) { return [b[0], new Date(d.nowMs + b[0] * WEEK).toISOString().slice(0, 10), (b[1] / RUNS * 100).toFixed(1) + '%']; })] };
  }

  /* ---------------------------------------------------------------- cumulative flow + brush */
  function flowSeries(d, from, to) {
    return days(from, to).map(function (t) {
      var o = { t: t, todo: 0, doing: 0, review: 0, done: 0 };
      d.cards.forEach(function (c) {
        if (!c.cM || c.cM > t) return;
        if (c.dM && c.dM <= t) o.done++;
        else if (c.rvM && c.rvM <= t && c.s !== 'backlog' && c.s !== 'ready') o.review++;
        else if (c.stM && c.stM <= t && c.s !== 'backlog' && c.s !== 'ready') o.doing++;
        else o.todo++;
      });
      return o;
    });
  }
  function flow(d3, el, d, st) {
    var from = rangeStart(d, st.range), pts = flowSeries(d, from, d.nowMs);
    var keys = STAGES.map(function (s) { return s[0]; });
    var stack = d3.stack().keys(keys)(pts);
    var wrap = el; wrap.innerHTML = '<div data-main></div><div data-mini></div><p class="rp-cap">Drag across the strip underneath to zoom in. Double-click it to zoom out.</p>';
    var main = wrap.querySelector('[data-main]'), mini = wrap.querySelector('[data-mini]');
    var f = svgFor(d3, main, innerWidth < 600 ? 240 : 300, { l: 40, r: 64, t: 10, b: 26 });
    var x = d3.scaleUtc().domain([from, d.nowMs]).range([0, f.iw]);
    var y = d3.scaleLinear().domain([0, d3.max(stack[stack.length - 1], function (p) { return p[1]; }) || 1]).nice().range([f.ih, 0]);
    var clipId = 'rpclip' + Math.round(Math.random() * 1e6);
    f.svg.append('defs').append('clipPath').attr('id', clipId).append('rect').attr('width', f.iw).attr('height', f.ih).attr('transform', 'translate(' + f.m.l + ',' + f.m.t + ')');
    f.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).ticks(5).tickSize(-f.iw).tickFormat(''));
    var xAxis = f.g.append('g').attr('transform', 'translate(0,' + f.ih + ')');
    f.g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('~s')).tickSizeOuter(0));
    var layer = f.svg.append('g').attr('clip-path', 'url(#' + clipId + ')').append('g').attr('transform', 'translate(' + f.m.l + ',' + f.m.t + ')');
    var area = d3.area().x(function (p) { return x(p.data.t); }).y0(function (p) { return y(p[0]); }).y1(function (p) { return y(p[1]); }).curve(d3.curveMonotoneX);
    var paths = layer.selectAll('path').data(stack).join('path').style('fill', function (s) { return STAGES[keys.indexOf(s.key)][2]; })
      .style('stroke', 'var(--c-surface)').style('stroke-width', 2);
    var labels = f.g.append('g');
    function redraw() {
      xAxis.call(d3.axisBottom(x).ticks(Math.max(2, Math.floor(f.iw / 90))).tickFormat(d3.utcFormat('%b %d')).tickSizeOuter(0));
      paths.attr('d', area);
      labels.selectAll('*').remove();
      var lastP = stack.map(function (s, i) { var p = s[s.length - 1]; return { i: i, n: p[1] - p[0], y: y((p[0] + p[1]) / 2) + 4 }; }).filter(function (l) { return l.n > 0; });
      lastP.sort(function (a, b) { return b.y - a.y; });
      for (var k = 1; k < lastP.length; k++) if (lastP[k - 1].y - lastP[k].y < 15) lastP[k].y = lastP[k - 1].y - 15;  // no overlapping labels
      lastP.forEach(function (l) { labels.append('text').attr('class', 'lbl').attr('x', f.iw + 4).attr('y', l.y).text(STAGES[l.i][1] + ' ' + l.n); });
    }
    redraw();
    crosshair(d3, f, x, pts, function (p) { return STAGES.map(function (s) { return { value: p[s[0]], label: s[1], color: s[2] }; }); });
    // overview strip with a brush
    var g2 = svgFor(d3, mini, 54, { l: 40, r: 64, t: 4, b: 18 });
    var x2 = d3.scaleUtc().domain(x.domain()).range([0, g2.iw]), y2 = d3.scaleLinear().domain(y.domain()).range([g2.ih, 0]);
    g2.g.append('path').datum(stack[stack.length - 1]).attr('d', d3.area().x(function (p) { return x2(p.data.t); }).y0(g2.ih).y1(function (p) { return y2(p[1]); }))
      .style('fill', 'var(--ch-1)').style('opacity', .45);
    g2.g.append('g').attr('transform', 'translate(0,' + g2.ih + ')').call(d3.axisBottom(x2).ticks(Math.max(2, Math.floor(g2.iw / 110))).tickFormat(d3.utcFormat('%b %d')).tickSizeOuter(0));
    var brush = d3.brushX().extent([[0, 0], [g2.iw, g2.ih]]).on('end', function (ev) {
      if (!ev.selection) { x.domain(x2.domain()); } else { x.domain(ev.selection.map(x2.invert)); }
      redraw();
    });
    g2.g.append('g').attr('class', 'brush').call(brush).on('dblclick', function () { g2.g.select('.brush').call(brush.move, null); });
    f.svg.attr('aria-label', 'Cumulative flow');
    var last = pts[pts.length - 1], wk = weekly(d.cards, d.nowMs, 8), tp = d3.mean(wk, function (w) { return w.cards; }) || 0, wip = last.doing + last.review;
    return {
      kpis: [[wip, 'in progress now'], [Math.round(tp * 10) / 10 + '<small>/wk</small>', 'finished per week', 'cyan'],
        [tp ? Math.round(wip / tp * 7 * 10) / 10 + '<small>d</small>' : '--', 'expected wait (WIP ÷ rate)', 'pink'], [last.todo, 'waiting to start', 'amber']],
      legend: STAGES.map(function (s) { return { name: s[1], color: s[2] }; }),
      note: 'Each band is how many cards sat in that stage on that day. Parallel bands mean smooth flow; a widening Doing or Review band means work is starting faster than it finishes. ' +
        'Little\'s law: with ' + wip + ' cards in progress and about ' + (Math.round(tp * 10) / 10) + ' finished a week, a new card waits about ' + (tp ? Math.round(wip / tp * 7) : '?') + ' days.',
      table: [['Date', 'To do', 'Doing', 'Review', 'Done'], pts.filter(function (p, i) { return i % Math.max(1, Math.round(pts.length / 40)) === 0 || i === pts.length - 1; })
        .map(function (p) { return [new Date(p.t).toISOString().slice(0, 10), p.todo, p.doing, p.review, p.done]; })]
    };
  }

  /* ---------------------------------------------------------------- control chart */
  function cycle(d3, el, d, st) {
    var from = rangeStart(d, st.range);
    var pts = d.cards.filter(function (c) { return c.dM && c.stM && c.dM >= from; }).map(function (c) { return { c: c, t: c.dM, v: Math.max(0.05, (c.dM - c.stM) / DAY) }; })
      .sort(function (a, b) { return a.t - b.t; });
    if (pts.length < 2) { el.innerHTML = '<div class="rp-err muted">Cycle times appear once cards go from Doing to Done.</div>'; return { kpis: [], note: '', table: [['Card', 'Days'], []] }; }
    var vals = pts.map(function (p) { return p.v; }).sort(d3.ascending), p50 = d3.quantile(vals, 0.5), p85 = d3.quantile(vals, 0.85);
    var f = svgFor(d3, el, innerWidth < 600 ? 260 : 320, { l: 40, r: 50, t: 12, b: 26 });
    var x0 = d3.scaleUtc().domain([from, d.nowMs]).range([0, f.iw]), x = x0.copy();
    var y = d3.scaleSymlog().constant(1).domain([0, d3.max(vals) * 1.1]).range([f.ih, 0]);
    var ticks = [0, 1, 2, 5, 10, 20, 50, 100].filter(function (t) { return t <= y.domain()[1]; });
    f.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).tickValues(ticks).tickSize(-f.iw).tickFormat(''));
    f.g.append('g').call(d3.axisLeft(y).tickValues(ticks).tickFormat(function (v) { return v + 'd'; }).tickSizeOuter(0));
    var xAxis = f.g.append('g').attr('transform', 'translate(0,' + f.ih + ')');
    var clipId = 'rpclipc' + Math.round(Math.random() * 1e6);
    f.svg.append('defs').append('clipPath').attr('id', clipId).append('rect').attr('x', -6).attr('y', -6).attr('width', f.iw + 12).attr('height', f.ih + 12);
    var plot = f.g.append('g').attr('clip-path', 'url(#' + clipId + ')');
    [[p50, '50%'], [p85, '85%']].forEach(function (r) {
      f.g.append('line').attr('x1', 0).attr('x2', f.iw).attr('y1', y(r[0])).attr('y2', y(r[0])).style('stroke', 'var(--c-muted)').style('stroke-dasharray', '4 4');
      f.g.append('text').attr('class', 'lbl muted').attr('x', f.iw + 4).attr('y', y(r[0]) + 4).text(r[1] + ' ' + (Math.round(r[0] * 10) / 10) + 'd');
    });
    var roll = pts.map(function (p, i) { var win = pts.slice(Math.max(0, i - 9), i + 1); return { t: p.t, v: d3.mean(win, function (q) { return q.v; }) }; });
    var rline = plot.append('path').datum(roll).style('fill', 'none').style('stroke', 'var(--c-ink)').style('stroke-width', 1.5).style('opacity', .55);
    var dots = plot.selectAll('circle').data(pts).join('circle').attr('class', 'dot').attr('r', 5)
      .style('fill', function (p) { return p.c.a ? 'var(--ch-3)' : 'var(--ch-2)'; }).style('stroke', 'var(--c-surface)').style('stroke-width', 2)
      .on('pointermove', function (ev, p) {
        AA.showTip(ev, p.c.k + ' · ' + (p.c.p == null ? '?' : p.c.p) + ' pts · ' + (p.c.w || 'unassigned'), [{ value: (Math.round(p.v * 10) / 10) + 'd', label: p.c.t, color: p.c.a ? 'var(--ch-3)' : 'var(--ch-2)' }]);
      }).on('pointerleave', AA.hideTip).on('click', function (ev, p) { AA.hideTip(); UI.go('card', p.c.k); });
    function redraw() {
      xAxis.call(d3.axisBottom(x).ticks(Math.max(2, Math.floor(f.iw / 90))).tickFormat(d3.utcFormat('%b %d')).tickSizeOuter(0));
      dots.attr('cx', function (p) { return x(p.t); }).attr('cy', function (p) { return y(p.v); });
      rline.attr('d', d3.line().x(function (p) { return x(p.t); }).y(function (p) { return y(p.v); }).curve(d3.curveMonotoneX));
    }
    redraw();
    var zoom = d3.zoom().scaleExtent([1, 12]).translateExtent([[0, 0], [f.iw, f.ih]]).extent([[0, 0], [f.iw, f.ih]])
      .filter(function (ev) { return ev.type !== 'wheel' || ev.ctrlKey || ev.shiftKey; })
      .on('zoom', function (ev) { x = ev.transform.rescaleX(x0); redraw(); });
    f.svg.call(zoom).on('dblclick.zoom', function () { f.svg.transition().duration(250).call(zoom.transform, d3.zoomIdentity); });
    f.svg.attr('aria-label', 'Cycle time control chart');
    var ag = pts.filter(function (p) { return p.c.a; }).map(function (p) { return p.v; }).sort(d3.ascending), hu = pts.filter(function (p) { return !p.c.a; }).map(function (p) { return p.v; }).sort(d3.ascending);
    var slow = pts.filter(function (p) { return p.v > p85; }).sort(function (a, b) { return b.v - a.v; }).slice(0, 3);
    return {
      kpis: [[Math.round(p50 * 10) / 10 + '<small>d</small>', 'half finish within'], [Math.round(p85 * 10) / 10 + '<small>d</small>', '85% finish within', 'pink'],
        [hu.length ? Math.round(d3.quantile(hu, 0.5) * 10) / 10 + '<small>d</small>' : '--', 'humans, median', 'cyan'], [ag.length ? Math.round(d3.quantile(ag, 0.5) * 10) / 10 + '<small>d</small>' : '--', 'agents, median', 'amber']],
      legend: [{ name: 'Humans', color: 'var(--ch-2)' }, { name: 'Agents', color: 'var(--ch-3)' }, { name: 'Rolling average (10 cards)', color: 'var(--c-ink)', kind: 'line' }],
      note: 'Each dot is a finished card: days from start to done. Use the 85% line when someone asks "when will it be done?": ' + Math.round(p85) + ' days covers most cards. ' +
        (slow.length ? 'Slowest: ' + slow.map(function (p) { return p.c.k + ' (' + Math.round(p.v) + 'd)'; }).join(', ') + '. ' : '') + 'Shift + scroll or drag to zoom, double-click to reset, click a dot to open the card.',
      table: [['Card', 'Finished', 'Days', 'Points', 'By'], pts.slice().reverse().map(function (p) { return [p.c.k, new Date(p.t).toISOString().slice(0, 10), Math.round(p.v * 10) / 10, p.c.p == null ? '' : p.c.p, p.c.w || '']; })]
    };
  }

  /* ---------------------------------------------------------------- epic treemap */
  function stageOf(c) { return c.s === 'done' ? 'done' : c.s === 'review' ? 'review' : c.s === 'doing' ? 'doing' : 'todo'; }
  function epics(d3, el, d, st) {
    var groups = d.epics.map(function (e) { return { e: e, cards: d.cards.filter(function (c) { return c.e === e.id; }) }; });
    groups.push({ e: { id: 'none', title: 'No epic', color: '#888' }, cards: d.cards.filter(function (c) { return !c.e && c.s !== 'done'; }) });
    if (st.open) groups.forEach(function (g) { g.cards = g.cards.filter(function (c) { return c.s !== 'done'; }); });
    groups = groups.filter(function (g) { return g.cards.length; });
    if (!groups.length) { el.innerHTML = '<div class="rp-err muted">No cards to map yet.</div>'; return { kpis: [], note: '', table: [['Epic'], []] }; }
    var root = d3.hierarchy({ children: groups.map(function (g) { return { g: g, children: g.cards.map(function (c) { return { c: c, value: c.p || 1 }; }) }; }) })
      .sum(function (n) { return n.value || 0; }).sort(function (a, b) { return b.value - a.value; });
    var f = svgFor(d3, el, innerWidth < 600 ? 420 : 460, { l: 0, r: 0, t: 0, b: 0 });
    d3.treemap().size([f.iw, f.ih]).paddingOuter(3).paddingTop(20).paddingInner(2).round(true)(root);
    var fill = {}; STAGES.forEach(function (s) { fill[s[0]] = s[2]; });
    var ep = f.g.selectAll('g.ep').data(root.children).join('g').attr('class', 'ep');
    ep.append('rect').attr('x', function (n) { return n.x0; }).attr('y', function (n) { return n.y0; }).attr('width', function (n) { return n.x1 - n.x0; })
      .attr('height', function (n) { return n.y1 - n.y0; }).style('fill', 'var(--c-surface-2)').style('stroke', 'var(--c-edge)').style('stroke-width', 2);
    ep.append('rect').attr('x', function (n) { return n.x0; }).attr('y', function (n) { return n.y0; }).attr('width', 5).attr('height', function (n) { return n.y1 - n.y0; })
      .style('fill', function (n) { return n.data.g.e.color; });
    ep.append('text').attr('class', 'tm-head').attr('x', function (n) { return n.x0 + 10; }).attr('y', function (n) { return n.y0 + 14; })
      .text(function (n) {
        var w = n.x1 - n.x0 - 16, done = n.data.g.cards.filter(function (c) { return c.s === 'done'; }).reduce(function (a, c) { return a + (c.p || 1); }, 0);
        var t = n.data.g.e.title + ' · ' + Math.round(100 * done / n.value) + '%';
        return w < 40 ? '' : t.length * 8.2 > w ? t.slice(0, Math.max(1, Math.floor(w / 8.2) - 1)) + '…' : t;
      });
    f.g.selectAll('rect.tm-leaf').data(root.leaves()).join('rect').attr('class', 'tm-leaf')
      .attr('x', function (n) { return n.x0; }).attr('y', function (n) { return n.y0; }).attr('width', function (n) { return Math.max(0, n.x1 - n.x0); })
      .attr('height', function (n) { return Math.max(0, n.y1 - n.y0); }).attr('rx', 2).style('fill', function (n) { return fill[stageOf(n.data.c)]; })
      .on('pointermove', function (ev, n) {
        var c = n.data.c;
        AA.showTip(ev, c.k + ' · ' + n.parent.data.g.e.title, [{ value: c.p == null ? '?' : c.p, label: 'pts · ' + AA.STATUS[c.s] + ' · ' + c.t, color: fill[stageOf(c)] }]);
      }).on('pointerleave', AA.hideTip).on('click', function (ev, n) { AA.hideTip(); UI.go('card', n.data.c.k); });
    f.svg.attr('aria-label', 'Epic map');
    var rows = groups.map(function (g) {
      var pts = g.cards.reduce(function (a, c) { return a + (c.p || 0); }, 0), done = g.cards.filter(function (c) { return c.s === 'done'; }).reduce(function (a, c) { return a + (c.p || 0); }, 0);
      return [g.e.title, g.cards.length, pts, done, pts ? Math.round(100 * done / pts) + '%' : '', g.e.size || ''];
    });
    var biggest = root.children[0];
    return {
      kpis: [[groups.length, 'epics with cards'], [root.leaves().length, st.open ? 'open cards' : 'cards', 'cyan'],
        [Math.round(root.value), 'points (unestimated = 1)', 'pink'], [esc(biggest.data.g.e.title.length > 14 ? biggest.data.g.e.title.slice(0, 13) + '…' : biggest.data.g.e.title), 'biggest', 'amber']],
      legend: STAGES.map(function (s) { return { name: s[1], color: s[2] }; }),
      note: 'Every box is a card, sized by its points (unestimated cards count as 1) and coloured by stage. Big pale areas are work nobody has started. Click a box to open the card.',
      table: [['Epic', 'Cards', 'Points', 'Done points', 'Done', 'Size'], rows]
    };
  }

  /* ---------------------------------------------------------------- work mix */
  function mix(d3, el, d, st) {
    var weeks = st.range === 'all' ? Math.min(52, Math.ceil((d.nowMs - d.firstMs) / WEEK)) : +st.range;
    var series = st.by === 'who' ? [['human', 'Humans', 'var(--ch-2)'], ['agent', 'Agents', 'var(--ch-3)']]
      : [['story', 'Features', 'var(--ch-1)'], ['bug', 'Bugs', 'var(--ch-2)'], ['other', 'Other work', 'var(--ch-3)']];
    var keyOf = function (c) { return st.by === 'who' ? (c.a ? 'agent' : 'human') : (c.y === 'story' || c.y === 'bug' ? c.y : 'other'); };
    var data = [];
    for (var i = weeks - 1; i >= 0; i--) {
      var hi = d.nowMs - i * WEEK, lo = hi - WEEK, o = { t: lo };
      series.forEach(function (s) { o[s[0]] = 0; });
      d.cards.forEach(function (c) { if (c.dM && c.dM > lo && c.dM <= hi) o[keyOf(c)] += st.unit === 'points' ? (c.p || 0) : 1; });
      data.push(o);
    }
    var stack = d3.stack().keys(series.map(function (s) { return s[0]; }))(data);
    var f = svgFor(d3, el, innerWidth < 600 ? 240 : 300, { l: 40, r: 12, t: 12, b: 26 });
    var x = d3.scaleBand().domain(data.map(function (o) { return o.t; })).range([0, f.iw]).padding(0.25);
    var y = d3.scaleLinear().domain([0, d3.max(stack[stack.length - 1], function (p) { return p[1]; }) || 1]).nice().range([f.ih, 0]);
    f.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).ticks(5).tickSize(-f.iw).tickFormat(''));
    var every = Math.ceil(data.length / Math.max(2, Math.floor(f.iw / 70)));
    f.g.append('g').attr('transform', 'translate(0,' + f.ih + ')').call(d3.axisBottom(x).tickValues(x.domain().filter(function (v, i) { return i % every === 0; })).tickFormat(function (v) { return fmtS(v); }).tickSizeOuter(0));
    f.g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('~s')).tickSizeOuter(0));
    f.g.selectAll('g.layer').data(stack).join('g').attr('class', 'layer').style('fill', function (s, i) { return series[i][2]; })
      .selectAll('rect').data(function (s) { return s; }).join('rect')
      .attr('x', function (p) { return x(p.data.t); }).attr('width', x.bandwidth()).attr('y', function (p) { return y(p[1]); })
      .attr('height', function (p) { return Math.max(0, y(p[0]) - y(p[1]) - (p[1] > p[0] ? 2 : 0)); })
      .on('pointermove', function (ev, p) {
        AA.showTip(ev, 'Week of ' + fmt(p.data.t), series.slice().reverse().map(function (s) { return { value: p.data[s[0]], label: s[1], color: s[2] }; }));
      }).on('pointerleave', AA.hideTip);
    f.svg.attr('aria-label', 'Work mix per week');
    var sum = function (arr, k) { return arr.reduce(function (a, o) { return a + o[k]; }, 0); };
    var tot = function (arr) { return series.reduce(function (a, s) { return a + sum(arr, s[0]); }, 0); };
    var recent = data.slice(-4), before = data.slice(0, -4), focus = st.by === 'who' ? 'agent' : 'bug';
    var share = function (arr) { var t = tot(arr); return t ? Math.round(100 * sum(arr, focus) / t) : null; };
    var sr = share(recent), sb = share(before);
    return {
      kpis: series.map(function (s, i) { return [sum(data, s[0]), s[1] + ' (' + st.unit + ')', ['', 'pink', 'cyan'][i]]; }).concat([[sr == null ? '--' : sr + '<small>%</small>', (st.by === 'who' ? 'agent' : 'bug') + ' share, last 4 wk', 'amber']]),
      legend: series.map(function (s) { return { name: s[1], color: s[2] }; }),
      note: st.by === 'who' ? 'Who finished the work each week. ' + (sr != null ? 'Agents did ' + sr + '% of it in the last 4 weeks' + (sb != null ? ' (' + sb + '% before).' : '.') : '')
        : 'What the crew finished each week. ' + (sr != null ? 'Bugs were ' + sr + '% of it in the last 4 weeks' + (sb != null ? ' (' + sb + '% before)' : '') + '. A rising bug share eats into feature time.' : ''),
      table: [['Week of'].concat(series.map(function (s) { return s[1]; })), data.map(function (o) { return [new Date(o.t).toISOString().slice(0, 10)].concat(series.map(function (s) { return o[s[0]]; })); })]
    };
  }

  var DRAW = { burnup: burnup, forecast: forecast, flow: flow, cycle: cycle, epics: epics, mix: mix };
  var INTRO = {
    burnup: 'How much is done against how much there is, over time, and when the rest will likely land.',
    forecast: 'Forecasts from your real weekly throughput. No story points needed.',
    flow: 'Where work piles up: cards per stage, every day.',
    cycle: 'How long cards take from start to done, and which ones were outliers.',
    epics: 'All the work at a glance: epics, their cards, and what is done.',
    mix: 'What kind of work the crew finished each week, and who finished it.'
  };

  UI.page('reports', { title: 'Reports', nav: 'Reports', icon: 'chart', auth: 'user', order: 60 }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'burnup';
    var st = UI.store.get('rp.st', {});
    st = { range: st.range || '12', unit: st.unit || 'cards', scope: 'crew', fscope: 'crew', mode: st.mode || 'when', custom: 20, by: st.by || 'type', open: st.open !== false,
      date: new Date(Date.now() + 6 * WEEK).toISOString().slice(0, 10) };
    var data = null, d3 = null, result = null;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:460px"></div></div>';

    function controls() {
      var seg = function (name, opts, cur) {
        return '<div class="ui-seg" role="group" aria-label="' + name + '">' + opts.map(function (o) { return '<button type="button" data-set="' + name + '" data-v="' + o[0] + '" class="' + (String(cur) === o[0] ? 'on' : '') + '">' + o[1] + '</button>'; }).join('') + '</div>';
      };
      var range = seg('range', [['4', '4W'], ['12', '12W'], ['26', '26W'], ['all', 'ALL']], st.range);
      var unit = seg('unit', [['cards', 'Cards'], ['points', 'Points']], st.unit);
      var scopes = scopeOptions(data);
      var sel = function (name, opts, cur) { return '<select data-sel="' + name + '" aria-label="' + name + '">' + opts.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[0] === cur ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select>'; };
      if (tab === 'burnup') return sel('scope', scopes, st.scope) + (st.scope.indexOf('s:') === 0 ? '' : range) + unit;
      if (tab === 'forecast') return seg('mode', [['when', 'When done?'], ['howmany', 'How many by?']], st.mode) +
        (st.mode === 'when' ? sel('fscope', scopes.map(function (o) { return [o[0], o[1] + ' (open cards)']; }).concat([['custom', 'A number of cards...']]), st.fscope) +
          (st.fscope === 'custom' ? '<input type="number" min="1" max="2000" data-sel="custom" value="' + st.custom + '" aria-label="Number of cards" style="width:100px">' : '')
          : '<label class="small">By <input type="date" data-sel="date" value="' + esc(st.date) + '" min="' + new Date(Date.now() + WEEK).toISOString().slice(0, 10) + '"></label>');
      if (tab === 'flow' || tab === 'cycle') return range;
      if (tab === 'epics') return seg('open', [['true', 'Open work'], ['false', 'Everything']], String(st.open));
      if (tab === 'mix') return seg('by', [['type', 'By type'], ['who', 'By who']], st.by) + range + unit;
      return '';
    }
    function draw() {
      var crew = data.crew;
      view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Reports // ' + esc(crew.key) + '</div><h1>' + esc(TABS.filter(function (t) { return t[0] === tab; })[0][1]) + '</h1>' +
        '<div class="sub">' + esc(INTRO[tab]) + '</div></div><div class="ui-row"><a class="ui-btn" href="#insights" data-go="insights">' + UI.icon('chart') + 'Insights</a>' +
        '<button class="ui-btn" data-csv>' + UI.icon('download') + 'CSV</button><button class="ui-btn" data-print>' + UI.icon('printer') + 'Print</button></div></div>' + AA.demoNote(crew) +
        '<nav class="rp-tabs" aria-label="Reports">' + TABS.map(function (t) { return '<a href="#reports/' + t[0] + '" data-go="reports/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + t[1] + '</a>'; }).join('') + '</nav>' +
        '<div class="rp-ctl">' + controls() + '<span class="grow"></span></div>' +
        '<div class="aa-lcds rp-kpis" data-kpis></div>' +
        AA.win(esc(TABS.filter(function (t) { return t[0] === tab; })[0][1]) + ' // ' + esc(crew.key), '<p class="rp-note" data-note></p><div data-legend></div><div data-chart></div><div data-table></div>', { cls: 'lime', extra: 'd3' }) + '</div>';
      chart();
    }
    function chart() {
      var el = view.querySelector('[data-chart]');
      if (!el || !view.isConnected) return false;
      try { result = DRAW[tab](d3, el, data, st); }
      catch (e) { el.innerHTML = '<div class="rp-err muted">This report could not be drawn: ' + esc(e.message) + '</div>'; result = null; if (window.console) console.warn(e); return; }
      view.querySelector('[data-kpis]').innerHTML = (result.kpis || []).map(function (k) { return AA.lcd(k[0], k[1], k[2]); }).join('');
      view.querySelector('[data-note]').textContent = result.note || '';
      view.querySelector('[data-legend]').innerHTML = legend(result.legend || []);
      view.querySelector('[data-table]').innerHTML = result.table && result.table[1].length ? AA.table(result.table[0], result.table[1]) : '';
    }
    view.addEventListener('click', function (e) {
      var b = e.target.closest('[data-set]');
      if (b) {
        var k = b.getAttribute('data-set'), v = b.getAttribute('data-v');
        st[k] = k === 'open' ? v === 'true' : v;
        UI.store.set('rp.st', { range: st.range, unit: st.unit, mode: st.mode, by: st.by, open: st.open });
        draw(); return;
      }
      if (e.target.closest('[data-print]')) { view.querySelectorAll('details.aa-tv').forEach(function (x) { x.open = true; }); window.print(); }
      if (e.target.closest('[data-csv]') && result && result.table) {
        AA.download(data.crew.key + '-' + tab + '-' + new Date().toISOString().slice(0, 10) + '.csv', AA.toCSV([result.table[0]].concat(result.table[1])), 'text/csv');
      }
    });
    view.addEventListener('change', function (e) {
      var s = e.target.closest('[data-sel]');
      if (!s) return;
      st[s.getAttribute('data-sel')] = s.value;
      draw();
    });
    return AA.withCrew(view, function (crew) {
      return Promise.all([UI.api('get_reports', crew.id), AA.d3()]).then(function (r) {
        data = prep(r[0]); d3 = r[1];
        draw();
        AA.onResize(chart);
      }, function (err) {
        view.innerHTML = '<div class="ui-wrap"><div class="rp-err">' + esc(err && err.message || 'Reports could not load.') + '</div></div>';
      });
    });
  });
})();

/* ===== requests.html ===== */
(function () {
  var esc = UI.esc;

  function stTag(r) {
    if (r.status === 'open') return r.overdue ? '<span class="rq-st late">overdue by ' + Math.max(1, -r.due_in) + 'd</span>'
      : '<span class="rq-st open">' + (r.due_in === 0 ? 'answer due today' : 'answer due in ' + r.due_in + 'd') + '</span>';
    if (r.shipped) return '<span class="rq-st shipped">shipped</span>';
    return '<span class="rq-st ' + r.status + '">' + esc(r.status) + '</span>';
  }
  function item(r, o) {
    return '<article class="rq-item" data-rid="' + esc(r.id) + '"><button type="button" class="rq-vote' + (r.voted ? ' on' : '') + '" data-vote="' + esc(r.id) + '"' + (o.canVote ? '' : ' disabled') +
      ' aria-pressed="' + r.voted + '" aria-label="' + (r.voted ? 'Remove your vote' : 'Vote') + ' (' + r.votes + ' votes)" title="' + (r.voted ? 'You voted. Click to take it back.' : 'Vote for this') + '">' + r.votes + '<small>VOTES</small></button>' +
      '<div><h3>' + esc(r.title) + '</h3><div class="rq-meta">' + stTag(r) + '<span>by ' + esc(r.by) + (r.mine ? ' (you)' : '') + ' · ' + esc(UI.ago(r.created)) + '</span>' +
      (r.card ? '<a href="#card/' + esc(r.card.key) + '"' + (o.crew ? ' data-card="' + esc(r.card.key) + '"' : '') + '>' + esc(r.card.key) + ' · ' + esc(AA.STATUS[r.card.status]) + '</a>' : '') + '</div>' +
      (r.body ? '<p class="rq-body">' + esc(r.body) + '</p>' : '') +
      (r.status !== 'open' && (r.answer || r.answered_by) ? '<div class="rq-answer"><b>' + esc(r.answered_by || 'The crew') + ' answered' + (r.took != null ? ' in ' + UI.plural(r.took, 'day') : '') + '</b>' + esc(r.answer || 'Accepted.') + '</div>' : '') +
      (o.crew ? '<div class="rq-acts">' + (r.status === 'open' ? '<button class="ui-btn sm primary" data-ans="accepted" data-id="' + esc(r.id) + '">' + UI.icon('check') + 'Accept</button>' +
        '<button class="ui-btn sm" data-ans="later" data-id="' + esc(r.id) + '">Later</button><button class="ui-btn sm danger" data-ans="declined" data-id="' + esc(r.id) + '">Decline</button>'
        : '<button class="ui-btn sm ghost" data-ans="open" data-id="' + esc(r.id) + '">Reopen</button>') + '</div>' : '') + '</div></article>';
  }
  function kpis(s, promise) {
    return '<div class="aa-lcds" style="margin-bottom:16px">' + AA.lcd(s.open, 'open') + AA.lcd(s.overdue, 'past the ' + promise + '-day promise', s.overdue ? 'red' : 'cyan') +
      AA.lcd(s.median_days == null ? '--' : s.median_days + '<small>d</small>', 'median time to answer', 'pink') +
      AA.lcd(s.on_time == null ? '--' : s.on_time + '<small>%</small>', 'answered on time', 'amber') + AA.lcd(s.shipped, 'shipped') + '</div>';
  }
  function answerFlow(rid, status, done) {
    if (status === 'open') return UI.api('answer_request', rid, 'open', '').then(done);
    var words = { accepted: ['Accept this request?', 'It becomes a card in the backlog, and the requester sees it move to Shipped. A note is optional.', 'Accept'],
      later: ['Not now, maybe later', 'Say why and when you might look again. A reason makes a "not now" fair.', 'Answer: later'],
      declined: ['Decline this request', 'Say why in a sentence or two. People take a clear no better than silence.', 'Decline'] }[status];
    var m = UI.modal('<h2>' + esc(words[0]) + '</h2><p class="muted">' + esc(words[1]) + '</p><form data-af class="ui-stack"><label class="ui-field"><span>Answer ' + (status === 'accepted' ? '<em>(optional)</em>' : '') + '</span>' +
      '<textarea name="answer" rows="3" maxlength="1000"' + (status === 'accepted' ? '' : ' required minlength="10"') + '></textarea></label>' +
      '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn ' + (status === 'declined' ? 'danger solid' : 'primary') + '" type="submit">' + esc(words[2]) + '</button></div></form>');
    m.el.querySelector('[data-af]').addEventListener('submit', function (e) {
      e.preventDefault();
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('answer_request', rid, status, UI.formData(e.target).answer)).then(function (r) {
        m.close(); UI.toast(status === 'accepted' ? 'Accepted: ' + r.request.card.key + ' is in the backlog' : 'Answered', 'ok'); done();
      });
    });
  }

  UI.page('requests', { title: 'Requests', auth: 'user' }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';
    return AA.withCrew(view, function (crew) {
      return UI.api('get_requests', crew.id).then(function (d) {
        var link = location.origin + location.pathname + '#ask/' + d.ask_code;
        var open = d.requests.filter(function (r) { return r.status === 'open'; }), done = d.requests.filter(function (r) { return r.status !== 'open'; });
        view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Requests // ' + esc(d.crew.key) + '</div><h1>Requests</h1>' +
          '<div class="sub">Every request gets an answer within ' + d.promise_days + ' days: yes, later or no, with a reason.</div></div>' +
          '<div class="ui-row"><a class="ui-btn" href="#ask/' + esc(d.ask_code) + '" data-go="ask/' + esc(d.ask_code) + '">' + UI.icon('megaphone') + 'What requesters see</a></div></div>' + AA.demoNote(crew) +
          kpis(d.stats, d.promise_days) +
          '<div class="rq-grid"><div class="ui-stack">' +
          AA.win('Waiting for an answer', open.length ? open.map(function (r) { return item(r, { crew: true, canVote: true }); }).join('') : '<p class="muted small" style="margin:0">Inbox zero. ' + AA.smiley(20) + ' Share the link so people can ask.</p>', { extra: open.length + ' open', cls: open.some(function (r) { return r.overdue; }) ? 'warn' : '' }) +
          AA.win('Answered', done.length ? done.map(function (r) { return item(r, { crew: true, canVote: true }); }).join('') : '<p class="muted small" style="margin:0">Answers show up here, with how long each took.</p>', { extra: done.length + '', cls: 'cyan' }) +
          '</div><div class="ui-stack">' +
          AA.win('Share the ask link', '<p class="small muted" style="margin-top:0">Anyone signed in with this link can add requests and vote. They see the requests and your answers, never the board.</p>' +
            '<code class="rq-link" data-asklink>' + esc(link) + '</code><div class="ui-row" style="margin-top:10px"><button class="ui-btn sm" data-copy="[data-asklink]">' + UI.icon('copy') + 'Copy link</button>' +
            (d.can_admin ? '<button class="ui-btn sm" data-newask>' + UI.icon('refresh') + 'New link</button>' : '') + '</div>', { cls: 'lime' }) +
          AA.win('Answer promise', '<p class="small muted" style="margin-top:0">How long people wait, at most, before the crew answers. Overdue requests show on the Deck and can alert the crew.</p>' +
            '<div class="ui-seg" role="group" aria-label="Answer promise">' + d.promises.map(function (p) { return '<button type="button" data-promise="' + p + '" class="' + (p === d.promise_days ? 'on' : '') + '">' + p + ' days</button>'; }).join('') + '</div>') +
          AA.win('Add one for someone', '<form data-addreq class="ui-stack"><label class="ui-field"><span>Title</span><input type="text" name="title" maxlength="140" required placeholder="What do they need?"></label>' +
            '<label class="ui-field"><span>Details <em>(optional)</em></span><textarea name="body" rows="3" maxlength="3000" placeholder="Who asked, why it matters"></textarea></label>' +
            '<button class="ui-btn sm primary" type="submit">' + UI.icon('plus') + 'Add request</button></form>', { cls: 'cyan' }) +
          '</div></div></div>';
        view.onclick = function (e) {
          var t;
          if ((t = e.target.closest('[data-vote]'))) UI.api('vote_request', t.getAttribute('data-vote'), !t.classList.contains('on')).then(function () { UI.refresh(); });
          else if ((t = e.target.closest('[data-ans]'))) answerFlow(t.getAttribute('data-id'), t.getAttribute('data-ans'), function () { UI.refresh(); });
          else if ((t = e.target.closest('[data-promise]'))) UI.api('update_crew', crew.id, { promise_days: +t.getAttribute('data-promise') }).then(function () { UI.toast('Answer promise saved', 'ok'); UI.refresh(); });
          else if (e.target.closest('[data-newask]')) UI.confirm({ title: 'Make a new ask link?', text: 'The old link stops working. Share the new one.', ok: 'New link' }).then(function (y) { if (y) UI.api('new_ask_code', crew.id).then(function () { UI.refresh(); }); });
        };
        view.onsubmit = function (e) {
          if (!e.target.matches('[data-addreq]')) return;
          e.preventDefault();
          var v = UI.formData(e.target);
          UI.busy(e.target.querySelector('[type=submit]'), UI.api('submit_request', v.title, v.body, crew.id)).then(function () { UI.toast('Request added', 'ok'); UI.refresh(); });
        };
      });
    });
  });

  UI.page('ask', { title: 'Ask a crew', auth: 'user' }, function (view, ctx) {
    var code = (ctx.args[0] || '').toUpperCase();
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:420px"></div></div>';
    return UI.apiQuiet('ask_page', code).catch(function (e) { return { ok: false, error: e.message }; }).then(function (d) {
      if (!d.ok) {
        view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Ask</div><h1>That link doesn\'t work</h1><div class="sub">' + esc(d.error) + '</div></div></div>' + AA.smiley(80, '#ff2bd6') + '</div>';
        return;
      }
      var c = d.crew;
      view.innerHTML = '<div class="ui-wrap"><div class="aa-head"><div><div class="eyebrow">Ask // ' + esc(c.key) + '</div><h1>Ask ' + esc(c.name) + '</h1>' +
        '<div class="sub">' + esc(c.mission || 'Tell the crew what you need.') + '</div></div>' + (c.id ? '<div class="ui-row"><a class="ui-btn" href="#requests" data-go="requests" data-crewid="' + esc(c.id) + '">' + UI.icon('inbox') + 'Crew request desk</a></div>' : '') + '</div>' +
        (c.demo ? '<div class="aa-demo-note"><b>DEMO CREW</b> // a sandbox: anything you add here is visible to everyone signed in.</div>' : '') +
        '<div class="rq-grid"><div class="ui-stack">' +
        AA.win('Requests', d.requests.length ? d.requests.map(function (r) { return item(r, { crew: false, canVote: r.status === 'open' }); }).join('') : '<p class="muted small" style="margin:0">Nothing asked yet. Be the first.</p>', { extra: d.stats.open + ' open' }) +
        '</div><div class="ui-stack">' +
        AA.win('Ask for something', '<form data-ask class="ui-stack"><label class="ui-field"><span>What do you need?</span><input type="text" name="title" maxlength="140" required placeholder="One line, like a headline"></label>' +
          '<label class="ui-field"><span>Why it matters <em>(optional)</em></span><textarea name="body" rows="4" maxlength="3000" placeholder="Who is it for? What happens today without it?"></textarea></label>' +
          '<button class="ui-btn primary" type="submit">' + UI.icon('megaphone') + 'Send the request</button></form>', { cls: 'lime' }) +
        AA.win('The promise', '<div class="rq-hero">' + AA.smiley(54) + '<p style="margin:0;flex:1;min-width:180px">' + esc(c.name) + ' answers every request within <b>' + d.promise_days + ' days</b>: yes (and you watch it ship), later, or no, always with a reason.</p></div>' +
          '<div class="aa-lcds" style="margin-top:12px">' + AA.lcd(d.stats.median_days == null ? '--' : d.stats.median_days + '<small>d</small>', 'median answer', 'pink') + AA.lcd(d.stats.shipped, 'shipped', 'cyan') + '</div>', { cls: 'cyan' }) +
        '</div></div></div>';
      view.onclick = function (e) {
        var t;
        if ((t = e.target.closest('[data-vote]')) && !t.disabled) UI.api('vote_request', t.getAttribute('data-vote'), !t.classList.contains('on'), code).then(function () { UI.refresh(); });
        else if ((t = e.target.closest('[data-crewid]'))) AA.setCrew(t.getAttribute('data-crewid'));
      };
      view.onsubmit = function (e) {
        if (!e.target.matches('[data-ask]')) return;
        e.preventDefault();
        var v = UI.formData(e.target);
        UI.busy(e.target.querySelector('[type=submit]'), UI.api('submit_request', v.title, v.body, null, code)).then(function () {
          AA.rave('REQUEST SENT', c.key + ' answers within ' + d.promise_days + ' days'); UI.refresh();
        });
      };
    });
  });
})();
