const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');

const root = '/Users/apple/temp/analysis_outputs';

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) {
      out.push(full);
    }
  }
  return out;
}

function pdfTarget(htmlPath) {
  const normalized = htmlPath.replace(/\\/g, '/');
  let m = normalized.match(/\/language_reports\/fb\/Reach_Genre_Emotion_Report_FB_8plus_([a-z0-9_]+)\.html$/i);
  if (m) {
    return path.join(path.dirname(htmlPath), `FB_Reach_Report_Language_${m[1].toUpperCase()}.pdf`);
  }

  m = normalized.match(/\/language_reports\/Reach_Genre_Emotion_Report_8plus_([a-z0-9_]+)\.html$/i);
  if (m) {
    return path.join(path.dirname(htmlPath), `IG_Reach_Report_Language_${m[1].toUpperCase()}.pdf`);
  }

  return htmlPath.replace(/\.html$/i, '.pdf');
}

async function main() {
  const htmlFiles = walk(root).sort();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1200 } });

  const injectedPrintCss = `
    @media print {
      * { box-sizing: border-box !important; }
      .two { display: block !important; }
      .two > div { margin-bottom: 10px !important; }
      .section { break-inside: auto !important; page-break-inside: auto !important; }
      .chart, .kpi, .chip, .data-table tr { break-inside: avoid !important; page-break-inside: avoid !important; }
      .chart img { max-height: 105mm !important; object-fit: contain !important; }
    }
  `;

  const written = [];
  for (const html of htmlFiles) {
    const pdf = pdfTarget(html);
    await page.goto(pathToFileURL(html).toString(), { waitUntil: 'load' });
    await page.emulateMedia({ media: 'print' });
    await page.addStyleTag({ content: injectedPrintCss });
    await page.pdf({
      path: pdf,
      printBackground: true,
      preferCSSPageSize: true,
      landscape: true,
      margin: { top: '10mm', right: '10mm', bottom: '10mm', left: '10mm' },
    });
    written.push(pdf);
  }

  await browser.close();
  console.log(`Generated PDFs via Playwright: ${written.length}`);
  for (const p of written) {
    console.log(p);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
