#server.py runs a tiny website on the device. When connecting your own device to the same WiFi network as the ereader and visit its IP in a browser, server.py is what responds
#server.py serves pages, accepts file uploads, and manages the library through a web browser
#server.py should:
#show the library page when someone visits the IP in the browser
#accept new book uploads and return to library page
#delete existing books and return to library page
#be accesible from any device on the network
#accept screensaver image uploads, process and centre them at display resolution

from flask import Flask, request, render_template, redirect, url_for
import os
from PIL import Image
from progress import get_completion, delete

app = Flask(__name__) #creates web server application
BOOKS_DIR   = os.path.join(os.path.dirname(__file__), 'books')   # builds path to book folder
IMAGES_DIR  = os.path.join(os.path.dirname(__file__), 'images')  # builds path to images folder

# Create folders if they don't exist
os.makedirs(BOOKS_DIR,  exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)


# ── INDEX ROUTE ────────────────────────────────────────────────────────────────

@app.route('/') #homepage route
def index():
    books = sorted([
        f for f in os.listdir(BOOKS_DIR)
        if f.endswith('.epub')
    ]) #get epub books from books folder in alphabetical order
    library = [
        {'name': os.path.splitext(b)[0],
         'file': b,
         'pct':  int(get_completion(b) * 100)}
        for b in books
    ] #loop through each book and creates a dictionary

    # Check if a screensaver has been uploaded already
    has_screensaver = os.path.exists(
        os.path.join(IMAGES_DIR, 'screensaver.png')
    )

    return render_template('index.html',
                           library=library,
                           has_screensaver=has_screensaver) #loads templates/index.html and passes the library and screensaver status into it


# ── UPLOAD ROUTE ───────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST']) #only responds to post requests. POST = http browser request that browser sends when you submit a form with a file attached. this route only accepts form submissions.
def upload():
    f = request.files.get('book') #retrieves uploaded file from the form submission
    if f and f.filename.endswith('.epub'):
        f.save(os.path.join(BOOKS_DIR, f.filename))
    return redirect(url_for('index')) #saves file in books and redirects back to the homepage


# ── DELETE ROUTE ───────────────────────────────────────────────────────────────

@app.route('/delete/<filename>') #variable filename route
def delete_book(filename):
    path = os.path.join(BOOKS_DIR, filename)
    # check file exists before trying to delete
    if os.path.exists(path):
        os.remove(path)          #deletes epub file from books folder
        delete(filename)         #delete function from progress.py to remove the books progress record from the db
    return redirect(url_for('index')) #sends browser back to the homepage


# ── SCREENSAVER UPLOAD ROUTE ───────────────────────────────────────────────────

@app.route('/upload-screensaver', methods=['POST'])
def upload_screensaver():
    f = request.files.get('screensaver')
    if f and f.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):

        img = Image.open(f).convert('1')

        # Resize to fit portrait display maintaining aspect ratio
        img.thumbnail((480, 648), Image.LANCZOS)

        # Centre on portrait canvas
        canvas = Image.new('1', (480, 648), 255)
        x = (480 - img.width)  // 2
        y = (648 - img.height) // 2
        canvas.paste(img, (x, y))

        # Rotate for display
        canvas = canvas.rotate(90, expand=True)

        canvas.save(os.path.join(IMAGES_DIR, 'screensaver.png'))

    return redirect(url_for('index'))


# ── DELETE SCREENSAVER ROUTE ───────────────────────────────────────────────────

@app.route('/delete-screensaver')
def delete_screensaver():
    path = os.path.join(IMAGES_DIR, 'screensaver.png')
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('index'))


# only runs when file is directly run. helpful for testing purposes
# host is 0.0.0.0 and not localhost so that flask accepts connections from any device on the network rather than just this computer
# server listens on port 5000
# debug on so flask shows error page in browser and restarts itself whenever changes are saved to the file. Only on for development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)