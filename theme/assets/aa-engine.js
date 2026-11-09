/* aa-engine.js: AutoAgile's JavaScript engine. Everything here DRAWS or PARSES; pages, lists, menus and dialogs
   are Python Forms (client_code). Python reaches it through client_code/aa.py (window.AA) and the components
   Components/Chart, Components/Md, Components/Report.
     AA.chart.bars|grouped|lines|stack|scatter(el, opts)   SVG charts with hover tooltips (+ AA.table for the table view)
     AA.report(tab, els, data, state)                       the d3 reports (burn-up, Monte Carlo, flow, cycle, epic map, mix)
     AA.md(text)                                            mini markdown -> HTML (escaped first)
     AA.imp.*                                               reading Jira CSV / Trello JSON / any CSV / AutoAgile exports
     AA.download, AA.toCSV, AA.parseCSV, AA.copy           files and the clipboard
     AA.rave(title, sub), AA.smiley(size, colour)           the LEVEL UP overlay and the acid smiley
     AA.dnd(root, onDrop)                                    board drag and drop (calls back into Python)
   Hooks Python sets at start-up: AA.toast(msg, kind), AA.go(page, arg). */
(function () {
  'use strict';
  var AA = window.AA = window.AA || {};
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  AA.esc = esc;
  AA.toast = AA.toast || function () {};
  AA.go = AA.go || function (name, arg) { location.hash = '#' + name + (arg ? '/' + encodeURIComponent(arg) : ''); };
  AA.STATUS = { backlog: 'Backlog', ready: 'Ready', doing: 'Doing', review: 'Review', done: 'Done' };
  function fmtDate(iso, opts) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d)) return '';
    try { return d.toLocaleDateString([], opts || { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return d.toISOString().slice(0, 10); }
  }
  AA.fmtDate = fmtDate;
  var UI = { fmtDate: fmtDate, toast: function (m, k) { AA.toast(m, k); }, go: function (a, b) { AA.go(a, b); } };


  AA.smiley = function (size, color) {
    color = color || '#b4ff1f';
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" fill="' + color + '" stroke="#07070d" stroke-width="5"/>' +
      '<ellipse cx="35" cy="38" rx="6" ry="11" fill="#07070d"/><ellipse cx="65" cy="38" rx="6" ry="11" fill="#07070d"/>' +
      '<path d="M24 58 Q50 86 76 58" fill="none" stroke="#07070d" stroke-width="6" stroke-linecap="round"/></svg>';
  };
  AA.copy = function (text, msg) {
    var done = function () { AA.toast(msg || 'Copied', 'ok'); };
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).then(done, function () { fallback(); });
    fallback();
    function fallback() {
      var t = document.createElement('textarea'); t.value = text; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) { AA.toast('Copy failed: select the text by hand.', 'error'); }
      t.remove();
    }
  };
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
  /* ================================================================ d3 reports (was web/pages/reports.html) */
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
        [fc ? (fmtS(fc.likely)) : (left <= 0 ? 'DONE' : '--'), fc ? 'likely finish' : (left <= 0 ? 'all of it' : 'need 3 weeks of finishes'), 'pink'],
        [fc ? (fmtS(fc.early)) + '–' + (fmtS(fc.late)) : '--', '70% range', 'amber']],
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
      return { kpis: [[q15, '85% sure: at least', 'cyan'], [p50, 'coin flip: at least', 'pink'], [q05, '95% sure: at least'], [wks + '<small>wk</small>', 'until ' + (fmtS(target)), 'amber']],
        legend: [{ name: 'At least the 85% number', color: 'var(--ch-1)' }, { name: 'Less likely', color: 'var(--ch-3)' }],
        note: 'By ' + fmt(target) + ' you will very likely (85%) finish at least ' + q15 + ' cards, and at least ' + p50 + ' half the time. ' +
          'Monte Carlo replays your real weeks (' + samples.join(', ') + ' cards) 5,000 times in random order. No estimates needed.',
        table: [['Cards finished', 'Share of runs'], bins.map(function (b) { return [b[0], (b[1] / RUNS * 100).toFixed(1) + '%']; })] };
    }
    return { kpis: [[(fmtS(d.nowMs + p85 * WEEK)), '85% sure by', 'cyan'], [(fmtS(d.nowMs + p50 * WEEK)), 'coin flip by', 'pink'],
      [(fmtS(d.nowMs + p95 * WEEK)), '95% sure by'], [n, 'cards to finish', 'amber']],
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
      }).on('pointerleave', AA.hideTip).on('click', function (ev, p) { AA.hideTip(); AA.go('card', p.c.k); });
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
      }).on('pointerleave', AA.hideTip).on('click', function (ev, n) { AA.hideTip(); AA.go('card', n.data.c.k); });
    f.svg.attr('aria-label', 'Epic map');
    var rows = groups.map(function (g) {
      var pts = g.cards.reduce(function (a, c) { return a + (c.p || 0); }, 0), done = g.cards.filter(function (c) { return c.s === 'done'; }).reduce(function (a, c) { return a + (c.p || 0); }, 0);
      return [g.e.title, g.cards.length, pts, done, pts ? Math.round(100 * done / pts) + '%' : '', g.e.size || ''];
    });
    var biggest = root.children[0];
    return {
      kpis: [[groups.length, 'epics with cards'], [root.leaves().length, st.open ? 'open cards' : 'cards', 'cyan'],
        [Math.round(root.value), 'points (unestimated = 1)', 'pink'], [(biggest.data.g.e.title.length > 14 ? biggest.data.g.e.title.slice(0, 13) + '…' : biggest.data.g.e.title), 'biggest', 'amber']],
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

  AA.REPORT_TABS = TABS;
  AA.REPORT_INTRO = INTRO;
  var lastReport = null;
  AA.reportPrep = function (json) { return prep(typeof json === 'string' ? JSON.parse(json) : json); };
  AA.reportScopes = function (d) { return JSON.stringify(scopeOptions(d)); };
  /* Draw one report into els = {chart, legend, table}; returns JSON {kpis: [[value, label, cls]], note} for the page. */
  AA.report = function (tab, els, d, stJson) {
    var st = JSON.parse(stJson);
    return AA.d3().then(function (d3) {
      var result;
      try { result = DRAW[tab](d3, els.chart, d, st); }
      catch (e) { els.chart.innerHTML = '<div class="rp-err muted">This report could not be drawn: ' + esc(e.message) + '</div>'; if (window.console) console.warn(e); result = null; }
      lastReport = { tab: tab, result: result, key: d.crew.key };
      els.legend.innerHTML = result ? legend(result.legend || []) : '';
      els.table.innerHTML = result && result.table && result.table[1].length ? AA.table(result.table[0], result.table[1]) : '';
      return JSON.stringify({ kpis: result ? result.kpis || [] : [], note: result ? result.note || '' : '' });
    });
  };
  AA.reportCSV = function () {
    var r = lastReport;
    if (!r || !r.result || !r.result.table) return;
    AA.download(r.key + '-' + r.tab + '-' + new Date().toISOString().slice(0, 10) + '.csv', AA.toCSV([r.result.table[0]].concat(r.result.table[1])), 'text/csv');
  };
  AA.printReport = function (root) {
    (root || document).querySelectorAll('details.aa-tv').forEach(function (x) { x.open = true; });
    window.print();
  };

  /* ================================================================ import readers (was web/pages/import.html) */
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

  /* The page (Pages/Import) keeps the mapping in Python; the parsed file stays here. */
  var parsed = null;
  AA.imp = {
    FIELDS: FIELDS,
    read: function (text, src) {
      var t = String(text || '').trim(), json = t[0] === '{' || t[0] === '[';
      var kind = json ? (t.indexOf('"autoagile-export"') >= 0 ? 'autoagile' : 'trello') : (src === 'jira' || /issue key|issue type/i.test(t.split('\n')[0]) ? 'jira' : 'csv');
      parsed = kind === 'autoagile' ? readAutoAgile(t) : kind === 'trello' ? readTrello(t) : readCSV(t, kind);
      var map = {};
      if (parsed.headers) {
        FIELDS.forEach(function (f) { var h = parsed.headers.filter(function (x) { return GUESS[f[0]].test(x.trim()); })[0]; if (h) map[f[0]] = h; });
        if (kind === 'jira') {
          if (parsed.headers.indexOf('Summary') >= 0) map.title = 'Summary';
          ['Custom field (Story Points)', 'Custom field (Story point estimate)'].forEach(function (h) { if (parsed.headers.indexOf(h) >= 0) map.points = h; });
        }
      }
      var heads = parsed.headers ? parsed.headers.filter(function (h, i) { return h && parsed.headers.indexOf(h) === i; }) : null;
      return JSON.stringify({ kind: kind, headers: heads, note: parsed.note || '', has_items: !!parsed.items, map: map });
    },
    clear: function () { parsed = null; },
    list: function (map, link) { return parsed ? (parsed.items || csvItems(parsed, JSON.parse(map), link)) : []; },
    /* [[source status, count]] most common first */
    sources: function (map, link) {
      var c = {};
      AA.imp.list(map, link).forEach(function (it) { c[it.src] = (c[it.src] || 0) + 1; });
      return JSON.stringify(Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).map(function (k) { return [k, c[k]]; }));
    },
    /* guessed target (column id or 'backlog') for each source status not mapped yet */
    guess: function (map, link, smapJson, colsJson) {
      var smap = JSON.parse(smapJson), cols = JSON.parse(colsJson), known = {};
      (parsed && parsed.items || []).forEach(function (it) { if (it.stage) known[it.src] = it.stage; });
      JSON.parse(AA.imp.sources(map, link)).forEach(function (s) {
        if (smap[s[0]]) return;
        var named = cols.filter(function (c) { return c.name.toLowerCase() === String(s[0]).toLowerCase(); })[0];
        var g = known[s[0]] || stageGuess(s[0]), byStage = cols.filter(function (c) { return c.stage === g; })[0];
        smap[s[0]] = named ? named.id : g === 'backlog' ? 'backlog' : (byStage ? byStage.id : g);
      });
      return JSON.stringify(smap);
    },
    /* the items ready for import_cards, with their target status */
    items: function (map, link, smapJson) {
      var smap = JSON.parse(smapJson);
      return JSON.stringify(AA.imp.list(map, link).map(function (it) {
        var o = Object.assign({}, it, { status: smap[it.src] || 'backlog' }); delete o.src; delete o.stage; return o;
      }));
    },
    exportCSV: function (json, name) {
      var x = JSON.parse(json);
      var rows = [['Issue key', 'Summary', 'Description', 'Issue Type', 'Status', 'Column', 'Priority', 'Story Points', 'Labels', 'Assignee', 'Epic', 'Sprint', 'Created', 'Started', 'Resolved', 'Source']];
      x.cards.forEach(function (c) {
        rows.push([c.key, c.title, c.body, c.type, AA.STATUS[c.status], c.column, 'P' + c.priority, c.points == null ? '' : c.points, (c.labels || []).join(' '), c.assignee || '', c.epic || '',
          c.sprint || '', c.created || '', c.started || '', c.done_at || '', c.source || '']);
      });
      AA.download(name, AA.toCSV(rows), 'text/csv');
    },
    exportJSON: function (json, name) { AA.download(name, JSON.stringify(JSON.parse(json), null, 1), 'application/json'); },
    readFile: function (input, cb) {
      var f = input.files && input.files[0];
      if (!f) return;
      if (f.size > 15 * 1024 * 1024) { AA.toast('That file is over 15 MB. Export fewer issues at a time.', 'error'); return; }
      var r = new FileReader();
      r.onload = function () { cb(String(r.result), f.name); input.value = ''; };
      r.readAsText(f);
    },
    dropzone: function (zone, input, cb) {
      zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('over'); });
      zone.addEventListener('dragleave', function () { zone.classList.remove('over'); });
      zone.addEventListener('drop', function (e) {
        e.preventDefault(); zone.classList.remove('over');
        var f = e.dataTransfer.files[0];
        if (!f) return;
        var r = new FileReader(); r.onload = function () { cb(String(r.result), f.name); }; r.readAsText(f);
      });
      input.addEventListener('change', function () { AA.imp.readFile(input, cb); });
    }
  };

  /* ================================================================ board drag and drop
     Cards are .aa-card[data-id][draggable]; drop targets are [data-drop][data-lane]. onDrop(id, column, lane, beforeId). */
  AA.dnd = function (root, onDrop) {
    var dragId = null, ph = document.createElement('div');
    ph.className = 'bd-ph';
    function beforeCard(body, y) {
      var cards = Array.prototype.slice.call(body.querySelectorAll('.aa-card:not(.dragging)'));
      for (var i = 0; i < cards.length; i++) { var r = cards[i].getBoundingClientRect(); if (y < r.top + r.height / 2) return cards[i]; }
      return null;
    }
    root.addEventListener('dragstart', function (e) {
      var c = e.target.closest && e.target.closest('.aa-card[data-id]');
      if (!c) return;
      dragId = c.getAttribute('data-id');
      c.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', dragId); } catch (err) {}
    });
    root.addEventListener('dragend', function (e) {
      var c = e.target.closest && e.target.closest('.aa-card'); if (c) c.classList.remove('dragging');
      ph.remove(); root.querySelectorAll('.drop').forEach(function (x) { x.classList.remove('drop'); });
    });
    root.addEventListener('dragover', function (e) {
      var body = e.target.closest && e.target.closest('[data-drop]');
      if (!body || !dragId) return;
      e.preventDefault();
      root.querySelectorAll('.drop').forEach(function (x) { if (x !== body) x.classList.remove('drop'); });
      body.classList.add('drop');
      var list = body.querySelector('.bd-cards') || body, b = beforeCard(body, e.clientY);
      if (b && b.parentNode) b.parentNode.insertBefore(ph, b); else list.appendChild(ph);
    });
    root.addEventListener('drop', function (e) {
      var body = e.target.closest && e.target.closest('[data-drop]');
      if (!body || !dragId) return;
      e.preventDefault();
      var b = beforeCard(body, e.clientY), id = dragId;
      dragId = null; ph.remove();
      root.querySelectorAll('.drop').forEach(function (x) { x.classList.remove('drop'); });
      onDrop(id, body.getAttribute('data-drop'), body.getAttribute('data-lane'), b ? b.getAttribute('data-id') : null);
    });
  };

  /* Keep the [data-key] chips etc. focusable things simple: scroll a console to its end. */
  AA.scrollEnd = function (el) { if (el) el.scrollTop = el.scrollHeight; };
})();
