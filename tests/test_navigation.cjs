const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const source = readFileSync(join(__dirname, '../app/static/js/main.js'), 'utf8');

test('mobile navigation focuses links, Escape restores the trigger, resize preserves visible focus', () => {
  const handlers = {};
  const document = { activeElement: null };
  const link = { focus() { document.activeElement = link; }, addEventListener() {} };
  const attributes = { 'aria-expanded': 'false' };
  const menu = {
    hidden: true,
    addEventListener(name, handler) { handlers[name] = handler; },
    setAttribute(name, value) { attributes[name] = value; },
    getAttribute(name) { return attributes[name]; },
    focus() { document.activeElement = menu; },
  };
  const sidebar = {
    classList: { toggle(name, open) { this.open = open; }, remove() { this.open = false; } },
    querySelector: () => link, querySelectorAll: () => [link],
    contains: element => element === link,
  };
  document.querySelector = selector => ({ '.menu-toggle': menu, '#sidebar': sidebar })[selector] || null;
  document.addEventListener = (name, handler) => { handlers[name] = handler; };
  const viewport = { matches: true, addEventListener(name, handler) { handlers.resize = handler; } };
  runInNewContext(source, { document, window: { matchMedia: () => viewport } });
  assert.equal(menu.hidden, false);
  handlers.click();
  assert.equal(attributes['aria-expanded'], 'true');
  assert.equal(document.activeElement, link);
  handlers.keydown({ key: 'Escape' });
  assert.equal(attributes['aria-expanded'], 'false');
  assert.equal(document.activeElement, menu);
  document.activeElement = link;
  handlers.resize();
  assert.equal(document.activeElement, menu);
  viewport.matches = false;
  document.activeElement = link;
  handlers.resize();
  assert.equal(document.activeElement, link);
});
