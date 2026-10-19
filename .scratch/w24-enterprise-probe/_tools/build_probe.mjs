// Probe: run vite build programmatically, overriding build.target to 'esnext'
// to bypass vite:esbuild-transpile (which fails on this host in esbuild temp-file removal).
const FE = 'C:/military-Rural Revitalization-system/frontend';
const { build } = await import('file:///' + FE + '/node_modules/vite/dist/node/index.js');
try {
  await build({
    root: FE,
    configFile: FE + '/vite.config.ts',
    logLevel: 'info',
    build: { target: 'esnext' },
  });
  console.log('PROBE_BUILD_OK');
} catch (e) {
  console.error('PROBE_BUILD_FAIL:', e && e.message ? e.message : e);
  process.exitCode = 3;
}
