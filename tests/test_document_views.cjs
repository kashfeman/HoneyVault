// Run with node --test tests/test_document_views.cjs; no npm dependencies.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

test('card/table controls switch the visible content and pressed state', () => {
  const buttons = ['cards', 'table'].map(view => ({
    dataset: { view },
    attributes: { 'aria-pressed': String(view === 'cards') },
    setAttribute(name, value) { this.attributes[name] = value; },
  }));
  let click;
  const controls = {
    hidden: true,
    addEventListener(type, handler) { assert.equal(type, 'click'); click = handler; },
    querySelectorAll() { return buttons; },
  };
  const cards = { hidden: false };
  const table = { hidden: true };
  const elements = { '.view-controls': controls, '#document-cards': cards, '#document-table': table };
  const source = readFileSync(join(__dirname, '../app/static/js/documents.js'), 'utf8');
  runInNewContext(source, { document: { querySelector: selector => elements[selector] } });
  assert.equal(controls.hidden, false);
  for (const button of [buttons[1], buttons[0]]) {
    click({ target: { closest: () => button } });
    assert.equal(cards.hidden, button.dataset.view !== 'cards');
    assert.equal(table.hidden, button.dataset.view === 'cards');
    for (const control of buttons) {
      assert.equal(control.attributes['aria-pressed'], String(control === button));
    }
  }
  // Empty results and unrelated pages have no views to initialize.
  assert.doesNotThrow(() => runInNewContext(source, {
    document: { querySelector: () => null },
  }));
});
