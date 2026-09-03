import os
import sys
import time
import threading
import RPi.GPIO as GPIO

# Add Waveshare library to path
sys.path.insert(0, '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd5in83_V2

from progress import init_db, save, load, get_completion
from renderer import (
    render_home,
    render_page,
    render_about,
    render_shutdown_screen,
    get_pages,
    prepare_for_display,
    BOOKS_DIR
)

# ── GPIO Button pins ────────────────────────────────────
BTN_UP     = 17
BTN_DOWN   = 27
BTN_SELECT = 22
BTN_MENU   = 23

# ── State ───────────────────────────────────────────────
# Tracks what the device is currently showing
STATE_HOME    = 'home'
STATE_READING = 'reading'
STATE_ABOUT   = 'about'

state          = STATE_HOME
selected_index = 0
current_book   = None
current_page   = 0
total_pages    = 0
pages          = []
epd            = None


# ══════════════════════════════════════════════════════════
# DISPLAY
# ══════════════════════════════════════════════════════════

def init_display():
    """Initialise the e-ink display."""
    global epd
    epd = epd5in83_V2.EPD()
    epd.init()
    return epd


def show(img):
    """Rotate for portrait and send image to display."""
    rotated = prepare_for_display(img)
    epd.display(epd.getbuffer(rotated))


def get_books():
    """Return sorted list of epub filenames."""
    return sorted([
        f for f in os.listdir(BOOKS_DIR)
        if f.endswith('.epub')
    ])


def get_battery():
    """Read battery percentage from PiSugar via its web API."""
    try:
        import requests
        r = requests.get('http://localhost:8421/api/battery', timeout=1)
        return int(r.json().get('data', 75))
    except:
        return 75  # fallback if PiSugar not available


# ══════════════════════════════════════════════════════════
# SCREENS
# ══════════════════════════════════════════════════════════

def show_home():
    """Render and display the home screen."""
    battery = get_battery()
    img = render_home(selected_index=selected_index,
                      battery_pct=battery)
    show(img)


def show_current_page():
    """Render and display the current book page."""
    img = render_page(pages[current_page],
                      current_page,
                      total_pages)
    show(img)


def show_about():
    """Render and display the about screen."""
    img = render_about()
    show(img)


def do_shutdown():
    """Display shutdown screen and power off."""
    # Check if user has uploaded a custom screensaver
    screensaver_path = os.path.join(
        os.path.dirname(__file__), 'images', 'screensaver.png'
    )

    if os.path.exists(screensaver_path):
        from PIL import Image
        img = Image.open(screensaver_path)
    else:
        img = render_shutdown_screen()
        img = prepare_for_display(img)

    epd.display(epd.getbuffer(img))
    epd.sleep()
    os.system('sudo shutdown -h now')


# ══════════════════════════════════════════════════════════
# NAVIGATION — HOME SCREEN
# ══════════════════════════════════════════════════════════

def home_up():
    global selected_index
    books = get_books()
    total = len(books) + 2  # books + Upload + About
    selected_index = (selected_index - 1) % total
    show_home()


def home_down():
    global selected_index
    books = get_books()
    total = len(books) + 2
    selected_index = (selected_index + 1) % total
    show_home()


def home_select():
    global state, current_book, current_page, total_pages, pages
    books = get_books()

    if selected_index < len(books):
        # Open a book
        book_file = books[selected_index]
        book_path = os.path.join(BOOKS_DIR, book_file)

        # Load cached pages or paginate
        pages = get_pages(book_path)
        total_pages = len(pages)

        # Load saved progress
        saved_page, _ = load(book_file)
        current_page  = saved_page
        current_book  = book_file
        state         = STATE_READING

        show_current_page()

    elif selected_index == len(books):
        # Upload option selected — show IP address info
        pass  # handled by server.py running in background

    elif selected_index == len(books) + 1:
        # About selected
        state = STATE_ABOUT
        show_about()


# ══════════════════════════════════════════════════════════
# NAVIGATION — READING
# ══════════════════════════════════════════════════════════

def reading_next():
    global current_page
    if current_page < total_pages - 1:
        current_page += 1
        save(current_book, current_page, total_pages)
        show_current_page()


def reading_prev():
    global current_page
    if current_page > 0:
        current_page -= 1
        save(current_book, current_page, total_pages)
        show_current_page()


def reading_menu():
    """Return to home screen from reading."""
    global state
    state = STATE_HOME
    show_home()


# ══════════════════════════════════════════════════════════
# BUTTON HANDLING
# ══════════════════════════════════════════════════════════

def setup_buttons():
    """Configure GPIO pins for button input."""
    GPIO.setmode(GPIO.BCM)
    for pin in [BTN_UP, BTN_DOWN, BTN_SELECT, BTN_MENU]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def handle_menu_button():
    """
    Detect short vs long press on menu button.
    Short press — back to home.
    Long press (2s) — shutdown.
    """
    press_time = time.time()

    # Wait while button is held
    while GPIO.input(BTN_MENU) == GPIO.LOW:
        if time.time() - press_time > 2.0:
            do_shutdown()
            return
        time.sleep(0.05)

    # Short press
    if state == STATE_READING:
        reading_menu()
    elif state == STATE_ABOUT:
        global state
        state = STATE_HOME
        show_home()


def button_callback(channel):
    """Called automatically when any button is pressed."""
    time.sleep(0.05)  # debounce — wait for signal to settle

    if channel == BTN_MENU:
        handle_menu_button()
        return

    if state == STATE_HOME:
        if channel == BTN_UP:
            home_up()
        elif channel == BTN_DOWN:
            home_down()
        elif channel == BTN_SELECT:
            home_select()

    elif state == STATE_READING:
        if channel == BTN_UP:
            reading_prev()
        elif channel == BTN_DOWN:
            reading_next()

    elif state == STATE_ABOUT:
        pass  # only menu button does anything on about screen


def register_button_callbacks():
    """Register interrupt callbacks for all buttons."""
    for pin in [BTN_UP, BTN_DOWN, BTN_SELECT, BTN_MENU]:
        GPIO.add_event_detect(
            pin,
            GPIO.FALLING,
            callback=button_callback,
            bouncetime=300
        )


# ══════════════════════════════════════════════════════════
# SERVER — runs in background
# ══════════════════════════════════════════════════════════

def start_server():
    """Start Flask upload server in a background thread."""
    import subprocess
    subprocess.Popen(
        ['python3', os.path.join(os.path.dirname(__file__), 'server.py')],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    try:
        # Initialise database
        init_db()

        # Start upload server in background
        start_server()

        # Set up buttons
        setup_buttons()
        register_button_callbacks()

        # Initialise display
        init_display()

        # Show home screen
        show_home()

        print('E-reader running. Press Ctrl+C to exit.')

        # Keep running — buttons handled by callbacks
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print('Shutting down...')

    finally:
        GPIO.cleanup()
        if epd:
            epd.sleep()


if __name__ == '__main__':
    main()