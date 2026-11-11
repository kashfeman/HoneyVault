// Optional real-Edge QA. Start the preview first; Node 22+ and installed Edge only.
// No npm dependencies, downloads, persisted browser profile or external site visits.
const { spawn } = require('node:child_process');
const { mkdtempSync, readFileSync, rmSync, existsSync, mkdirSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve, dirname } = require('node:path');
const { once } = require('node:events');
const origin = 'http://127.0.0.1:5000';
const edge = process.env.HONEYVAULT_EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const pause = ms => new Promise(done => setTimeout(done, ms));

class Page {
  constructor(socket) {
    this.socket = socket;
    this.sequence = 0;
    this.pending = new Map();
    this.errors = [];
    socket.addEventListener('message', message => {
      const response = JSON.parse(message.data);
      if (response.method === 'Runtime.exceptionThrown') this.errors.push(response.params.exceptionDetails.text);
      const pending = this.pending.get(response.id);
      if (!pending) return;
      this.pending.delete(response.id);
      clearTimeout(pending.timer);
      response.error ? pending.reject(Error(response.error.message)) : pending.resolve(response.result);
    });
  }
  send(method, params = {}) {
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(Error('CDP timeout: ' + method)); }, 10000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  async navigate(path) {
    await this.send('Page.navigate', { url: origin + path });
    for (let index = 0; index < 100; index++) {
      if (await this.evaluate(`location.pathname + location.search === ${JSON.stringify(path)} && document.readyState === 'complete'`)) break;
      if (index === 99) throw Error('Navigation timed out: ' + path);
      await pause(50);
    }
    await this.evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))');
  }
  async key(key, code = key, modifiers = 0) {
    const keyCode = { Enter: 13, Escape: 27, Tab: 9 }[key];
    for (const type of ['keyDown', 'keyUp']) {
      await this.send('Input.dispatchKeyEvent', { type, key, code, modifiers, windowsVirtualKeyCode: keyCode, ...(key === 'Enter' && type === 'keyDown' ? { text: '\r' } : {}) });
    }
    if (key === 'Escape') await pause(50); // Native dialog close dispatch is queued.
  }
}

async function run() {
  if (!existsSync(edge)) throw Error('Installed Edge not found; set HONEYVAULT_EDGE to its executable.');
  await fetch(origin + '/dashboard').then(response => { if (!response.ok) throw Error('Start the preview first.'); });
  const temporaryRoot = resolve(tmpdir());
  const profile = mkdtempSync(join(temporaryRoot, 'honeyvault-browser-'));
  const browser = spawn(edge, ['--headless=new', '--no-first-run', '--disable-sync', '--disable-background-networking', '--disable-extensions', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  const exit = once(browser, 'exit');
  let page;
  const failures = [];
  let checks = 0;
  const check = (condition, description) => { checks++; if (!condition) failures.push(description); };
  try {
    const activePort = join(profile, 'DevToolsActivePort');
    for (let index = 0; !existsSync(activePort); index++) {
      if (index > 100) throw Error('Edge did not expose its local debugging port.');
      await pause(100);
    }
    const port = readFileSync(activePort, 'utf8').split('\n')[0];
    const target = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' }).then(response => response.json());
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((done, reject) => { socket.addEventListener('open', done, { once: true }); socket.addEventListener('error', reject, { once: true }); });
    page = new Page(socket);
    await page.send('Page.enable');
    await page.send('Runtime.enable');
    const paths = ['/login', '/dashboard', '/dashboard/manage-documents', '/dashboard/manage-documents/doc-102', '/dashboard/alerts', '/dashboard/alerts/ALERT-001', '/dashboard/events', '/dashboard/events/DEMO-008', '/employee', '/employee/documents', '/employee/documents/doc-102'];
    for (const width of [1440, 768, 375]) {
      await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
      for (const path of paths) {
        await page.navigate(path);
        const layout = await page.evaluate(`({ width: innerWidth, scroll: document.documentElement.scrollWidth, heading: !!document.querySelector('h1'), overflow: [...document.querySelectorAll('.topbar,.heading-row,.library-results-bar')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.className) })`);
        check(layout.scroll <= width + 1 && !layout.overflow.length, `${width}px ${path}: overflow ${JSON.stringify(layout)}`);
        check(layout.heading, `${path}: missing main heading`);
        if (path === '/dashboard/manage-documents') {
          const display = await page.evaluate(`({ table: getComputedStyle(document.querySelector('.inventory-table')).display, cards: getComputedStyle(document.querySelector('.inventory-cards')).display })`);
          check(width > 1200 ? display.table !== 'none' && display.cards === 'none' : display.table === 'none' && display.cards !== 'none', `${width}px inventory table/card fallback`);
        }
      }
    }
    if (!process.argv.includes('--scan-only')) {
      await page.navigate('/employee/documents');
      await page.evaluate(`document.querySelector('.menu-toggle').focus()`);
      await page.key('Enter');
      const menuState = await page.evaluate(`({ focused: document.activeElement.outerHTML.slice(0,250), expanded: document.querySelector('.menu-toggle').getAttribute('aria-expanded'), path: location.pathname, first: document.activeElement === document.querySelector('#sidebar nav a') })`);
      check(menuState.first, 'Mobile menu must focus its first link: ' + JSON.stringify(menuState));
      await page.key('Escape');
      check(await page.evaluate(`document.activeElement.matches('.menu-toggle') && document.activeElement.getAttribute('aria-expanded') === 'false'`), 'Escape must close menu and restore trigger focus');
      await page.evaluate(`document.querySelector('[data-view="table"]').click()`);
      check(await page.evaluate(`!document.querySelector('#document-table').hidden && document.querySelector('#document-cards').hidden`), 'Library table toggle');
      await page.navigate('/dashboard/alerts');
      await page.evaluate(`document.querySelector('[data-review]').click()`);
      check(await page.evaluate(`document.querySelector('#reviewed-total').textContent === '2'`), 'Temporary review counter');
      await page.evaluate(`dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))`);
      check(await page.evaluate(`document.querySelector('#reviewed-total').textContent === '1' && !document.querySelector('[data-review]').disabled`), 'Restored history-page snapshot reset');
      await page.navigate('/dashboard/alerts');
      check(await page.evaluate(`document.querySelector('#reviewed-total').textContent === '1'`), 'Review resets on navigation');
      await page.navigate('/dashboard/manage-documents');
      await page.evaluate(`document.querySelector('[data-open-dialog]').click()`);
      check(await page.evaluate(`document.activeElement.id === 'simulation-name'`), 'Dialog initial focus');
      for (let index = 0; index < 10; index++) {
        await page.key('Tab');
        check(await page.evaluate(`document.querySelector('dialog').contains(document.activeElement)`), 'Native dialog focus containment');
      }
      await page.key('Escape');
      check(await page.evaluate(`!document.querySelector('dialog').open && document.activeElement.matches('[data-open-dialog]')`), 'Dialog Escape/return focus');
      await page.evaluate(`document.querySelector('[data-open-dialog]').click(); const name = document.querySelector('#simulation-name'); name.value = '   '; name.dispatchEvent(new Event('input'));`);
      check(await page.evaluate(`!document.querySelector('form#document-simulation').checkValidity()`), 'Dialog rejects blank name');
      await page.evaluate(`const form = document.querySelector('#document-simulation'); for (const [name,value] of Object.entries({title:'Fictional QA plan',category:'Finance',format:'CSV',sensitivity:'Internal'})) { const input = form.elements.namedItem(name); input.value=value; input.dispatchEvent(new Event('input')); } form.requestSubmit();`);
      await pause(100);
      check(await page.evaluate(`!document.querySelector('dialog').open && !document.querySelector('#simulation-result').hidden && document.activeElement.id === 'simulation-result'`), 'Simulation confirmation and focus');
    }
    if (process.argv.includes('--screenshots')) {
      const artifacts = resolve(__dirname, '../generated/frontend-qa');
      mkdirSync(artifacts, { recursive: true });
      for (const [width, path, name] of [[1440, '/dashboard', 'desktop'], [375, '/employee/documents', 'mobile']]) {
        await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
        await page.navigate(path);
        const screenshot = await page.send('Page.captureScreenshot', { format: 'png' });
        writeFileSync(join(artifacts, name + '.png'), Buffer.from(screenshot.data, 'base64'));
      }
    }
    check(!page.errors.length, 'Uncaught browser exceptions: ' + page.errors.join(', '));
    console.log(`${checks - failures.length}/${checks} real-Edge checks passed (11 pages at 1440/768/375px, plus interactions when enabled).`);
    for (const failure of failures) console.error(failure);
    if (failures.length) process.exitCode = 1;
  } finally {
    if (page) { try { await page.send('Browser.close'); } catch { /* process may already be closed */ } page.socket.close(); }
    else browser.kill();
    await Promise.race([exit, pause(5000)]);
    // Check the absolute target before deleting only this test-created profile.
    if (dirname(resolve(profile)) === temporaryRoot && profile.startsWith(join(temporaryRoot, 'honeyvault-browser-'))) {
      rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    }
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
