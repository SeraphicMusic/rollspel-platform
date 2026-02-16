#!/usr/bin/env node
const https = require('https');
const fs = require('fs');
const path = require('path');

// Hämta API-nyckel
function getApiKey() {
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;

  const configPath = path.join(process.env.USERPROFILE || process.env.HOME, '.config', 'gemini', 'credentials.json');
  if (fs.existsSync(configPath)) {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    if (config.apiKey) return config.apiKey;
  }
  return null;
}

const apiKey = getApiKey();
if (!apiKey) {
  console.log('Ingen API-nyckel hittades!');
  process.exit(1);
}

console.log('Testar Gemini API...');
console.log('API-nyckel:', apiKey.substring(0, 10) + '...');

const url = new URL('https://generativelanguage.googleapis.com/v1beta/models');
url.searchParams.set('key', apiKey);

https.get(url, res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    try {
      const json = JSON.parse(data);
      if (json.error) {
        console.log('API-fel:', json.error.message);
        return;
      }
      if (json.models) {
        console.log('\nAPI OK! Tillgangliga modeller:\n');

        const imagenModels = json.models.filter(m => m.name.toLowerCase().includes('imagen'));
        const geminiModels = json.models.filter(m => m.name.toLowerCase().includes('gemini'));

        if (imagenModels.length > 0) {
          console.log('IMAGEN (bildgenerering):');
          imagenModels.forEach(m => console.log('  -', m.name));
        } else {
          console.log('IMAGEN: Ingen modell synlig (kan kravas aktivering i Google Cloud)');
        }

        console.log('\nGEMINI (text):');
        geminiModels.slice(0, 5).forEach(m => console.log('  -', m.name));
        if (geminiModels.length > 5) console.log('  ... och', geminiModels.length - 5, 'till');
      }
    } catch (e) {
      console.log('Parse-fel:', e.message);
      console.log('Ratt svar:', data.substring(0, 200));
    }
  });
}).on('error', err => {
  console.log('Natverksfel:', err.message);
});