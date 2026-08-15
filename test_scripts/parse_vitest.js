const fs = require('fs');
const j = JSON.parse(fs.readFileSync('vitest-results2.json', 'utf8'));
console.log('numTotalTestSuites:', j.numTotalTestSuites);
console.log('numPassedTestSuites:', j.numPassedTestSuites);
console.log('numFailedTestSuites:', j.numFailedTestSuites);
console.log('numTotalTests:', j.numTotalTests);
console.log('numPassedTests:', j.numPassedTests);
console.log('numFailedTests:', j.numFailedTests);
const fails = [];
for (const t of j.testResults || []) {
  if (t.status === 'failed') fails.push(t.name);
  for (const a of t.assertionResults || []) {
    if (a.status === 'failed') fails.push(a.fullName + ' :: ' + (a.failureMessages || []).join(' ').slice(0, 200));
  }
}
console.log('FAILURES:', fails.length);
for (const f of fails.slice(0, 20)) console.log(' -', f);
