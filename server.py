#server.py runs a tiny website on the device. When connecting your own device to the same WiFi network as the ereader and visit its IP in a browser, server.py is what responds
#server.py serves pages, accepts file uploads, and manages the library through a web browser
#server.py should:
#show the library page when someone visits the IP in the browser
#accept new book uploads and return to library page
#delete existing books and return to library page
#be accesible from any device on the network

from flask import Flask, request, render_template, redirect, url_for
import os
from progress import get_completion, delete

app = Flask(__name__) #creates web server application
BOOKS_DIR = os.path.join(os.path.dirname(__file__), 'books') # builds path to book folder

#INDEX ROUTE
@app.route('/')#homepage route
def index():
    books = sorted([
        f for f in os.listdir(BOOKS_DIR)
        if f.endswith('.epub')
    ])#get epub books from books folder in alphabetical order
    library = [
        {'name': os.path.splitext(b)[0],
         'file': b,
         'pct':  int(get_completion(b) * 100)}
        for b in books
    ] #loop through each book and creates a dictionary
    return render_template('index.html', library=library) #loads templates/index.html and passes the library into it. The HTML can then loop through thte library to display each book

#UPLOAD ROUTE
@app.route('/upload', methods=['POST'])#only responds to post requests. POST =http browser request that browser sends when you submit a form with a file attached. this route only accpets form submissions.
def upload():
    f = request.files.get('book')#retrieves uploaded file from the form submission
    if f and f.filename.endswith('.epub'):
        f.save(os.path.join(BOOKS_DIR, f.filename))
    return redirect(url_for('index')) #saves file in books and redirects back to the homepage

#DELETE ROUTE
@app.route('/delete/<filename>')#variable filename route
def delete_book(filename):
    path = os.path.join(BOOKS_DIR, filename) 
    #check file exists before trying to delete
    if os.path.exists(path):
        os.remove(path)#deletes epub file from books folder
        delete(filename)#delete function from progress.py to remove the books progress record from the db
    return redirect(url_for('index')) #sends browser back to the homepage


#only runs when file is directly run. helpful for testing purposes
#host is 0.0.0.0 and not localhost so that flask accepts connections from any device on the network rather than just this computer
#server listens on port 500
#debug on so flask shows error page in browser and restarts itself whenever changes are saved to the file.Only on for development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)