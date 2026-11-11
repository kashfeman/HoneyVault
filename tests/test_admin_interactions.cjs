// Built-in Node test runner only; no DOM package or npm installation required.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const source = readFileSync(join(__dirname, '../app/static/js/admin.js'), 'utf8');

function control(properties = {}) {
  return Object.assign({
    hidden: true, handlers: {},
    addEventListener(type, callback) { this.handlers[type] = callback; },
    focus() { this.focused = true; },
  }, properties);
}

test('review updates only its row, counts once and resets with a fresh page', () => {
  function page() {
    const button = control({ dataset: { review: 'ALERT-001' }, textContent: 'Mark reviewed · Demo' });
    const status = control({ textContent: 'Open' });
    const other = control({ textContent: 'Reviewed' });
    const row = { dataset: { alertRow: 'ALERT-001' }, querySelector: () => status };
    const unrelated = { dataset: { alertRow: 'ALERT-003' }, querySelector: () => other };
    const total = { dataset: { baseline: '1' }, textContent: '1' };
    const feedback = { textContent: '' };
    const document = {
      querySelector(selector) { return ({ '#reviewed-total': total, '#review-feedback': feedback })[selector] || null; },
      querySelectorAll(selector) { return selector === '[data-review]' ? [button] : [row, unrelated]; },
    };
    let restore;
    runInNewContext(source, { document, addEventListener(type, handler) { if (type === 'pageshow') restore = handler; } });
    return { button, status, other, total, feedback, restore };
  }
  const first = page();
  assert.equal(first.button.hidden, false);
  first.button.handlers.click();
  assert.equal(first.status.textContent, 'Reviewed · Temporary');
  assert.equal(first.other.textContent, 'Reviewed');
  assert.equal(first.total.textContent, '2');
  assert.equal(first.button.disabled, true);
  assert.match(first.feedback.textContent, /Refresh or navigate to reset/);
  first.button.handlers.click();
  assert.equal(first.total.textContent, '2');
  first.restore({ persisted: true });
  assert.equal(first.status.textContent, 'Open');
  assert.equal(first.button.disabled, false);
  assert.equal(first.total.textContent, '1');
  first.button.handlers.click();
  assert.equal(first.total.textContent, '2');
  const refreshed = page();
  assert.equal(refreshed.status.textContent, 'Open');
  assert.equal(refreshed.total.textContent, '1');
});

test('document dialog validates, confirms text safely and restores focus on cancel', () => {
  const fields = {
    title: control({ value: '   ', setCustomValidity(message) { this.error = message; } }),
    category: { value: 'Finance' }, format: { value: 'CSV' }, sensitivity: { value: 'Confidential' },
  };
  const opener = control();
  const cancel = control();
  const result = control();
  const form = control({
    elements: { namedItem: name => fields[name] || null }, resets: 0,
    reset() { this.resets++; },
    reportValidity() { return !fields.title.error; },
  });
  const dialog = control({
    opened: false, closed: false,
    showModal() { this.opened = true; },
    close() { this.closed = true; },
    querySelectorAll: () => [cancel],
  });
  const document = {
    querySelector(selector) { return ({ '#document-dialog': dialog, '#document-simulation': form, '#simulation-result': result })[selector] || null; },
    querySelectorAll(selector) { return selector === '[data-open-dialog]' ? [opener] : []; },
  };
  runInNewContext(source, { document });
  assert.equal(opener.hidden, false);
  opener.handlers.click();
  assert.equal(dialog.opened, true);
  const event = { preventDefault() { this.prevented = true; } };
  form.handlers.submit(event);
  assert.equal(event.prevented, true);
  assert.equal(dialog.closed, false);
  assert.match(fields.title.error, /non-blank/);
  fields.title.value = '<img src=x onerror=example>';
  fields.title.handlers.input();
  form.handlers.submit(event);
  assert.equal(dialog.closed, true);
  assert.equal(result.hidden, false);
  assert.match(result.textContent, /<img src=x onerror=example>/);
  assert.match(result.textContent, /No document was created or changed/);
  assert.equal(result.innerHTML, undefined);
  // Native close is asynchronous; dispatch it after the submit handler completes.
  dialog.handlers.close();
  assert.equal(result.focused, true);
  opener.handlers.click();
  cancel.handlers.click();
  dialog.handlers.close();
  assert.equal(opener.focused, true);
  assert.equal(result.hidden, true);
  assert.equal(fields.title.error, '');
  assert.ok(form.resets >= 4);
});

test('unrelated pages have no administrator interactions to initialize', () => {
  assert.doesNotThrow(() => runInNewContext(source, {
    document: { querySelector: () => null, querySelectorAll: () => [] },
  }));
});
