const fs = require('fs');
const t = fs.readFileSync('frontend/src/data/guizhouRegion.ts', 'utf8');
const blocks = [...t.matchAll(/const\s+(\w+_TOWNSHIPS)[^=]*=\s*\{/g)];
const totals = [];
let grand = 0;
for (const b of blocks) {
  const name = b[1];
  let i = b.index + b[0].length, depth = 1, out = '';
  for (let j = i; j < t.length; j++) {
    const c = t[j];
    if (c === '{') depth++;
    if (c === '}') { depth--; if (depth === 0) { out = t.slice(i, j); break; } }
  }
  const keys = [...out.matchAll(/^\s*([^'":]+)\s*:\s*\[/gm)].map(m => m[1].trim());
  totals.push(name + ': ' + keys.length + ' keys');
  if (name === 'OTHER_TOWNSHIPS') {
    for (const m of out.matchAll(/^\s*([^'":]+)\s*:\s*\{/gm)) {
      const city = m[1].trim();
      let i2 = m.index + m[0].length, d = 1, sub = '';
      for (let j = i2; j < out.length; j++) {
        if (out[j] === '{') d++;
        if (out[j] === '}') { d--; if (d === 0) { sub = out.slice(i2, j); break; } }
      }
      const k = [...sub.matchAll(/^\s*([^'":]+)\s*:\s*\[/gm)].length;
      totals.push('  ' + city + ': ' + k + ' counties');
      grand += k;
    }
  } else {
    grand += keys.length;
  }
}
console.log(totals.join('\n'));
console.log('TOTAL_COUNTIES: ' + grand);
