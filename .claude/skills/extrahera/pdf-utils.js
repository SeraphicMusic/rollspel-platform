#!/usr/bin/env node

/**
 * PDF Utilities for Rollspels-PDF Extraktor
 *
 * Provides info and split commands for handling large PDFs
 * that exceed Claude's 100-page / 32MB limits.
 *
 * Usage:
 *   node pdf-utils.js info "path/to/file.pdf"
 *   node pdf-utils.js split "path/to/file.pdf" <startPage> <endPage> "path/to/output.pdf"
 *
 * Pages are 1-indexed (first page = 1).
 */

const { PDFDocument } = require('pdf-lib');
const fs = require('fs');

const command = process.argv[2];
const pdfPath = process.argv[3];

if (!command || !pdfPath) {
  console.error('Usage:');
  console.error('  node pdf-utils.js info "path/to/file.pdf"');
  console.error('  node pdf-utils.js split "path/to/file.pdf" <startPage> <endPage> "path/to/output.pdf"');
  process.exit(1);
}

async function info() {
  const bytes = fs.readFileSync(pdfPath);
  const fileSizeMB = parseFloat((bytes.length / (1024 * 1024)).toFixed(1));
  const pdf = await PDFDocument.load(bytes, { ignoreEncryption: true });
  const pageCount = pdf.getPageCount();

  const result = { pageCount, fileSizeMB };
  console.log(JSON.stringify(result));
}

async function split() {
  const startPage = parseInt(process.argv[4], 10);
  const endPage = parseInt(process.argv[5], 10);
  const outputPath = process.argv[6];

  if (!startPage || !endPage || !outputPath) {
    console.error('Usage: node pdf-utils.js split "input.pdf" <startPage> <endPage> "output.pdf"');
    process.exit(1);
  }

  const bytes = fs.readFileSync(pdfPath);
  const srcPdf = await PDFDocument.load(bytes, { ignoreEncryption: true });
  const totalPages = srcPdf.getPageCount();

  if (startPage < 1 || endPage > totalPages || startPage > endPage) {
    console.error(`Invalid page range ${startPage}-${endPage}. PDF has ${totalPages} pages.`);
    process.exit(1);
  }

  const newPdf = await PDFDocument.create();
  // pdf-lib uses 0-based indices
  const indices = [];
  for (let i = startPage - 1; i < endPage; i++) {
    indices.push(i);
  }
  const copiedPages = await newPdf.copyPages(srcPdf, indices);
  for (const page of copiedPages) {
    newPdf.addPage(page);
  }

  const newBytes = await newPdf.save();
  fs.writeFileSync(outputPath, newBytes);
  console.log(JSON.stringify({
    outputPath,
    pages: `${startPage}-${endPage}`,
    pageCount: endPage - startPage + 1,
  }));
}

(async () => {
  try {
    if (command === 'info') {
      await info();
    } else if (command === 'split') {
      await split();
    } else {
      console.error(`Unknown command: ${command}. Use "info" or "split".`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
})();
