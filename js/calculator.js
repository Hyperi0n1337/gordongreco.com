/**
 * Tax Alpha Calculator — Gordon Greco LLC
 * Formulas ported from Financial-Engine/client_report.py:396-440
 */

(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  function calculate() {
    const aum = parseInt($('calc-aum').value, 10);
    const marginal = parseFloat($('calc-rate').value);
    const hasTaxable = $('calc-taxable').checked;
    const hasIRA = $('calc-ira').checked;
    const hasRoth = $('calc-roth').checked;
    const ltcgRate = 0.15;
    const feeRate = 0.01;

    const items = [];
    let totalAlpha = 0;

    // 1. TLH: 2% of AUM in harvestable losses × marginal rate
    if (hasTaxable) {
      const tlhLosses = aum * 0.02;
      const tlhAlpha = tlhLosses * marginal;
      items.push({ name: 'Tax-Loss Harvesting', desc: `Harvesting ~$${fmt(tlhLosses)}/yr in losses at ${pct(marginal)}`, value: tlhAlpha });
      totalAlpha += tlhAlpha;
    }

    // 2. Asset Location: 20bp savings if taxable + tax-deferred
    if (hasTaxable && (hasIRA || hasRoth)) {
      const locAlpha = aum * 0.0020;
      items.push({ name: 'Asset Location', desc: 'Placing tax-inefficient holdings in tax-deferred accounts', value: locAlpha });
      totalAlpha += locAlpha;
    }

    // 3. QDI: 60% of 2% dividend yield × (marginal - LTCG rate)
    if (hasTaxable) {
      const divIncome = aum * 0.02;
      const qdiPct = 0.60;
      const qdiAlpha = divIncome * qdiPct * (marginal - ltcgRate);
      if (qdiAlpha > 0) {
        items.push({ name: 'Qualified Dividends', desc: `Maximizing QDI-eligible holdings (${pct(qdiPct)} qualified)`, value: qdiAlpha });
        totalAlpha += qdiAlpha;
      }
    }

    // 4. Roth Conversion: $20K bracket-filling
    if (hasIRA && hasRoth) {
      const bracketRoom = 20000;
      const futureRate = Math.max(marginal + 0.10, 0.32);
      const rothAlpha = bracketRoom * (futureRate - marginal);
      if (rothAlpha > 0) {
        items.push({ name: 'Roth Conversion', desc: `$${fmt(bracketRoom)}/yr bracket-filling at ${pct(marginal)} vs future ${pct(futureRate)}`, value: rothAlpha });
        totalAlpha += rothAlpha;
      }
    }

    // Render results
    const annualFee = aum * feeRate;
    const netAlpha = totalAlpha - annualFee;

    $('calc-total').textContent = `$${fmt(totalAlpha)}`;
    $('calc-total').classList.toggle('text-red-500', totalAlpha === 0);
    $('calc-total').classList.toggle('text-emerald-600', totalAlpha > 0);

    // Breakdown table
    let rows = '';
    for (const item of items) {
      rows += `<tr class="border-b border-gray-100">
        <td class="py-2 pr-4 font-medium text-gray-800">${item.name}</td>
        <td class="py-2 pr-4 text-gray-600 text-sm">${item.desc}</td>
        <td class="py-2 text-right font-semibold text-emerald-700">$${fmt(item.value)}</td>
      </tr>`;
    }

    // Fee comparison row
    rows += `<tr class="border-t-2 border-gray-300">
      <td class="py-2 pr-4 font-medium text-gray-800">Advisory Fee (1% AUM)</td>
      <td class="py-2 pr-4 text-gray-600 text-sm">Annual cost of tax-aware management</td>
      <td class="py-2 text-right font-semibold text-red-600">–$${fmt(annualFee)}</td>
    </tr>`;
    rows += `<tr class="bg-gray-50">
      <td class="py-2 pr-4 font-bold text-gray-900" colspan="2">Net Tax Alpha (after fees)</td>
      <td class="py-2 text-right font-bold ${netAlpha >= 0 ? 'text-emerald-700' : 'text-red-600'}">$${fmt(netAlpha)}</td>
    </tr>`;

    $('calc-breakdown').innerHTML = rows;

    // Show results section
    $('calc-results').classList.remove('hidden');

    // Show empty state message if no strategies apply
    if (items.length === 0) {
      $('calc-breakdown').innerHTML = `<tr><td colspan="3" class="py-4 text-center text-gray-500">Select account types above to see applicable strategies.</td></tr>`;
    }
  }

  function fmt(n) {
    return Math.round(n).toLocaleString('en-US');
  }

  function pct(n) {
    return (n * 100).toFixed(0) + '%';
  }

  // Expose
  window.calculateAlpha = calculate;

  // Update slider label
  window.updateSliderLabel = function () {
    const val = parseInt($('calc-aum').value, 10);
    $('calc-aum-label').textContent = '$' + fmt(val);
  };
})();
