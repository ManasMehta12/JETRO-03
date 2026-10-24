// A six-second, silent fixture for playback integration tests, never course content.
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
try {
  const page = await browser.newPage();
  const bytes = await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 640; canvas.height = 360;
    const context = canvas.getContext('2d');
    const recorder = new MediaRecorder(canvas.captureStream(10), { mimeType: 'video/webm;codecs=vp8' });
    const chunks = [];
    recorder.ondataavailable = event => chunks.push(event.data);
    const result = new Promise(resolve => {
      recorder.onstop = async () => resolve(Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer())));
    });
    let frame = 0;
    const draw = () => {
      context.fillStyle = '#f0f2ef'; context.fillRect(0, 0, 640, 360);
      context.fillStyle = '#345443'; context.font = '24px Arial';
      context.fillText('Playback integration test', 120, 165);
      context.font = '16px Arial'; context.fillText(`Test fixture · ${Math.floor(frame++ / 10)} seconds`, 200, 205);
    };
    draw(); recorder.start();
    const interval = setInterval(draw, 100);
    setTimeout(() => { clearInterval(interval); recorder.stop(); }, 6100);
    return result;
  });
  await mkdir('e2e/fixtures', { recursive: true });
  await writeFile('e2e/fixtures/lesson.webm', Buffer.from(bytes));
} finally { await browser.close(); }
