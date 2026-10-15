// Read-only verification: caller ranges from Yarn lock selectors, not overrides.
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');
const [baselineDir, candidateDir] = process.argv.slice(2);
const semver = createRequire(path.resolve(candidateDir, 'package.json'))('semver');
function read(directory) {
  const entries = new Map();
  for (const block of fs.readFileSync(path.join(directory, 'yarn.lock'), 'utf8').split('\n\n')) {
    const lines = block.split('\n');
    if (!lines[0] || lines[0].startsWith('#')) continue;
    const version = block.match(/^  version "([^"]+)"$/m)?.[1];
    if (!version) throw Error('Missing version');
    const selectors = [...lines[0].slice(0, -1).matchAll(/"([^"]+)"|([^, ]+)/g)].map(m => m[1] || m[2]);
    for (const selector of selectors) entries.set(selector, version);
  }
  return entries;
}
const baseline = read(baselineDir), candidate = read(candidateDir);
const failures = [], changed = [], newSelectors = [];
for (const [selector, version] of candidate) {
  const separator = selector.indexOf('@', selector.startsWith('@') ? 1 : 0);
  const range = selector.slice(separator + 1);
  if (!semver.validRange(range) || !semver.satisfies(version, range)) failures.push({selector, version, range});
  const previous = baseline.get(selector);
  if (previous && previous !== version) changed.push({selector, previous, version, major_changed: semver.major(previous) !== semver.major(version)});
  else if (!previous) newSelectors.push(selector);
}
const manifest = JSON.parse(fs.readFileSync(path.join(candidateDir, 'package.json')));
const report = {selectors: candidate.size, invalid_selectors: failures, changed_existing_selectors: changed.length, changed_existing_major: changed.filter(v => v.major_changed), new_selector_count: newSelectors.length, overrides: manifest.resolutions || null, changes: changed};
process.stdout.write(JSON.stringify(report, null, 2) + '\n');
if (failures.length || report.changed_existing_major.length || manifest.resolutions) process.exitCode = 1;
