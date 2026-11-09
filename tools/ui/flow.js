/* The main user journey, run inside the real app (Anvil App Server) by tools/ui_test.py through tools/live/drive.mjs.
   Resolves to {ok, log}. Keep log lines ASCII (the Windows console). ADD THE APP'S OWN JOURNEYS HERE as you build
   features: every page reached, every main button pressed, the result checked on screen. */
(async function () {
  const log = [], t0 = Date.now();
  const say = (m) => log.push(((Date.now() - t0) / 1000).toFixed(1) + 's ' + m);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 20000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const byText = (sel, text) => $$(sel).find((e) => e.textContent.trim().replace(/\s+/g, ' ') === text);
  async function click(sel, text) {
    const el = await until(() => (text ? byText(sel, text) : $(sel)), sel + (text ? ' "' + text + '"' : ''));
    el.scrollIntoView({ block: 'center' });
    el.click();
    return el;
  }
  function type(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  async function page(hash, ready, what) {
    if (location.hash !== hash) window.UI_READY = false;  // the old page stays until the router runs
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && ready(), what || hash, 30000);
    await sleep(300);
  }
  const ok = (cond, msg) => { if (!cond) throw new Error('FAILED: ' + msg); say('ok   ' + msg); };

  try {
    // ---- landing (visitors)
    await page('#landing', () => $('.lp-hero'), 'landing');
    ok($('.lp-hero a[href="#auth/signup"]'), 'landing: hero with a sign-up link');
    ok($('.ui-header .ui-btn.primary'), 'landing: Get started in the header');

    // ---- members-only page sends visitors to sign in, then back
    await page('#profile', () => true);
    await until(() => window.UI_READY && $$('.au-card input').length >= 2, 'redirected to sign in');
    ok(true, 'a members-only page asks visitors to sign in');

    // ---- sign up
    await click('.au-card .ui-seg button', 'Create account');
    await until(() => $$('.au-card input[type=password]').length && $$('.au-card input').filter((i) => i.offsetParent).length >= 3, 'sign-up form');
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter((i) => i.offsetParent);
    type(inputs[0], 'Flow Tester'); type(inputs[1], 'flow' + Date.now() + '@example.com'); type(inputs[2], 'Hb-' + Math.random().toString(36).slice(2) + '-Kq7');
    const tick = $('.au-card input[type=checkbox]');
    if (tick && !tick.checked) tick.click();
    await click('.anvil-role-btn-block button', 'Create account');
    await until(() => location.hash === '#profile' && window.UI_READY && $('.pf-grid'), 'back on the page they wanted', 40000);
    ok(true, 'sign-up: signed in and sent on to the page they asked for');
    ok($('.anvil-role-avatar button') && /FT/.test($('.anvil-role-avatar button').textContent), 'header: account button with initials');

    // ---- home: add an item through the dialog, then delete it
    await page('#home', () => $('.anvil-role-ic-plus'), 'home');
    const before = $$('.ui-item').length;
    await click('.anvil-role-ic-plus button');
    const box = await until(() => $('.add-item input'), 'add dialog');
    type(box, 'Flow test item');
    type($('.add-item textarea'), 'Made by the UI test');
    await click('.add-item .anvil-role-btn-primary button');
    await until(() => !$('.add-item') && $$('.ui-item').length === before + 1, 'item added');
    ok(/Flow test item/.test($('.anvil-role-item-list').textContent), 'home: the dialog adds an item to the list');
    const mine = $$('.ui-item').find((i) => /Flow test item/.test(i.textContent));
    mine.querySelector('.anvil-role-ic-trash button').click();
    await click('.anvil-modal-content button', 'Delete');
    await until(() => !/Flow test item/.test(($('.anvil-role-item-list') || document.body).textContent), 'item deleted');
    ok(true, 'home: delete asks, then removes the item');

    // ---- profile: change the name
    await page('#profile', () => $('.pf-grid'), 'profile');
    type($('.pf-grid input'), 'Flow Tester Two');
    await click('.pf-grid .anvil-role-btn-primary button', 'Save');
    await until(() => /Flow Tester Two/.test($('.pf-head').textContent), 'name saved');
    ok(true, 'profile: name saved');

    // ---- light / dark switch in the account menu
    await click('.anvil-role-avatar button');
    await click('.ui-menu .ui-seg button', 'Dark');
    ok(document.documentElement.classList.contains('ui-dark'), 'menu: Dark switches the theme');
    await click('.ui-menu .ui-seg button', 'Auto');

    // ---- sign out
    await click('.ui-menu button', 'Sign out');
    await until(() => location.hash === '#landing' && window.UI_READY && $('.ui-header .ui-btn.primary'), 'signed out');
    ok(true, 'sign out: back to the landing page as a visitor');

    say('PASSED');
    return { ok: true, log: log };
  } catch (e) {
    say(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
