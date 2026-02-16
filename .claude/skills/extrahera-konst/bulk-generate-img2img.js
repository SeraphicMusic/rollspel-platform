#!/usr/bin/env node

/**
 * Bulk Image-to-Image Generator for DoD Art Extraction
 *
 * Använder Gemini 2.5 Flash Image för att omarbeta extraherade sidbilder
 * i olika svenska illustratörers stilar.
 *
 * Användning:
 *   node bulk-generate-img2img.js <illustrations.json> <pages-folder> <output-folder> [style]
 *
 * Exempel:
 *   node bulk-generate-img2img.js Barbia_illustrations.json ./pages ./output ackegard
 *   node bulk-generate-img2img.js Barbia_illustrations.json ./pages ./output all
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const args = process.argv.slice(2);

if (args.length < 3) {
  console.error('Användning: node bulk-generate-img2img.js <illustrations.json> <pages-folder> <output-folder> [style]');
  console.error('');
  console.error('Stilar: ackegard, bergting, egerkrans, all (default)');
  process.exit(1);
}

const inputFile = args[0];
const pagesFolder = args[1];
const outputFolder = args[2];
const targetStyle = args[3] || 'all';

// Hämta API-nyckel
function getApiKey() {
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;

  const configPaths = [
    path.join(process.env.USERPROFILE || process.env.HOME, '.config', 'gemini', 'credentials.json'),
  ];

  for (const configPath of configPaths) {
    if (fs.existsSync(configPath)) {
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        if (config.apiKey) return config.apiKey;
      } catch (e) { /* ignore */ }
    }
  }
  return null;
}

// Extrahera creature-namn från subject
function extractCreatureName(subject) {
  // Subject format: "Halvalv - En kvinnlig halvalv med..."
  const match = subject.match(/^([^-–]+)/);
  if (match) {
    return match[1].trim();
  }
  return 'Unknown';
}

// Sanitera filnamn
function sanitizeFilename(name) {
  return name
    .replace(/[<>:"/\\|?*]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Generera bild via Gemini 2.5 Flash Image (img2img)
function generateImage(prompt, sourceImagePath, apiKey) {
  return new Promise((resolve, reject) => {
    // Läs källbilden
    if (!fs.existsSync(sourceImagePath)) {
      reject(new Error(`Källbild saknas: ${sourceImagePath}`));
      return;
    }

    const imageBuffer = fs.readFileSync(sourceImagePath);
    const base64Image = imageBuffer.toString('base64');
    const mimeType = sourceImagePath.endsWith('.png') ? 'image/png' : 'image/jpeg';

    // Gemini 2.5 Flash Image - stöder img2img
    const url = new URL('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent');
    url.searchParams.set('key', apiKey);

    const requestBody = {
      contents: [{
        parts: [
          { text: `Transform this illustration while preserving the exact pose, composition, and character positioning. ${prompt}` },
          { inlineData: { mimeType, data: base64Image } }
        ]
      }],
      generationConfig: {
        responseModalities: ['image', 'text']
      }
    };

    const postData = JSON.stringify(requestBody);

    const req = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`API-fel (${res.statusCode}): ${data.substring(0, 200)}`));
          return;
        }
        try {
          const json = JSON.parse(data);
          // Hitta bilddata i svaret
          const parts = json.candidates?.[0]?.content?.parts || [];
          for (const part of parts) {
            if (part.inlineData?.data) {
              resolve(Buffer.from(part.inlineData.data, 'base64'));
              return;
            }
          }
          reject(new Error('Ingen bild i svaret'));
        } catch (e) {
          reject(new Error(`Parse-fel: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

// Vänta mellan anrop (rate limiting)
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Hitta källbild för en illustration
function findSourceImage(pagesFolder, pageNum) {
  // Försök olika namnformat
  const formats = [
    `page_${String(pageNum).padStart(2, '0')}.jpg`,
    `page_${pageNum}.jpg`,
    `page-${String(pageNum).padStart(2, '0')}.jpg`,
    `page-${pageNum}.jpg`,
    `${String(pageNum).padStart(3, '0')}.jpg`,
  ];

  for (const format of formats) {
    const filePath = path.join(pagesFolder, format);
    if (fs.existsSync(filePath)) {
      return filePath;
    }
  }
  return null;
}

// Huvudfunktion
async function main() {
  const apiKey = getApiKey();

  if (!apiKey) {
    console.error('Fel: Ingen GEMINI_API_KEY hittades.');
    console.error('Konfigurera: $env:GEMINI_API_KEY = "din-nyckel"');
    console.error('Eller skapa: ~/.config/gemini/credentials.json');
    process.exit(1);
  }

  // Läs illustrations-JSON
  if (!fs.existsSync(inputFile)) {
    console.error(`Fil saknas: ${inputFile}`);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const illustrations = data.illustrations || [];

  if (illustrations.length === 0) {
    console.error('Inga illustrationer hittades i filen.');
    process.exit(1);
  }

  // Verifiera pages-mapp
  if (!fs.existsSync(pagesFolder)) {
    console.error(`Pages-mapp saknas: ${pagesFolder}`);
    process.exit(1);
  }

  // Skapa output-mapp
  if (!fs.existsSync(outputFolder)) {
    fs.mkdirSync(outputFolder, { recursive: true });
  }

  console.log('='.repeat(60));
  console.log('DoD Art Bulk Generator (Image-to-Image)');
  console.log('='.repeat(60));
  console.log(`Källa: ${data.source || inputFile}`);
  console.log(`Illustrationer: ${illustrations.length}`);
  console.log(`Stil: ${targetStyle}`);
  console.log(`Pages: ${pagesFolder}`);
  console.log(`Output: ${outputFolder}`);
  console.log('='.repeat(60));

  const styles = targetStyle === 'all'
    ? ['ackegard', 'bergting', 'egerkrans']
    : [targetStyle];

  let totalImages = illustrations.length * styles.length;
  let generated = 0;
  let skipped = 0;
  let failed = 0;

  const results = [];

  for (const illust of illustrations) {
    const creatureName = extractCreatureName(illust.subject || `Illustration_${illust.id}`);
    const sourceImage = findSourceImage(pagesFolder, illust.page);

    console.log(`\n[${illust.id}] ${creatureName} (sida ${illust.page})`);

    if (!sourceImage) {
      console.log(`  ⚠ Källbild saknas för sida ${illust.page}`);
      failed += styles.length;
      continue;
    }

    for (const style of styles) {
      const prompt = illust.prompts?.[style];
      if (!prompt) {
        console.log(`  ⚠ Ingen prompt för stil: ${style}`);
        failed++;
        continue;
      }

      const filename = `${sanitizeFilename(creatureName)} - ${style.charAt(0).toUpperCase() + style.slice(1)}.png`;
      const outputPath = path.join(outputFolder, filename);

      // Skippa om filen redan finns
      if (fs.existsSync(outputPath)) {
        console.log(`  ✓ ${style}: Finns redan`);
        skipped++;
        continue;
      }

      try {
        process.stdout.write(`  ⏳ ${style}: Genererar...`);

        const imageBuffer = await generateImage(prompt, sourceImage, apiKey);
        fs.writeFileSync(outputPath, imageBuffer);

        console.log(` ✓ Sparad`);
        generated++;

        results.push({
          id: illust.id,
          creature: creatureName,
          page: illust.page,
          style,
          file: filename,
          success: true
        });

        // Rate limiting - vänta 3 sekunder mellan anrop
        await sleep(3000);

      } catch (error) {
        console.log(` ✗ Fel: ${error.message.substring(0, 60)}`);
        failed++;

        results.push({
          id: illust.id,
          creature: creatureName,
          page: illust.page,
          style,
          error: error.message,
          success: false
        });

        // Vänta längre vid fel
        await sleep(5000);
      }
    }
  }

  // Spara resultatrapport
  const reportPath = path.join(outputFolder, '_generation_report.json');
  fs.writeFileSync(reportPath, JSON.stringify({
    source: data.source,
    generatedAt: new Date().toISOString(),
    style: targetStyle,
    method: 'img2img',
    model: 'gemini-2.5-flash-image',
    total: totalImages,
    generated,
    skipped,
    failed,
    results
  }, null, 2));

  console.log('\n' + '='.repeat(60));
  console.log('KLART!');
  console.log(`Genererade: ${generated}`);
  console.log(`Hoppade över: ${skipped}`);
  console.log(`Misslyckade: ${failed}`);
  console.log(`Rapport: ${reportPath}`);
  console.log('='.repeat(60));
}

main().catch(err => {
  console.error('Kritiskt fel:', err.message);
  process.exit(1);
});