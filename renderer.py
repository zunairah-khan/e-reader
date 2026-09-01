import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from progress import get_completion, init_db

# ── Display dimensions ──────────────────────────────────
W, H = 648, 480

# ── Paths ───────────────────────────────────────────────
BASE_DIR  = os.path.dirname(__file__)
BOOKS_DIR = os.path.join(BASE_DIR, 'books')

# ── Margins ─────────────────────────────────────────────
MARGIN_TOP    = 50
MARGIN_BOTTOM = 40
MARGIN_LEFT   = 36
MARGIN_RIGHT  = 36
LINE_SPACING  = 34
MAX_LINES     = (H - MARGIN_TOP - MARGIN_BOTTOM) // LINE_SPACING

# ── Fonts ───────────────────────────────────────────────
def load_font(name, size):
    """Try to load a font, fall back to default if not found."""
    try:
        return ImageFont.truetype(name, size)
    except:
        return ImageFont.load_default()

FONT_BODY    = load_font('LiberationSerif-Regular.ttf', 22)
FONT_UI      = load_font('LiberationSans-Regular.ttf', 13)
FONT_UI_BOLD = load_font('LiberationSans-Bold.ttf', 15)
FONT_TOPBAR  = load_font('LiberationSans-Bold.ttf', 20)


# ══════════════════════════════════════════════════════════
# EPUB PARSING
# ══════════════════════════════════════════════════════════

def extract_text(epub_path):
    """
    Opens an EPUB and extracts clean plain text from every chapter.
    Skips non-content documents like copyright pages and TOC.
    Returns one large string of the entire book's text.
    """
    book     = epub.read_epub(epub_path)
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        # Strip HTML tags using BeautifulSoup
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text()

        # Skip very short documents — likely metadata, TOC, blank pages
        if len(text.strip()) < 100:
            continue

        # Clean up excessive blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        chapters.append('\n'.join(lines))

    # Join all chapters with double newline between them
    return '\n\n'.join(chapters)


# ══════════════════════════════════════════════════════════
# PAGINATION
# ══════════════════════════════════════════════════════════

def wrap_text(draw, text, font, max_width):
    """
    Splits a string of text into lines that fit within max_width pixels.
    Works word by word — measures actual pixel width before deciding
    whether a word fits on the current line.
    """
    words = text.split()
    lines = []
    line  = ''

    for word in words:
        test = line + ' ' + word if line else word
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines


def paginate(epub_path):
    """
    Splits the entire book into screen sized pages.
    Each page is a list of text lines that fit on the 648x480 display.
    Returns a list of pages.
    """
    # Create a dummy canvas just for measuring text widths
    dummy_img = Image.new('1', (W, H), 255)
    draw      = ImageDraw.Draw(dummy_img)
    max_width = W - MARGIN_LEFT - MARGIN_RIGHT

    full_text  = extract_text(epub_path)
    paragraphs = full_text.split('\n\n')

    pages        = []
    current_page = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        # Wrap this paragraph into pixel-accurate lines
        lines = wrap_text(draw, paragraph, FONT_BODY, max_width)

        # Add blank line between paragraphs for readability
        if current_page:
            lines = [''] + lines

        for line in lines:
            current_page.append(line)

            # Page is full — save it and start a new one
            if len(current_page) >= MAX_LINES:
                pages.append(current_page)
                current_page = []

    # Don't lose the final partial page
    if current_page:
        pages.append(current_page)

    return pages


# ══════════════════════════════════════════════════════════
# TESTING
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()

    books = sorted([f for f in os.listdir(BOOKS_DIR) if f.endswith('.epub')])

    if not books:
        print('No EPUBs found in books/ folder')
        print('Download one from gutenberg.org and place it in books/')
    else:
        book_path = os.path.join(BOOKS_DIR, books[0])
        print(f'Testing with: {books[0]}')
        print('---')

        # Test 1 — extraction
        print('Testing extract_text...')
        text = extract_text(book_path)
        print(f'Total characters extracted: {len(text)}')
        print('First 500 characters:')
        print(text[:500])
        print('---')

        # Test 2 — pagination
        print('Testing paginate...')
        print('This may take a few seconds for a full book...')
        pages = paginate(book_path)
        print(f'Total pages: {len(pages)}')
        print('---')
        print('First page lines:')
        for line in pages[0]:
            print(repr(line))
        print('---')
        print('Second page lines:')
        for line in pages[1]:
            print(repr(line))