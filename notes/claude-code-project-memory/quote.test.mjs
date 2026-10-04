// From https://houseofvibe.ai/blog/claude-code-project-memory
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { quoteTotal } from './quote.mjs';

test('keeps a two-line quote in integer cents', () => {
  assert.deepEqual(
    quoteTotal([
      { unitPriceCents: 1999, quantity: 2 },
      { unitPriceCents: 500, quantity: 1 },
    ]),
    { totalCents: 4498, currency: 'USD' },
  );
});

test('returns the same shape for an empty quote', () => {
  assert.deepEqual(quoteTotal([]), { totalCents: 0, currency: 'USD' });
});

test('rejects malformed inputs and invalid item values with RangeError', () => {
  for (const input of [undefined, null, {}, 'items', 1]) {
    assert.throws(() => quoteTotal(input), RangeError);
  }
  for (const item of [undefined, null, 1, 'item', {}, { quantity: 1 }]) {
    assert.throws(() => quoteTotal([item]), RangeError);
  }
  assert.throws(
    () => quoteTotal([{ unitPriceCents: 2, quantity: 1.5 }]),
    RangeError,
  );
  for (const value of [-1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(
      () => quoteTotal([{ unitPriceCents: value, quantity: 1 }]),
      RangeError,
    );
    assert.throws(
      () => quoteTotal([{ unitPriceCents: 1, quantity: value }]),
      RangeError,
    );
  }
});

test('rejects an unsafe product or accumulated total', () => {
  assert.throws(
    () =>
      quoteTotal([{ unitPriceCents: Number.MAX_SAFE_INTEGER, quantity: 2 }]),
    RangeError,
  );
  assert.throws(
    () =>
      quoteTotal([
        { unitPriceCents: Number.MAX_SAFE_INTEGER, quantity: 1 },
        { unitPriceCents: 1, quantity: 1 },
      ]),
    RangeError,
  );
});
