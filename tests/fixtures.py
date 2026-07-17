"""Syntetiska PDF-fixturer med känt facit, genererade med PyMuPDF."""
import fitz

A4 = fitz.paper_rect("a4")

WATERMARK = "Testförlaget AB, alla rättigheter"


def text_pdf(path, n_pages=3):
    """Ren digital text: rubrik + brödtext + sidnummer + sidhuvud."""
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=A4.width, height=A4.height)
        page.insert_text((72, 40), "Regelboken — kapitel %d" % (i + 1),
                         fontsize=9)  # sidhuvud (upprepas)
        page.insert_text((72, 120), "Kapitel %d" % (i + 1), fontsize=22)
        y = 170
        for j in range(12):
            page.insert_text(
                (72, y),
                "Detta är brödtext rad %d på sida %d. Rollpersonen slår 1T20 "
                "mot sitt färdighetsvärde." % (j + 1, i + 1),
                fontsize=11)
            y += 18
        page.insert_text((290, 810), str(i + 1), fontsize=10)  # sidnummer
    doc.save(str(path))
    doc.close()


def two_column_pdf(path):
    """En sida med två kolumner: vänster ska läsas före höger."""
    doc = fitz.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    y = 100
    for j in range(10):
        page.insert_text((60, y), "VANSTER-%02d text i vänsterspalten" % j,
                         fontsize=11)
        page.insert_text((330, y), "HOGER-%02d text i högerspalten" % j,
                         fontsize=11)
        y += 30
    doc.save(str(path))
    doc.close()


def _page_as_pixmap(text="Inskannad sida", extra=None):
    src = fitz.open()
    page = src.new_page(width=A4.width, height=A4.height)
    page.insert_text((72, 120), text, fontsize=16)
    for i, line in enumerate(extra or []):
        page.insert_text((72, 160 + i * 20), line, fontsize=11)
    pix = page.get_pixmap(dpi=100)
    src.close()
    return pix


def image_pdf(path, n_pages=3, watermark=False):
    """Bildsidor (skanning-simulering); ev. med stub-textlager (vattenstämpel)."""
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=A4.width, height=A4.height)
        pix = _page_as_pixmap("Inskannad sida %d" % (i + 1),
                              ["Lorem ipsum rad %d" % j for j in range(10)])
        page.insert_image(page.rect, pixmap=pix)
        if watermark:
            page.insert_text((150, 826), WATERMARK, fontsize=9)
    doc.save(str(path))
    doc.close()


def mixed_pdf(path):
    """Sida 1 digital text, sida 2 bild, sida 3 bild+vattenstämpel."""
    doc = fitz.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    for j in range(15):
        page.insert_text((72, 100 + j * 20),
                         "Digital textrad %d med gott om innehåll på sidan." % j,
                         fontsize=11)
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_image(page.rect, pixmap=_page_as_pixmap("Bildsida"))
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_image(page.rect, pixmap=_page_as_pixmap("Bildsida med stub"))
    page.insert_text((150, 826), WATERMARK, fontsize=9)
    doc.save(str(path))
    doc.close()


def dod_text_pdf(path):
    """Digital text med tydlig DoD-signatur för systemdetektering."""
    doc = fitz.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    lines = [
        "Drakar och Demoner — äventyr",
        "Grottrollet har STY 18, FYS 12, SMI 9, INT 5, PSY 8, KAR 4, STO 20.",
        "Kroppspoäng beräknas som vanligt och Skadebonus är +1T4.",
        "Färdighetsvärde: Svärd 14. Spelledarperson: byäldsten.",
        "En besvärjelse kostar magipunkter.",
    ]
    for j, line in enumerate(lines):
        page.insert_text((72, 100 + j * 24), line, fontsize=12)
    doc.save(str(path))
    doc.close()
