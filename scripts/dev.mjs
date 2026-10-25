import { spawn, execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

if (process.platform === 'win32') {
  try {
    const regOut = execSync('reg query HKCU\\Environment /v Path', { stdio: ['ignore', 'pipe', 'ignore'] }).toString();
    const match = regOut.match(/Path\s+REG_\w+\s+(.*)/i);
    if (match?.[1]) {
      const paths = match[1].trim().split(';').filter(Boolean);
      for (const p of paths) {
        if (!process.env.PATH?.includes(p)) {
          process.env.PATH = `${process.env.PATH};${p}`;
        }
      }
    }
  } catch {}
}

const root = fileURLToPath(new URL('../', import.meta.url));
const children = [
  spawn('uv', ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001', '--no-access-log'], { cwd: `${root}/takumi-backend`, stdio: 'inherit' }),
  spawn(process.execPath, [`${root}/node_modules/vite/bin/vite.js`, '--host', '127.0.0.1', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' }),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (process.platform === 'win32' && child.pid) {
      // Terminate only this launcher's own process trees, including uvicorn's child.
      spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
    } else child.kill();
  }
  process.exitCode = code;
}
for (const child of children) {
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => stop(code || 0));
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
