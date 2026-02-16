#!/usr/bin/env node

/**
 * Bulk Image Generator for DoD Art Extraction
 *
 * Tar en illustrations-JSON och genererar alla bilder automatiskt via Imagen API.
 *
 * Användning:
 *   node bulk-generate.js <illustrations.json> <output-folder> [style]
 *
 * Exempel:
 *   node bulk-generate.js Barbia_illustrations.json ./output ackegard
 *   node bulk-generate.js Barbia_illustrations.json ./output all
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const args = process.argv.slice(2);

if (args.length < 2) {
  console.error('Användning: node bulk-generate.js <illustrations.json> <output-folder> [style]');
  console.error('');
  console.error('Stilar: ackegard, bergting, egerkrans, all (default)');
  process.exit(1);
}

const inputFile = args[0];
const outputFolder = args[1];
const targetStyle = args[2] || 'all';

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

// Generera bild via Imagen
function generateImage(prompt, aspectRatio, apiKey) {
  return new Promise((resolve, reject) => {
    // Imagen 4 Fast - bäst för bulk ($0.02/bild)
    const url = new URL('https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict');
    url.searchParams.set('key', apiKey);

    const requestBody = {
      instances: [{ prompt }],
      parameters: {
        sampleCount: 1,
        aspectRatio: aspectRatio || '4:3',
        safetyFilterLevel: 'block_only_high',
        personGeneration: 'allow_adult'
      }
    };

    const req = https.request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`API-fel (${res.statusCode}): ${data}`));
          return;
        }
        try {
          const json = JSON.parse(data);
          if (json.predictions?.[0]?.bytesBase64Encoded) {
            resolve(Buffer.from(json.predictions[0].bytesBase64Encoded, 'base64'));
          } else {
            reject(new Error('Ingen bild i svaret'));
          }
        } catch (e) {
          reject(new Error(`Parse-fel: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(JSON.stringify(requestBody));
    req.end();
  });
}

// Vänta mellan anrop (rate limiting)
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Sanitera filnamn
function sanitizeFilename(name) {
  return name.replace(/[<>:"/\\|?*]/g, '_').substring(0, 50);
}

// Huvudfunktion
async function main() {
  const apiKey = getApiKey();

  if (!apiKey) {
    console.error('Fel: Ingen GEMINI_API_KEY hittades.');
    console.error('Konfigurera: $env:GEMINI_API_KEY = "din-nyckel"');
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

  // Skapa output-mapp
  if (!fs.existsSync(outputFolder)) {
    fs.mkdirSync(outputFolder, { recursive: true });
  }

  console.log('='.repeat(60));
  console.log('DoD Art Bulk Generator');
  console.log('='.repeat(60));
  console.log(`Källa: ${data.source || inputFile}`);
  console.log(`Illustrationer: ${illustrations.length}`);
  console.log(`Stil: ${targetStyle}`);
  console.log(`Output: ${outputFolder}`);
  console.log('='.repeat(60));

  const styles = targetStyle === 'all'
    ? ['ackegard', 'bergting', 'egerkrans']
    : [targetStyle];

  let totalImages = illustrations.length * styles.length;
  let generated = 0;
  let failed = 0;

  const results = [];

  for (const illust of illustrations) {
    console.log(`\n[${illust.id}] Sida ${illust.page}: ${illust.originalDescription?.substring(0, 50)}...`);

    for (const style of styles) {
      const prompt = illust.prompts?.[style];
      if (!prompt) {
        console.log(`  ⚠ Ingen prompt för stil: ${style}`);
        failed++;
        continue;
      }

      const filename = `p${String(illust.page).padStart(3, '0')}_${illust.id}_${style}.png`;
      const outputPath = path.join(outputFolder, filename);

      // Skippa om filen redan finns
      if (fs.existsSync(outputPath)) {
        console.log(`  ✓ ${style}: Finns redan`);
        generated++;
        continue;
      }

      try {
        process.stdout.write(`  ⏳ ${style}: Genererar...`);

        const imageBuffer = await generateImage(prompt, '4:3', apiKey);
        fs.writeFileSync(outputPath, imageBuffer);

        console.log(` ✓ Sparad`);
        generated++;

        results.push({
          id: illust.id,
          page: illust.page,
          style,
          file: filename,
          success: true
        });

        // Rate limiting - vänta 2 sekunder mellan anrop
        await sleep(2000);

      } catch (error) {
        console.log(` ✗ Fel: ${error.message.substring(0, 50)}`);
        failed++;

        results.push({
          id: illust.id,
          page: illust.page,
          style,
          error: error.message,
          success: false
        });

        // Om det är faktureringsfel, avbryt
        if (error.message.includes('billed users')) {
          console.error('\n' + '='.repeat(60));
          console.error('STOPP: Imagen API kräver fakturering.');
          console.error('Aktivera på: https://console.cloud.google.com/billing');
          console.error('='.repeat(60));
          process.exit(1);
        }

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
    total: totalImages,
    generated,
    failed,
    results
  }, null, 2));

  console.log('\n' + '='.repeat(60));
  console.log('KLART!');
  console.log(`Genererade: ${generated}/${totalImages}`);
  console.log(`Misslyckade: ${failed}`);
  console.log(`Rapport: ${reportPath}`);
  console.log('='.repeat(60));
}

main().catch(err => {
  console.error('Kritiskt fel:', err.message);
  process.exit(1);
});