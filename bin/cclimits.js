#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');

const script = path.join(__dirname, '..', 'lib', 'cclimits.py');
const child = spawn('python3', [script, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env
});

child.on('error', (err) => {
  if (err.code === 'ENOENT') {
    console.error('Error: python3 not found. Please install Python 3.10+');
    process.exit(1);
  }
  throw err;
});

child.on('close', (code) => process.exit(code ?? 0));
