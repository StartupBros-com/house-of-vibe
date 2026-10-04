// From https://houseofvibe.ai/blog/claude-code-project-memory
export function quoteTotal(items) {
  if (!Array.isArray(items)) {
    throw new RangeError('items must be an array');
  }

  let totalCents = 0;

  for (const item of items) {
    if (item === null || typeof item !== 'object') {
      throw new RangeError('each item must be an object');
    }

    const { unitPriceCents, quantity } = item;

    if (!Number.isSafeInteger(unitPriceCents) || unitPriceCents < 0) {
      throw new RangeError('unitPriceCents must be a nonnegative safe integer');
    }

    if (!Number.isSafeInteger(quantity) || quantity < 0) {
      throw new RangeError('quantity must be a nonnegative safe integer');
    }

    const lineCents = unitPriceCents * quantity;

    if (!Number.isSafeInteger(lineCents)) {
      throw new RangeError('line total is not a safe integer');
    }

    totalCents += lineCents;

    if (!Number.isSafeInteger(totalCents)) {
      throw new RangeError('total is not a safe integer');
    }
  }

  return { totalCents, currency: 'USD' };
}
