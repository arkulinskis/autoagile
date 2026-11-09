/* Smoke test (tools/ui_test.py --only smoke.js): every page address opens without a JavaScript or Python error and
   without an empty page: signed out, then as a new member (who lands in the demo crews), then as the admin
   (arkulinskis@gmail.com becomes admin on sign-up; ui_test.py starts from an empty local database). Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const errors = [];
  window.addEventListener('error', (e) => errors.push(String(e.message || e)));
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function pageErrors() {
    const shown = $$('.anvil-error-dialog, .error-popup, #error-indicator').filter((e) => e.offsetParent !== null || e.getBoundingClientRect().width);
    return shown.map((e) => (e.innerText || '').slice(0, 160));
  }
  async function open(hash, expect) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY === true, hash, 45000);
    await sleep(700);
    const main = $('.ui-main');
    const text = main ? main.innerText.trim() : '';
    const errs = errors.splice(0).concat(pageErrors());
    const where = location.hash;
    const ok = text.length > 40 && !errs.length && (!expect || where.indexOf(expect) === 0);
    if (!ok) bad.push(hash + ' -> ' + where + ' (' + text.length + ' chars) ' + errs.join(' | '));
    log.push((ok ? 'ok   ' : 'BAD  ') + hash + (where !== hash ? ' -> ' + where : '') + ' (' + text.length + ' chars)');
  }
  async function signUp(name, email, password) {
    if (location.hash !== '#auth/signup') window.UI_READY = false;
    location.hash = '#auth/signup';
    const createBtn = () => $$('.anvil-role-btn-block button').find((b) => /Create account/.test(b.textContent));
    await until(() => window.UI_READY && createBtn() && $$('.au-card input').length >= 3, 'sign-up form');
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]');
    type(inputs[0], name); type(inputs[1], email); type(inputs[2], password || ('Hb-' + Math.random().toString(36).slice(2) + '-Kq7'));
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    createBtn().click();
    if (password) {  // the local admin may exist from an earlier run (the database volume is kept): sign in instead
      await until(() => location.hash.indexOf('#deck') === 0 || /already exists/.test(document.body.innerText), 'sign-up answer', 60000);
      if (location.hash.indexOf('#deck') !== 0) {
        $$('.au-card .ui-seg button').find((b) => /Sign in/.test(b.textContent)).click();
        await until(() => $$('.anvil-role-btn-block button').find((b) => /^Sign in$/.test(b.textContent.trim())), 'sign-in form');
        const f = $$('.au-card input[type=email], .au-card input[type=password]');
        type(f[0], email); type(f[1], password);
        $$('.anvil-role-btn-block button').find((b) => /^Sign in$/.test(b.textContent.trim())).click();
      }
    }
    await until(() => location.hash.indexOf('#deck') === 0 && window.UI_READY, 'signed in as ' + email, 60000);
    await sleep(800);
  }
  async function signOut() {
    $('.anvil-role-avatar button').click();
    await sleep(300);
    $$('.ui-menu button').find((b) => /Sign out/.test(b.textContent)).click();
    await until(() => location.hash.indexOf('#landing') === 0 && window.UI_READY && !$('.anvil-role-avatar button:not([hidden])')?.offsetParent, 'signed out', 30000);
    await sleep(800);
  }
  try {
    // signed out: public pages, and member pages send people to sign in
    for (const h of ['#landing', '#auth', '#auth/signup']) await open(h);
    await open('#deck', '#deck');  // the address stays; the Auth page shows
    if (!$('.au-card')) bad.push('#deck signed out did not show the sign-in page');

    // a member (lands in the demo crews)
    await signUp('Smoke Tester', 'smoke' + Date.now() + '@example.com');
    const member = ['#deck', '#board', '#backlog', '#backlog/party', '#plan/level', '#plan/sprints', '#plan/quarter', '#plan/year', '#plan/epics',
      '#agents', '#insights', '#reports/burnup', '#reports/forecast', '#reports/flow', '#reports/cycle', '#reports/epics', '#reports/mix',
      '#requests', '#import', '#crew', '#crew/new', '#crew/join', '#profile', '#landing'];
    for (const h of member) await open(h);
    await open('#board');
    const card = $('a.aa-card');
    if (card) await open(card.getAttribute('href')); else bad.push('no card on the board');
    await open('#card/NOPE-999');
    await open('#requests');
    const link = $$('.anvil-role-rq-link').map((e) => e.innerText)[0] || '';
    const code = (link.split('#ask/')[1] || '').trim();
    if (code) await open('#ask/' + code); else bad.push('no ask link on #requests');
    await open('#ask/ZZZZZZ');
    // the palette and the crew switcher open and close
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
    await until(() => $('.aa-pal'), 'palette');
    log.push('ok   palette opens');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(600);
    const pal = $('.aa-pal'); if (pal) { const x = $('.anvil-modal .anvil-close, .modal .close'); if (x) x.click(); await sleep(400); }
    if (errors.length) bad.push('palette: ' + errors.splice(0).join(' | '));
    await signOut();

    // the admin
    await signUp('Admin Tester', 'arkulinskis@gmail.com', 'Local-smoke-Admin-7Qx-' + location.port);  // local test database only
    for (const h of ['#admin/overview', '#admin/feedback', '#admin/users', '#admin/crews', '#admin/demo', '#deck']) await open(h);
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' || ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push('STOPPED: ' + String(e && e.message || e));
    if (bad.length) log.push('PROBLEMS: ' + bad.join(' || '));
    return { ok: false, log: log };
  }
})();
