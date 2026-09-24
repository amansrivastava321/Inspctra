import { spawnSync } from 'node:child_process';

const forwarded = process.argv.slice(2);
let runOnce = false;

const vitestArgs = forwarded.flatMap(argument => {
  if (argument === '--watchAll=false') {
    runOnce = true;
    return [];
  }
  if (argument === '--watchAll=true') return ['--watch'];
  return [argument];
});

if (runOnce && !vitestArgs.includes('--run') && !vitestArgs.includes('--watch')) {
  vitestArgs.unshift('--run');
}

const result = spawnSync(process.platform === 'win32' ? 'vitest.cmd' : 'vitest', vitestArgs, {
  stdio: 'inherit',
  shell: process.platform === 'win32',
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
