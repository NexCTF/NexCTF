// Compares the locale catalogs against a snapshot taken before i18next-parser ran.
// Fails when the parser added or removed keys - i.e. the source and the catalogs
// have drifted apart.
//
// The comparison is on parsed content, not bytes: Weblate escapes invisible
// whitespace ( ,   - French typography uses them before « » ? ! : ;)
// while JSON.stringify writes those characters literally. Both parse identically,
// so a byte diff would fail every Weblate pull request for a formatting
// difference that changes nothing.
import fs from "node:fs";
import path from "node:path";

const [snapshot, current] = process.argv.slice(2);
if (!snapshot || !current) {
  console.error("usage: i18n-sync-check.mjs <snapshot-dir> <catalog-dir>");
  process.exit(2);
}

const read = (dir, file) => {
  const p = path.join(dir, file);
  if (!fs.existsSync(p)) return null;
  // Key order is preserved through parse/stringify, so reordering is still caught.
  return JSON.stringify(JSON.parse(fs.readFileSync(p, "utf8")));
};

const files = new Set([...fs.readdirSync(snapshot), ...fs.readdirSync(current)]);
let drifted = false;

for (const file of [...files].filter((f) => f.endsWith(".json")).sort()) {
  const before = read(snapshot, file);
  const after = read(current, file);
  if (before === after) continue;
  drifted = true;
  if (before === null) console.error(`i18n: ${file} was created by the parser`);
  else if (after === null) console.error(`i18n: ${file} was removed by the parser`);
  else console.error(`i18n: ${file} is out of sync with the source`);
}

if (drifted) {
  console.error("\nRun `task dev:frontend:i18n` and commit the result.");
  process.exit(1);
}
