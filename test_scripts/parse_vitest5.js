const fs = require('fs');
const j = JSON.parse(fs.readFileSync('vitest-results5.json', 'utf8'));
console.log('suites:', j.numTotalTestSuites, 'passed:', j.numPassedTestSuites, 'failed:', j.numFailedTestSuites);
console.log('tests:', j.numTotalTests, 'passed:', j.numPassedTests, 'failed:', j.numFailedTests);
