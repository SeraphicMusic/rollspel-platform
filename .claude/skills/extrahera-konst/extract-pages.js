#!/usr/bin/env node
const { PDFDocument } = require('pdf-lib');
const fs = require('fs');

const [,, inputPath, startPage, endPage, outputPath] = process.argv;

if (!inputPath || !startPage || !endPage || !outputPath) {
  console.error('Usage: node extract-pages.js <input.pdf> <startPage> <endPage> <output.pdf>');
  process.exit(1);
}

async function extractPages() {
  try {
    const bytes = fs.readFileSync(inputPath);
    const srcPdf = await PDFDocument.load(bytes, { ignoreEncryption: true });
    const totalPages = srcPdf.getPageCount();

    console.log(`Total pages: ${totalPages}`);

    const start = parseInt(startPage) - 1;
    const end = Math.min(parseInt(endPage), totalPages);

    const newPdf = await PDFDocument.create();
    const indices = [];
    for (let i = start; i < end; i++) {
      indices.push(i);
    }

    const copiedPages = await newPdf.copyPages(srcPdf, indices);
    for (const page of copiedPages) {
      newPdf.addPage(page);
    }

    const newBytes = await newPdf.save();
    fs.writeFileSync(outputPath, newBytes);
    console.log(`Extracted pages ${startPage}-${endPage} to ${outputPath}`);
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
}

extractPages();
