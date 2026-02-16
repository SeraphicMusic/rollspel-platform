#!/usr/bin/env node

/**
 * DoD PDF Extraktor - Word Document Generator
 *
 * Tar en JSON-fil med extraherat innehåll och skapar ett formaterat Word-dokument.
 *
 * Användning:
 *   node create-docx.js <input.json> <output.docx>
 */

const {
  Document,
  Packer,
  Paragraph,
  Table,
  TableRow,
  TableCell,
  TextRun,
  HeadingLevel,
  WidthType,
  BorderStyle,
  AlignmentType,
  convertInchesToTwip,
} = require('docx');
const fs = require('fs');
const path = require('path');

// Kommandoradsargument
const args = process.argv.slice(2);

if (args.length < 2) {
  console.error('Användning: node create-docx.js <input.json> <output.docx>');
  process.exit(1);
}

const inputPath = args[0];
const outputPath = args[1];

// Läs JSON-data
let data;
try {
  const jsonContent = fs.readFileSync(inputPath, 'utf-8');
  data = JSON.parse(jsonContent);
} catch (error) {
  console.error(`Kunde inte läsa JSON-fil: ${error.message}`);
  process.exit(1);
}

/**
 * Skapar en tabell för NPC-statblock (grundegenskaper)
 */
function createAttributeTable(attributes) {
  const rows = [
    // Header-rad
    new TableRow({
      children: [
        new TableCell({
          children: [new Paragraph({
            children: [new TextRun({ text: 'Egenskap', bold: true })],
            alignment: AlignmentType.CENTER,
          })],
          shading: { fill: 'E0E0E0' },
        }),
        new TableCell({
          children: [new Paragraph({
            children: [new TextRun({ text: 'Värde', bold: true })],
            alignment: AlignmentType.CENTER,
          })],
          shading: { fill: 'E0E0E0' },
        }),
      ],
    }),
  ];

  // Data-rader
  for (const [attr, value] of Object.entries(attributes)) {
    rows.push(
      new TableRow({
        children: [
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: attr, bold: true })],
              alignment: AlignmentType.CENTER,
            })],
          }),
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: String(value) })],
              alignment: AlignmentType.CENTER,
            })],
          }),
        ],
      })
    );
  }

  return new Table({
    rows,
    width: {
      size: 3000,
      type: WidthType.DXA,
    },
  });
}

/**
 * Skapar en tabell för färdigheter
 */
function createSkillsTable(skills) {
  const rows = [
    // Header-rad
    new TableRow({
      children: [
        new TableCell({
          children: [new Paragraph({
            children: [new TextRun({ text: 'Färdighet', bold: true })],
            alignment: AlignmentType.CENTER,
          })],
          shading: { fill: 'E0E0E0' },
        }),
        new TableCell({
          children: [new Paragraph({
            children: [new TextRun({ text: 'FV', bold: true })],
            alignment: AlignmentType.CENTER,
          })],
          shading: { fill: 'E0E0E0' },
        }),
      ],
    }),
  ];

  // Data-rader
  for (const [skill, fv] of Object.entries(skills)) {
    rows.push(
      new TableRow({
        children: [
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: skill })],
            })],
          }),
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: String(fv) })],
              alignment: AlignmentType.CENTER,
            })],
          }),
        ],
      })
    );
  }

  return new Table({
    rows,
    width: {
      size: 4000,
      type: WidthType.DXA,
    },
  });
}

/**
 * Skapar en generell tabell
 */
function createGenericTable(headers, tableRows) {
  const rows = [
    // Header-rad
    new TableRow({
      children: headers.map(header =>
        new TableCell({
          children: [new Paragraph({
            children: [new TextRun({ text: header, bold: true })],
            alignment: AlignmentType.CENTER,
          })],
          shading: { fill: 'E0E0E0' },
        })
      ),
    }),
  ];

  // Data-rader
  for (const row of tableRows) {
    rows.push(
      new TableRow({
        children: row.map(cell =>
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: String(cell) })],
            })],
          })
        ),
      })
    );
  }

  return new Table({
    rows,
    width: {
      size: 100,
      type: WidthType.PERCENTAGE,
    },
  });
}

/**
 * Konverterar innehållsobjekt till docx-element
 */
function convertContentToElements(content) {
  const elements = [];

  for (const item of content) {
    switch (item.type) {
      case 'heading1':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: item.text, bold: true })],
            heading: HeadingLevel.HEADING_1,
            spacing: { before: 400, after: 200 },
          })
        );
        break;

      case 'heading2':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: item.text, bold: true })],
            heading: HeadingLevel.HEADING_2,
            spacing: { before: 300, after: 150 },
          })
        );
        break;

      case 'heading3':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: item.text, bold: true })],
            heading: HeadingLevel.HEADING_3,
            spacing: { before: 200, after: 100 },
          })
        );
        break;

      case 'paragraph':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: item.text })],
            spacing: { after: 120 },
          })
        );
        break;

      case 'italic':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: item.text, italics: true })],
            spacing: { after: 120 },
          })
        );
        break;

      case 'statblock':
        // Karaktärsnamn som rubrik (skippa om det redan är en heading2 ovanför)
        if (item.name) {
          elements.push(
            new Paragraph({
              children: [new TextRun({ text: `Statblock: ${item.name}`, bold: true, size: 22 })],
              spacing: { before: 150, after: 80 },
            })
          );
        }

        // Grundegenskaper (stöd för både 'attributes' och 'stats')
        const attrs = item.attributes || item.stats;
        if (attrs && Object.keys(attrs).length > 0) {
          elements.push(createAttributeTable(attrs));
          elements.push(new Paragraph({ spacing: { after: 80 } }));
        }

        // Färdigheter (stöd för både 'skills' och 'extraStats')
        const skills = item.skills || item.extraStats;
        if (skills && Object.keys(skills).length > 0) {
          elements.push(createSkillsTable(skills));
          elements.push(new Paragraph({ spacing: { after: 150 } }));
        }

        // Övriga värden (KP, SV, etc.)
        if (item.other) {
          const otherText = Object.entries(item.other)
            .map(([key, value]) => `${key}: ${value}`)
            .join(', ');
          elements.push(
            new Paragraph({
              children: [new TextRun({ text: otherText, bold: true })],
              spacing: { after: 150 },
            })
          );
        }
        break;

      case 'table':
        if (item.headers && item.rows) {
          elements.push(createGenericTable(item.headers, item.rows));
          elements.push(new Paragraph({ spacing: { after: 200 } }));
        }
        break;

      case 'list':
        if (item.items) {
          for (const listItem of item.items) {
            elements.push(
              new Paragraph({
                children: [new TextRun({ text: `• ${listItem}` })],
                spacing: { after: 60 },
                indent: { left: convertInchesToTwip(0.25) },
              })
            );
          }
          elements.push(new Paragraph({ spacing: { after: 100 } }));
        }
        break;

      case 'pagebreak':
        elements.push(
          new Paragraph({
            children: [new TextRun({ text: `--- Sida ${item.page || ''} ---` })],
            spacing: { before: 300, after: 300 },
            alignment: AlignmentType.CENTER,
          })
        );
        break;

      default:
        // Okänd typ, behandla som paragraph
        if (item.text) {
          elements.push(
            new Paragraph({
              children: [new TextRun({ text: item.text })],
              spacing: { after: 120 },
            })
          );
        }
    }
  }

  return elements;
}

// Skapa dokumentet
async function createDocument() {
  const title = data.title || 'Rollspels-extraktion';
  const pages = data.pages || '';
  const content = data.content || [];

  // Dokumentelement
  const children = [
    // Titel
    new Paragraph({
      children: [new TextRun({ text: title, bold: true, size: 48 })],
      heading: HeadingLevel.TITLE,
      spacing: { after: 200 },
    }),
  ];

  // Sidintervall om angivet
  if (pages) {
    children.push(
      new Paragraph({
        children: [new TextRun({ text: `Sidor: ${pages}`, italics: true })],
        spacing: { after: 400 },
      })
    );
  }

  // Konvertera och lägg till innehåll
  const contentElements = convertContentToElements(content);
  children.push(...contentElements);

  const doc = new Document({
    sections: [
      {
        properties: {},
        children,
      },
    ],
  });

  // Spara dokumentet
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log(`Word-dokument skapat: ${outputPath}`);
}

// Kör
createDocument().catch(error => {
  console.error(`Fel vid skapande av dokument: ${error.message}`);
  process.exit(1);
});
