from curses import raw
import os
import re
import json
import ebooklib
from ebooklib import epub
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

# ── Characters per line — adjust to match font size ─────
CHARS_PER_LINE = 42

# ── Fonts ───────────────────────────────────────────────
def load_font(name, size):
    """Load font — detects OS and uses appropriate font path."""
    if os.name == 'nt':  # Windows
        windows_fonts = {
            'LiberationSerif-Regular.ttf': 'georgia.ttf',
            'LiberationSerif-Bold.ttf':    'georgiab.ttf',
            'LiberationSans-Regular.ttf':  'arial.ttf',
            'LiberationSans-Bold.ttf':     'arialbd.ttf',
        }
        fallback = windows_fonts.get(name, 'arial.ttf')
        try:
            return ImageFont.truetype(f'C:/Windows/Fonts/{fallback}', size)
        except Exception as e:
            print(f'Font error: {e}')
            return ImageFont.load_default()
    else:  # Linux / Pi
        try:
            return ImageFont.truetype(name, size)
        except Exception as e:
            print(f'Font error: {e}')
            return ImageFont.load_default()

FONT_BODY    = load_font('LiberationSerif-Bold.ttf', 22)
FONT_UI      = load_font('LiberationSans-Regular.ttf', 15)
FONT_UI_BOLD = load_font('LiberationSans-Bold.ttf', 17)
FONT_TOPBAR  = load_font('LiberationSans-Bold.ttf', 22)


# ══════════════════════════════════════════════════════════
# EPUB PARSING
# ══════════════════════════════════════════════════════════

def strip_html(content):
    """Strip HTML tags using regex — much faster than BeautifulSoup on Pi Zero."""
    text = content.decode('utf-8', errors='ignore')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&#13;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text(epub_path):
    """
    Opens an EPUB and extracts clean plain text from every chapter.
    Uses regex instead of BeautifulSoup for speed on Pi Zero.
    Skips non-content documents like copyright pages and TOC.
    Returns one large string of the entire book's text.
    """
    book     = epub.read_epub(epub_path)
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        text = strip_html(item.get_content())

        # Skip very short documents — likely metadata, TOC, blank pages
        if len(text.strip()) < 300:
            continue

        # Skip if it looks like a table of contents
        # TOC has many short lines but very little actual text
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cleaned = '\n'.join(lines)
        if cleaned.count('\n') > 50 and len(cleaned) < 2000:
            continue

        chapters.append(text)

    return '\n\n'.join(chapters)


# ══════════════════════════════════════════════════════════
# PAGINATION
# ══════════════════════════════════════════════════════════

def wrap_text_by_chars(text):
    """
    Wraps text by character count instead of pixel width.
    Much faster than textlength() on Pi Zero.
    Adjust CHARS_PER_LINE at the top of this file to fit your font.
    """
    words = text.split()
    lines, line = [], ''

    for word in words:
        test = line + ' ' + word if line else word
        if len(test) <= CHARS_PER_LINE:
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
    Splits the entire book into screen sized pages using
    character count wrapping for speed on Pi Zero.
    Each page is a list of text lines that fit on the display.
    Returns a list of pages.
    """
    full_text  = extract_text(epub_path)
    paragraphs = full_text.split('\n\n')

    pages        = []
    current_page = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        lines = wrap_text_by_chars(paragraph)

        # Add blank line between paragraphs for readability
        if current_page:
            lines = [''] + lines

        for line in lines:
            current_page.append(line)

            if len(current_page) >= MAX_LINES:
                pages.append(current_page)
                current_page = []

    # Don't lose the final partial page
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
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    books = sorted([
        f for f in os.listdir(BOOKS_DIR)
        if f.endswith('.epub')
    ])

    # ── Header ─────────────────────────────────────────
    draw.text((36, 24), 'MY LIBRARY', font=FONT_TOPBAR, fill=0)

    ## Battery — top right, black rounded pill
    pct_text = f'{battery_pct}%'
    pct_w    = draw.textlength(pct_text, font=FONT_UI_BOLD)
    pill_pad = 10
    pill_x   = W - 36 - pct_w - pill_pad * 2
    pill_y   = 18
    draw.rounded_rectangle(
        [pill_x, pill_y, pill_x + pct_w + pill_pad * 2, pill_y + 28],
        radius=14,
        fill=0
    )
    draw.text((pill_x + pill_pad, pill_y + 6), pct_text, font=FONT_UI_BOLD, fill=255)

    # Curved rule under header — drawn as a very shallow arc
    # Simulated with a thick line and rounded caps
    draw.line([36, 58, W - 36, 58], fill=0, width=1)
    # Small decorative end circles
    draw.ellipse([32, 54, 40, 62], fill=0)
    draw.ellipse([W - 40, 54, W - 32, 62], fill=0)

    # ── Book list ──────────────────────────────────────
    ROW_H   = 76
    y_start = 70
    visible = 6

    scroll = max(0, selected_index - visible + 1)

    for i in range(visible):
        idx = i + scroll
        if idx >= len(books):
            break

        book = books[idx]
        y    = y_start + i * ROW_H
        sel  = (idx == selected_index)

        if sel:
            # Filled black rounded rectangle
            draw.rounded_rectangle(
                [10, y + 2, W - 10, y + ROW_H - 4],
                radius=12,
                fill=0
            )
            fg = 255  # white text and elements on black
        else:
            fg = 0    # black text on white

        # Title
        title = os.path.splitext(book)[0]
        while draw.textlength(title, font=FONT_UI_BOLD) > W - 100:
            title = title[:-1]

        text_x = 28 if sel else 20
        draw.text((text_x, y + 10), title, font=FONT_UI_BOLD, fill=fg)

        # Progress percentage — right aligned
        pct     = get_completion(book)
        pct_int = int(pct * 100)
        label   = f'{pct_int}%' + (' ✓' if pct_int == 100 else '')
        label_w = draw.textlength(label, font=FONT_UI_BOLD)
        draw.text((W - 36 - label_w, y + 10), label, font=FONT_UI_BOLD, fill=fg)

        # Rounded progress bar
        bar_x, bar_y, bar_w, bar_h = 28, y + 48, W - 60, 6

        if sel:
        # Track — medium grey on black so fill is visible
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                radius=3, fill=60
            )
            # Fill — white
            fill_w = int(bar_w * pct)
            if fill_w > 0:
                draw.rounded_rectangle(
                    [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
                    radius=3, fill=0
                )
        else:
            # Track — light grey with black outline
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                radius=3, fill=220, outline=0, width=1
            )
            # Fill — black
            if pct_int > 0:
                fill_w = max(6, int(bar_w * pct))
                draw.rounded_rectangle(
                    [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
                    radius=3, fill=0
                )

        # Row divider — only on unselected rows
        if not sel:
            draw.line([36, y + ROW_H - 2, W - 36, y + ROW_H - 2],
                      fill=200, width=1)

    # ── About — bottom ─────────────────────────────────
    about_sel = (selected_index == len(books))

    # Decorative rule above About — same style as header
    draw.line([36, H - 54, W - 36, H - 54], fill=0, width=1)
    draw.ellipse([32, H - 58, 40, H - 50], fill=0)
    draw.ellipse([W - 40, H - 58, W - 32, H - 50], fill=0)

    about_text = 'About'
    about_w    = draw.textlength(about_text, font=FONT_UI_BOLD)

    if about_sel:
        # Black filled rounded rectangle, white text
        draw.rounded_rectangle(
            [10, H - 48, W - 10, H - 8],
            radius=12,
            fill=0
        )
        draw.text(((W - about_w) // 2, H - 38),
              about_text, font=FONT_UI_BOLD, fill=255)
    else:
        draw.text(((W - about_w) // 2, H - 38),
              about_text, font=FONT_UI_BOLD, fill=0)

    return img


# ══════════════════════════════════════════════════════════
# ABOUT SCREEN
# ══════════════════════════════════════════════════════════

def render_about():
    """Draws the about/help screen — minimal editorial style."""
    img  = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)

    # ── Header ─────────────────────────────────────────
    draw.text((36, 24), 'ABOUT', font=FONT_TOPBAR, fill=0)

    # Decorative rule — same style as home screen
    draw.line([36, 58, W - 36, 58], fill=0, width=1)
    draw.ellipse([32, 54, 40, 62], fill=0)
    draw.ellipse([W - 40, 54, W - 32, 62], fill=0)

    # ── Controls section ───────────────────────────────
    y = 78

    # Section label — rounded pill
    draw.rounded_rectangle([36, y, 140, y + 24], radius=12, fill=0)
    draw.text((88, y + 6), 'Controls', font=FONT_UI_BOLD,
              fill=255, anchor='mt')

    y += 34

    controls = [
        ('UP / DOWN', 'Navigate'),
        ('SELECT',    'Open book'),
        ('MENU',      'Return to library'),
        ('Hold MENU', 'Power off'),
    ]

    for key, action in controls:
        # Key label — small rounded border
        key_w = draw.textlength(key, font=FONT_UI_BOLD) + 16
        draw.rounded_rectangle([36, y, 36 + key_w, y + 22],
                               radius=6, outline=0, width=1)
        draw.text((44, y + 3), key, font=FONT_UI_BOLD, fill=0)

        # Action — plain text after key
        draw.text((36 + key_w + 12, y + 3), action, font=FONT_UI_BOLD, fill=0)

        y += 34

    # ── Upload section ─────────────────────────────────
    y += 8

    # Section divider
    draw.line([36, y, W - 36, y], fill=0, width=1)
    draw.ellipse([32, y - 4, 40, y + 4], fill=0)
    draw.ellipse([W - 40, y - 4, W - 32, y + 4], fill=0)

    y += 14

    # Section label — rounded pill
    draw.rounded_rectangle([36, y, 172, y + 24], radius=12, fill=0)
    draw.text((104, y + 6), 'Upload Books', font=FONT_UI_BOLD,
              fill=255, anchor='mt')

    y += 34

    upload_lines = [
        'Connect to the same WiFi and visit the device IP address on',
        'port 5000 in your browser.'
    ]

    for line in upload_lines:
        draw.text((36, y), line, font=FONT_UI, fill=0)
        y += 26

    # ── IP address — rounded box ────────────────────────
    y += 8
    ip_text = '192.168.1.118:5000'
    ip_w    = draw.textlength(ip_text, font=FONT_UI_BOLD)
    box_x   = (W - ip_w - 24) // 2
    draw.rounded_rectangle([box_x, y, box_x + ip_w + 24, y + 28],
                           radius=8, outline=0, width=1, fill=0)
    draw.text((box_x + 12, y + 4), ip_text, font=FONT_UI_BOLD, fill=255)

    # ── Back hint ──────────────────────────────────────
    draw.line([36, H - 54, W - 36, H - 54], fill=0, width=1)
    draw.ellipse([32, H - 58, 40, H - 50], fill=0)
    draw.ellipse([W - 40, H - 58, W - 32, H - 50], fill=0)

    draw.text((W // 2, H - 32), 'Press MENU to return',
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

    # Outer rounded border
    draw.rounded_rectangle([8, 8, W - 8, H - 8],
                           radius=20, outline=0, width=2)
    draw.rounded_rectangle([14, 14, W - 14, H - 14],
                           radius=16, outline=0, width=1)

    # Decorative circles in corners
    for cx, cy in [(36, 36), (W - 36, 36),
                   (36, H - 36), (W - 36, H - 36)]:
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], outline=0, width=1)
        draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=0)

    # Decorative rule above text
    draw.line([60, H // 2 - 52, W - 60, H // 2 - 52], fill=0, width=1)
    draw.ellipse([56, H // 2 - 56, 64, H // 2 - 48], fill=0)
    draw.ellipse([W - 64, H // 2 - 56, W - 56, H // 2 - 48], fill=0)

    # Central text
    powered_w = draw.textlength('POWERED OFF', font=FONT_TOPBAR)
    draw.text(((W - powered_w) // 2, H // 2 - 40),
              'POWERED OFF', font=FONT_TOPBAR, fill=0)

    draw.text((W // 2, H // 2 + 8), 'Hold power button to wake',
              font=FONT_UI, fill=0, anchor='mm')

    # Decorative rule below text
    draw.line([60, H // 2 + 30, W - 60, H // 2 + 30], fill=0, width=1)
    draw.ellipse([56, H // 2 + 26, 64, H // 2 + 34], fill=0)
    draw.ellipse([W - 64, H // 2 + 26, W - 56, H // 2 + 34], fill=0)

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
    import time
    init_db()

    books = sorted([f for f in os.listdir(BOOKS_DIR) if f.endswith('.epub')])

    if not books:
        print('No EPUBs found in books/ folder')
    else:
        book_path = os.path.join(BOOKS_DIR, books[0])
        print(f'Testing with: {books[0]}')
        print('---')

        # Test extraction
        print('Testing extract_text...')
        t = time.time()
        text = extract_text(book_path)
        print(f'Extraction took: {time.time() - t:.2f}s')
        print(f'Total characters: {len(text)}')
        print('First 300 characters:')
        print(text[:300])
        print('---')

        # Test pagination
        print('Testing paginate...')
        t = time.time()
        pages = paginate(book_path)
        print(f'Pagination took: {time.time() - t:.2f}s')
        print(f'Total pages: {len(pages)}')
        print('---')

        # Render first page as PNG
        print('Rendering first page...')
        img = render_page(pages[10], 0, len(pages))
        img.save('test_page.png')
        print('Saved test_page.png')

        # Render home screen as PNG
        print('Rendering home screen...')
        img = render_home(selected_index=0, battery_pct=100)
        img.save('test_home.png')
        print('Saved test_home.png')

        # Render about screen
        print('Rendering about screen...')
        img = render_about()
        img.save('test_about.png')
        print('Saved test_about.png')

        # Render shutdown screen
        print('Rendering shutdown screen...')
        img = render_shutdown_screen()
        img.save('test_shutdown.png')
        print('Saved test_shutdown.png')

        print('All done — open PNG files to check layout.')