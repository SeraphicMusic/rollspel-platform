#!/usr/bin/env node

/**
 * Gemini Image Generator
 *
 * Genererar bilder via Google Gemini API (native image generation).
 * Stöder både Imagen (kräver fakturering) och Gemini 2.0 Flash (gratis tier).
 *
 * Användning:
 *   node generate-image.js "<prompt>" "<output-path>" [aspect-ratio] [--model=imagen|gemini]
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// Kommandoradsargument
const args = process.argv.slice(2);

if (args.length < 2) {
  console.error('Användning: node generate-image.js "<prompt>" "<output-path>" [aspect-ratio] [--model=imagen|gemini]');
  console.error('');
  console.error('Aspect ratios: 1:1, 16:9, 9:16, 4:3, 3:4');
  console.error('Models: gemini (default, free), imagen (requires billing)');
  process.exit(1);
}

const prompt = args[0];
const outputPath = args[1];
const aspectRatio = args[2] && !args[2].startsWith('--') ? args[2] : '1:1';
const modelArg = args.find(a => a.startsWith('--model='));
const useModel = modelArg ? modelArg.split('=')[1] : 'gemini';

// Hämta API-nyckel
function getApiKey() {
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;

  const configPaths = [
    path.join(process.env.USERPROFILE || process.env.HOME, '.config', 'gemini', 'credentials.json'),
    path.join(process.env.USERPROFILE || process.env.HOME, '.gemini', 'credentials.json'),
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

// HTTP POST helper
function httpPost(url, body) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const req = https.request({
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
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
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Parse-fel: ${e.message}`));
        }
      });
    });
    req.on('error', reject);
    req.write(JSON.stringify(body));
    req.end();
  });
}

// Generera med Gemini 2.0 Flash (native image generation)
async function generateWithGemini(promptText, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${apiKey}`;

  // Gemini native image generation
  const requestBody = {
    contents: [{
      parts: [{
        text: `Generate an image: ${promptText}.

Please create this as a high-quality illustration. Respond with ONLY the generated image, no text explanation.`
      }]
    }],
    generationConfig: {
      responseModalities: ["IMAGE", "TEXT"],
      responseMimeType: "text/plain"
    }
  };

  return httpPost(url, requestBody);
}

// Generera med Imagen (kräver fakturering)
async function generateWithImagen(promptText, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key=${apiKey}`;

  const requestBody = {
    instances: [{ prompt: promptText }],
    parameters: {
      sampleCount: 1,
      aspectRatio: aspectRatio,
      safetyFilterLevel: 'block_only_high',
      personGeneration: 'allow_adult'
    }
  };

  return httpPost(url, requestBody);
}

// Extrahera bild från Gemini-svar
function extractImageFromGemini(response) {
  if (!response.candidates || !response.candidates[0]) {
    return null;
  }

  const parts = response.candidates[0].content?.parts || [];
  for (const part of parts) {
    if (part.inlineData && part.inlineData.mimeType?.startsWith('image/')) {
      return Buffer.from(part.inlineData.data, 'base64');
    }
  }
  return null;
}

// Extrahera bild från Imagen-svar
function extractImageFromImagen(response) {
  if (!response.predictions || !response.predictions[0]) {
    return null;
  }
  const prediction = response.predictions[0];
  if (prediction.bytesBase64Encoded) {
    return Buffer.from(prediction.bytesBase64Encoded, 'base64');
  }
  return null;
}

// Huvudfunktion
async function main() {
  const apiKey = getApiKey();

  if (!apiKey) {
    console.error('Fel: Ingen GEMINI_API_KEY hittades.');
    process.exit(1);
  }

  console.log('Genererar bild...');
  console.log(`Modell: ${useModel === 'imagen' ? 'Imagen 4.0' : 'Gemini 2.0 Flash'}`);
  console.log(`Prompt: ${prompt.substring(0, 80)}...`);
  if (useModel === 'imagen') console.log(`Aspect ratio: ${aspectRatio}`);

  try {
    let response, imageBuffer;

    if (useModel === 'imagen') {
      response = await generateWithImagen(prompt, apiKey);
      imageBuffer = extractImageFromImagen(response);
    } else {
      response = await generateWithGemini(prompt, apiKey);
      imageBuffer = extractImageFromGemini(response);

      // Om Gemini inte genererade bild, visa textsvaret
      if (!imageBuffer && response.candidates?.[0]?.content?.parts) {
        const textParts = response.candidates[0].content.parts
          .filter(p => p.text)
          .map(p => p.text)
          .join('\n');
        if (textParts) {
          console.log('\nGemini svarade med text istället för bild:');
          console.log(textParts.substring(0, 500));
          console.log('\n---');
          console.log('Tips: Gemini 2.0 Flash stöder inte alltid bildgenerering.');
          console.log('Alternativ: Använd prompten i Google AI Studio manuellt,');
          console.log('eller aktivera fakturering för Imagen API.');
        }
      }
    }

    if (imageBuffer) {
      fs.writeFileSync(outputPath, imageBuffer);
      console.log(`\nBild sparad: ${outputPath}`);
      console.log(JSON.stringify({ success: true, path: outputPath }));
    } else {
      console.error('\nIngen bild genererades.');
      console.log('\nFör att generera bilder, välj ett av dessa alternativ:');
      console.log('1. Aktivera fakturering i Google Cloud för Imagen API');
      console.log('2. Använd Google AI Studio manuellt: https://aistudio.google.com');
      console.log('3. Kopiera prompten till en annan bildgenereringstjänst');
      process.exit(1);
    }

  } catch (error) {
    console.error(`Fel: ${error.message}`);

    if (error.message.includes('billed users')) {
      console.log('\n--- LÖSNING ---');
      console.log('Imagen API kräver fakturering. Alternativ:');
      console.log('1. Aktivera fakturering: https://console.cloud.google.com/billing');
      console.log('2. Använd prompten manuellt i Google AI Studio');
      console.log('3. Kopiera prompten till Midjourney/DALL-E/etc.');
    }
    process.exit(1);
  }
}

main();