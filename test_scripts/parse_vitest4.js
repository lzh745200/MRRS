const fs = require('fs');
const j = JSON.parse(fs.readFileSync('vitest-results4.json', 'utf8'));
console.log('suites:', j.numTotalTestSuites, 'passed:', j.numPassedTestSuites, 'failed:', j.numFailedTestSuites);
console.log('tests:', j.numTotalTests, 'passed:', j.numPassedTests, 'failed:', j.numFailedTests);
const fails = [];
for (const t of j.testResults || []) {
  for (const a of t.assertionResults || []) {
    if (a.status === 'failed') fails.push(a.fullName);
  }
}
console.log('failures:', fails.length);
fails.slice(0, 10).forEach(f => console.log(' -', f));
