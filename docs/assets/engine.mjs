// Small, independent model shared by the website and its regression tests.
// Inputs are timestamped evidence or explicitly supplied scenario assumptions.
// No API credentials, DOM access, network calls or implicit server rules.

export const CHEST_UNITS = 27 * 64;

function nonNegativeNumber(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    throw new RangeError(label + ' must be a finite, non-negative number');
  }
  return value;
}

function wholeNumber(value, label) {
  nonNegativeNumber(value, label);
  if (!Number.isSafeInteger(value)) throw new RangeError(label + ' must be a safe integer');
  return value;
}

export function simulate({quantity, bids, mode = 'orders', worth = null, feeRate = 0,
                           unitCost = null, axeCost = null}) {
  wholeNumber(quantity, 'Quantity');
  nonNegativeNumber(feeRate, 'Fee rate');
  if (feeRate >= 1) throw new RangeError('Fee rate must be under 100%');
  if (!Array.isArray(bids)) throw new TypeError('Bid levels must be an array');
  if (mode !== 'orders' && mode !== 'axe') throw new RangeError('Unrecognized sale mode');
  if (mode === 'axe') nonNegativeNumber(worth, 'Server worth');
  if (unitCost !== null) nonNegativeNumber(unitCost, 'Unit acquisition cost');
  if (axeCost !== null) nonNegativeNumber(axeCost, 'Axe/tool cost');

  const levels = bids.map((b, order) => {
    nonNegativeNumber(b.p, 'Bid price');
    wholeNumber(b.q, 'Bid depth');
    return {...b, order};
  }).sort((a, b) => b.p - a.p || a.order - b.order);

  let remaining = quantity;
  let orderRevenue = 0;
  const fills = [];
  for (const b of levels) {
    if (remaining === 0) break;
    if (mode === 'axe' && b.p <= worth) continue;
    if (!b.q) continue;
    const units = Math.min(remaining, b.q);
    orderRevenue += units * b.p;
    fills.push({price:b.p, units, revenue:units*b.p, approximate:!!b.approx});
    remaining -= units;
  }

  const worthUnits = mode === 'axe' ? remaining : 0;
  const worthRevenue = worthUnits * (worth ?? 0);
  const unsold = mode === 'orders' ? remaining : 0;
  const totalGross = orderRevenue + worthRevenue;
  const fee = totalGross * feeRate;
  const cashProceeds = totalGross - fee;
  const hasCostBasis = unitCost !== null && (mode !== 'axe' || axeCost !== null);
  const totalCosts = hasCostBasis ? unitCost * quantity + (mode === 'axe' ? axeCost : 0) : null;
  const net = hasCostBasis ? cashProceeds - totalCosts : null;
  return {quantity, fills, orderUnits:quantity-remaining, worthUnits, unsold,
          orderRevenue, worthRevenue, totalGross, fee, cashProceeds,
          totalCosts, net, hasCostBasis,
          approximate: fills.some(f => f.approximate),
          warning: mode === 'axe' ? 'Sell Axe order routing and current /worth must be verified in game.'
                                  : 'Unfilled units are unsold, not valued at the asking price.'};
}

export function sellAxeCapacity({producedPerHour, chestsPerHour, hours = 24}) {
  nonNegativeNumber(producedPerHour, 'Farm rate');
  nonNegativeNumber(chestsPerHour, 'Chest rate');
  nonNegativeNumber(hours, 'Hours');
  const chests = Math.floor(Math.min(producedPerHour * hours / CHEST_UNITS,
                                     chestsPerHour * hours));
  return {chests, units:chests * CHEST_UNITS};
}

export function quoteGapPercent(historical, current) {
  if (!Number.isFinite(historical) || historical <= 0 || !Number.isFinite(current)) return null;
  return (current / historical - 1) * 100;
}

export function shareableSummary(item, result) {
  const fmt = n => '$' + Math.round(n).toLocaleString('en-US');
  const lines = [
    'Donut Quant | Market Exit Calculator',
    'Item: ' + item.name,
    'Snapshot: ' + (item.snapshotAt?.slice(0, 10) || 'unknown') + ' (NOT LIVE)',
    'Quantity: ' + result.quantity.toLocaleString('en-US'),
    'Order-filled units (top observed levels): ' + result.orderUnits.toLocaleString('en-US'),
    'Order gross: ' + fmt(result.orderRevenue),
    'Server fallback: ' + fmt(result.worthRevenue),
    'Unsold: ' + result.unsold.toLocaleString('en-US'),
    'Cash after assumed fees: ' + fmt(result.cashProceeds),
    'Net after entered costs: ' + (result.net === null ? 'UNKNOWN' : fmt(result.net)),
    'Scenario only. Prices, availability and item variants require rechecking.',
    'Source: ' + item.source
  ];
  return lines.join('\n');
}
