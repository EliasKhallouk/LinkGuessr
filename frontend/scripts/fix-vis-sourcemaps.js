// Remove sourceMappingURL comments from vis-network bundle to avoid source-map-loader warnings
// Safe: idempotent and non-destructive
const fs = require('fs');
const path = require('path');

const target = path.join(__dirname, '..', 'node_modules', 'vis-network', 'standalone', 'esm', 'vis-network.mjs');
if (!fs.existsSync(target)) {
  console.log('vis-network bundle not found, skipping');
  process.exit(0);
}
try {
  let content = fs.readFileSync(target, 'utf8');
  // Remove any sourceMappingURL comments
  const fixed = content.replace(/\/\/# sourceMappingURL=.*$/gm, '').replace(/\/\*# sourceMappingURL=.*\*\//gm, '');
  if (fixed !== content) {
    fs.writeFileSync(target, fixed, 'utf8');
    console.log('Stripped sourceMappingURL comments from vis-network bundle');
  } else {
    console.log('No sourceMappingURL comments found in vis-network bundle');
  }
} catch (e) {
  console.error('Failed to patch vis-network bundle', e);
  process.exit(1);
}
