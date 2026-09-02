import os
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from progress import get_completion, init_db

# ── Display dimensions ──────────────────────────────────
W, H = 480, 648  # portrait — width x height

# ── Paths ───────────────────────────────────────────────
BASE_DIR  = os.path.dirname(__file__)
BOOKS_DIR = os.path.join(BASE_DIR, 'books')

# ── Margins ─────────────────────────────────────────────
MARGIN_TOP    = 50
MARGIN_BOTTOM = 40
MARGIN_LEFT   = 30
MARGIN_RIGHT  = 30
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
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text()

        # Skip very short documents
        if len(text.strip()) < 300:
            continue

        # Clean up excessive blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cleaned = '\n'.join(lines)

        # Skip if it looks like a table of contents
        # TOC has many short lines but little actual text
        if cleaned.count('\n') > 50 and len(cleaned) < 2000:
            continue

        chapters.append(cleaned)

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

        lines = wrap_text(draw, paragraph, FONT_BODY, max_width)

        if current_page:
            lines = [''] + lines

        for line in lines:
            current_page.append(line)

            if len(current_page) >= MAX_LINES:
                pages.append(current_page)
                current_page = []

    if current_page:
        pages.append(current_page)

    return pages


def get_pages(epub_path):
    """
    Returns pages for a book. Paginates on first open and caches
    the result as a JSON file so subsequent opens are instant.
    """
    cache_path = epub_path.replace('.epub', '_pages.json')

    # If cache exists load it instantly
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)

    # Otherwise paginate and save cache
    print('Paginating book for first time — please wait...')
    pages = paginate(epub_path)

    with open(cache_path, 'w') as f:
        json.dump(pages, f)

    return pages


# ══════════════════════════════════════════════════════════
# PAGE RENDERING
# ══════════════════════════════════════════════════════════

def render_page(lines, current_page_num, total_pages):
    """
    Takes a list of text lines and draws them onto a blank canvas.
    Returns a Pillow Image object ready to send to the display.
    """
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    # Draw each line of text
    y = MARGIN_TOP
    for line in lines:
        if line:
            draw.text((MARGIN_LEFT, y), line, font=FONT_BODY, fill=0)
        y += LINE_SPACING

    # Thin divider line above page number
    draw.line(
        [MARGIN_LEFT, H - MARGIN_BOTTOM + 6,
         W - MARGIN_RIGHT, H - MARGIN_BOTTOM + 6],
        fill=0, width=1
    )

    # Page number centred at the bottom
    page_label = f'{current_page_num + 1} / {total_pages}'
    label_w    = draw.textlength(page_label, font=FONT_UI)
    draw.text(
        ((W - label_w) // 2, H - MARGIN_BOTTOM + 10),
        page_label,
        font=FONT_UI,
        fill=0
    )

    return img


# ══════════════════════════════════════════════════════════
# HOME SCREEN RENDERING
# ══════════════════════════════════════════════════════════

def draw_battery(draw, pct, x, y):
    """Draws a small battery icon at position x, y."""
    draw.rectangle([x, y, x + 40, y + 18], outline=0, width=2)
    draw.rectangle([x + 40, y + 5, x + 44, y + 13], fill=0)
    fill_w = int(36 * (pct / 100))
    if fill_w > 0:
        draw.rectangle([x + 2, y + 2, x + 2 + fill_w, y + 16], fill=0)


def render_home(selected_index=0, battery_pct=75):
    """
    Draws the home/library screen.
    selected_index is which item the cursor is currently on.
    Returns a Pillow Image object.
    """
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    books = sorted([
        f for f in os.listdir(BOOKS_DIR)
        if f.endswith('.epub')
    ])

    # ── Top bar ────────────────────────────────────────
    draw.rectangle([0, 0, W, 46], fill=0)
    draw.text((24, 12), 'MY LIBRARY', font=FONT_TOPBAR, fill=255)

    # Battery percentage
    pct_text = f'{battery_pct}%'
    pct_w    = draw.textlength(pct_text, font=FONT_UI)
    draw.text((570 - pct_w, 16), pct_text, font=FONT_UI, fill=255)
    draw_battery(draw, battery_pct, 576, 14)

    # ── Book rows ──────────────────────────────────────
    ROW_H   = 72
    y_start = 46
    visible = 4

    scroll = max(0, selected_index - visible + 1)

    for i in range(visible):
        idx = i + scroll
        if idx >= len(books):
            break

        book = books[idx]
        y    = y_start + i * ROW_H
        sel  = (idx == selected_index)
        bg   = 0 if sel else 255
        fg   = 255 if sel else 0

        draw.rectangle([0, y, W, y + ROW_H - 1], fill=bg)

        if sel:
            draw.text((12, y + 22), '>', font=FONT_UI_BOLD, fill=fg)

        # Title — strip .epub extension
        title = os.path.splitext(book)[0]
        # Truncate long titles so they don't overflow
        while draw.textlength(title, font=FONT_UI_BOLD) > W - 80:
            title = title[:-1]
        draw.text((36, y + 8), title, font=FONT_UI_BOLD, fill=fg)

        # Progress bar
        pct     = get_completion(book)
        pct_int = int(pct * 100)
        bar_x, bar_y, bar_w, bar_h = 36, y + 50, 200, 5

        draw.rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
            fill=fg
        )
        if pct_int < 100:
            fill_end = bar_x + int(bar_w * pct)
            draw.rectangle(
                [fill_end, bar_y, bar_x + bar_w, bar_y + bar_h],
                fill=bg
            )

        label = f'{pct_int}%' + (' ✓' if pct_int == 100 else '')
        draw.text(
            (bar_x + bar_w + 10, bar_y - 2),
            label, font=FONT_UI, fill=fg
        )

        if not sel:
            draw.line([0, y + ROW_H - 1, W, y + ROW_H - 1],
                      fill=180, width=1)

    # ── Bottom menu ────────────────────────────────────
    menu_y = y_start + visible * ROW_H
    draw.line([0, menu_y, W, menu_y], fill=0, width=1)

    menu_options = [
        ('[ Upload New Book ]', 'Visit device IP:5000'),
        ('[ About ]',           'Controls & info'),
    ]

    for i, (label, sublabel) in enumerate(menu_options):
        idx   = len(books) + i
        sel   = (selected_index == idx)
        x     = (W // 4) + i * (W // 2)
        bg    = 0 if sel else 255
        fg    = 255 if sel else 0
        left  = i * (W // 2)
        right = left + W // 2

        draw.rectangle([left, menu_y, right, menu_y + 72], fill=bg)
        draw.text((x, menu_y + 14), label,
                  font=FONT_UI_BOLD, fill=fg, anchor='mm')
        draw.text((x, menu_y + 40), sublabel,
                  font=FONT_UI, fill=fg, anchor='mm')

    draw.line([W // 2, menu_y, W // 2, menu_y + 72], fill=0, width=1)

    # ── Controls hint bar ──────────────────────────────
    hint_y = menu_y + 73
    draw.rectangle([0, hint_y, W, H], fill=230)
    draw.line([0, hint_y, W, hint_y], fill=0, width=1)
    draw.text(
        (W // 2, hint_y + 16),
        'UP/DOWN  Navigate     SELECT  Open     MENU  Return',
        font=FONT_UI, fill=0, anchor='mm'
    )
    draw.text(
        (W // 2, hint_y + 36),
        'Hold MENU 2s to power off safely',
        font=FONT_UI, fill=100, anchor='mm'
    )

    return img


# ══════════════════════════════════════════════════════════
# ABOUT SCREEN
# ══════════════════════════════════════════════════════════

def render_about():
    """Draws the about/help screen."""
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W, 46], fill=0)
    draw.text((24, 12), 'ABOUT', font=FONT_TOPBAR, fill=255)

    lines = [
        ('Controls', True),
        ('UP / DOWN  —  Navigate menu', False),
        ('SELECT     —  Open book / confirm', False),
        ('MENU       —  Return to library', False),
        ('Hold MENU  —  Power off safely', False),
        ('', False),
        ('Upload Books', True),
        ('Connect to the same WiFi and visit', False),
        ('the device IP address on port 5000', False),
        ('in your browser to upload EPUBs.', False),
    ]

    y = 60
    for text, bold in lines:
        if text:
            font = FONT_UI_BOLD if bold else FONT_UI
            draw.text((MARGIN_LEFT, y), text, font=font, fill=0)
        y += 28

    # Back hint
    draw.line([0, H - 36, W, H - 36], fill=0, width=1)
    draw.text((W // 2, H - 18), 'Press MENU to return',
              font=FONT_UI, fill=0, anchor='mm')

    return img


# ══════════════════════════════════════════════════════════
# SHUTDOWN SCREEN
# ══════════════════════════════════════════════════════════

def render_shutdown_screen():
    """
    Draws the image that stays on screen after power off.
    This persists with no power consumption until next boot.
    """
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([8, 8, W - 8, H - 8], outline=0, width=2)
    draw.rectangle([12, 12, W - 12, H - 12], outline=0, width=1)

    # Central text
    draw.text((W // 2, H // 2 - 30), 'POWERED OFF',
              font=FONT_TOPBAR, fill=0, anchor='mm')
    draw.text((W // 2, H // 2 + 10), 'Hold power button to wake',
              font=FONT_UI, fill=0, anchor='mm')

    # Decorative corner marks
    for cx, cy in [(24, 24), (W - 24, 24),
                   (24, H - 24), (W - 24, H - 24)]:
        draw.rectangle([cx - 5, cy - 5, cx + 5, cy + 5], fill=0)

    return img


# ══════════════════════════════════════════════════════════
# ROTATION FUNCTION
# ══════════════════════════════════════════════════════════
def prepare_for_display(img):
    """
    Rotates image 90 degrees for portrait display orientation.
    Call this on any image before sending to the e-ink screen.
    """
    return img.rotate(90, expand=True)

# ══════════════════════════════════════════════════════════
# TESTING
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()

    books = sorted([f for f in os.listdir(BOOKS_DIR) if f.endswith('.epub')])

    if not books:
        print('No EPUBs found in books/ folder')
    else:
        book_path = os.path.join(BOOKS_DIR, books[0])
        print(f'Testing with: {books[0]}')
        print('---')

        # Test 1 — extraction only
        print('Testing extract_text...')
        text = extract_text(book_path)
        print(f'Total characters extracted: {len(text)}')
        print('First 500 characters:')
        print(text[:500])
        print('---')

        # Test 2 — home screen only (no pagination needed)
        print('Testing render_home...')
        img = render_home(selected_index=0, battery_pct=75)
        img.save('test_home.png')
        print('Saved test_home.png')

        # Test 3 — about screen
        print('Testing render_about...')
        img = render_about()
        img.save('test_about.png')
        print('Saved test_about.png')

        # Test 4 — shutdown screen
        print('Testing render_shutdown_screen...')
        img = render_shutdown_screen()
        img.save('test_shutdown.png')
        print('Saved test_shutdown.png')

        print('All done.')