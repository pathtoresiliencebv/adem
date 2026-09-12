/* Optional browser QA: PLAYWRIGHT_PATH and AXE_PATH may point at installed packages. */
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

(async () => {
  const root = path.resolve(__dirname, '..');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence, { recursive: true });
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'adem-browser-test-'));
  const executable = path.join(temporary, 'vlc');
  fs.copyFileSync('/usr/bin/sleep', executable); fs.chmodSync(executable, 0o755);
  const child = spawn(executable, ['60'], { stdio: 'ignore' });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const report = { checks: [], violations: [], browserErrors: [] };
  const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); };
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
    page.on('pageerror', (error) => report.browserErrors.push(error.message));
    await page.goto('http://127.0.0.1:8765');
    await page.getByText('● Lokaal verbonden', { exact: true }).waitFor();
    await page.locator('#auto-refresh').uncheck();
    check('Live Linux metrics shown', !(await page.locator('#available').innerText()).includes('—'));
    check('Protected processes cannot be selected', await page.locator('.app-row input[disabled]').count() > 0);
    await page.screenshot({ path: path.join(evidence, 'desktop.png'), fullPage: true });
    const axePath = process.env.AXE_PATH || require.resolve('axe-core/axe.min.js');
    await page.evaluate(fs.readFileSync(axePath, 'utf8'));
    const scan = async (label) => {
      const results = await page.evaluate(async () => await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }));
      report.violations.push(...results.violations.map((v) => ({ context: label, id: v.id, impact: v.impact, nodes: v.nodes.map((n) => ({target: n.target, summary: n.failureSummary})) })));
    };
    await scan('desktop');
    await page.locator('#search').fill('no-such-app-12345');
    check('Empty search state shown', await page.locator('#empty').isVisible());
    await page.locator('#search').fill('VLC');
    await page.getByRole('button', { name: 'Selecteer sluitbare apps', exact: true }).click();
    check('Only test app selected', (await page.locator('#selection-count').innerText()).startsWith('1 app'));
    await page.locator('#review').focus(); await page.keyboard.press('Enter');
    await page.locator('#confirm-dialog[open]').waitFor();
    check('Dialog starts on cancel', await page.locator('#cancel').evaluate((el) => el === document.activeElement));
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab');
      check(`Dialog Tab ${i + 1} stays inside`, await page.evaluate(() => document.querySelector('#confirm-dialog').contains(document.activeElement)));
    }
    await scan('confirmation dialog');
    await page.screenshot({ path: path.join(evidence, 'confirmation.png') });
    await page.keyboard.press('Escape');
    check('Escape closes confirmation', !(await page.locator('#confirm-dialog').evaluate((el) => el.open)));
    await page.waitForFunction(() => document.activeElement === document.querySelector('#review'));
    check('Focus returns to review', await page.locator('#review').evaluate((el) => el === document.activeElement));
    check('Cancel preserves test process', child.exitCode === null && child.signalCode === null);
    await page.keyboard.press('Enter'); await page.locator('#confirm-dialog[open]').waitFor();
    await page.locator('#confirm').focus(); await page.keyboard.press('Enter');
    await page.locator('#confirm-dialog').waitFor({ state: 'hidden' });
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('1 proces afgesloten'));
    check('Browser confirmation really terminated disposable process', child.signalCode === 'SIGTERM');
    await page.waitForFunction(() => document.activeElement === document.querySelector('#search'));
    check('Focus stays usable after completed action', await page.locator('#search').evaluate((el) => el === document.activeElement));
    report.closeResult = await page.locator('#notice').innerText();
    await page.locator('#search').fill('');
    await page.locator('#notice').evaluate((el) => el.textContent = '');
    await page.setViewportSize({ width: 320, height: 800 });
    check('320px layout has no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await scan('320px mobile');
    await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: path.join(evidence, 'mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.evaluate(() => document.documentElement.style.fontSize = '200%');
    check('200% text has no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await scan('200% text');
    await page.evaluate(() => document.documentElement.style.fontSize = '');
    await page.route('**/api/state', (route) => route.abort());
    await page.locator('#refresh').click();
    await page.locator('#error').waitFor({ state: 'visible' });
    check('Offline state blocks closing', await page.locator('#review').isDisabled());
    check('Offline error announced', await page.locator('#error').getAttribute('role') === 'alert');
    await page.unroute('**/api/state');
    await page.locator('#refresh').click();
    await page.locator('#error').waitFor({ state: 'hidden' });
    check('Reconnect recovers', (await page.locator('#connection').innerText()).includes('gepauzeerd'));
    check('No browser JavaScript errors', report.browserErrors.length === 0);
    fs.writeFileSync(path.join(evidence, 'browser-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    assert.equal(report.violations.length, 0, 'Accessibility violations');
  } finally {
    await browser.close();
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    fs.rmSync(temporary, {recursive: true});
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
