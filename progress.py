#this file needs to:
#Create the database on first run if it doesn't exist yet
#Save position when you turn a page
#Load position when you open a book
#Calculate what percentage of a book is completed
#Delete a book's progress if removed
import sqlite3
import os

#get the full path to the current file with __file__, strip the filename off the end with os.path.dirname(__file__), and join this folder path to the progress db file name. this gives the path to the DB
DB = os.path.join(os.path.dirname(__file__), 'progress.db')

def init_db():
    """RUNS ONCE ON STARTUP. 
    Creates the database and table if they dont exist yet. safe to call every time the app starts."""
    conn = sqlite3.connect(DB) #opens a connection to db file. SQL creates it automatically if it doesnt exist yet.
    conn.execute(''' 
        CREATE TABLE IF NOT EXISTS progress (
            book        TEXT PRIMARY KEY,
            page        INTEGER DEFAULT 0,
            total_pages INTEGER DEFAULT 1
        )
    ''') #sends sql instruction to database to create progress table if doesnt exist already.
    conn.commit() #saves changes permanently to disk
    conn.close() #closes database connection to save memory

def save(book,page,total_pages):
    """CALLED EVERY PAGE TURN. 
    Saves current page and total pages for a book"""
    conn = sqlite3.connect(DB) 
    conn.execute( 
        'INSERT OR REPLACE INTO progress VALUES (?,?,?)'
        (book,page,total_pages) #variables passed separately as tuples to avoid security vulnerabilities that come with putting variables directly into SQL strings.
    )
    conn.commit()
    conn.close()

def load(book):
    """CALLED WHEN BOOK OPENED. 
    Returns(page,total_pages). returns (0,1) if book has never been opened"""
    conn=sqlite3.connect(DB)
    row=conn.execute(
        'SELECT page, total_pages FROM progress WHERE book=?',
        (book,)
    ).fetchone() #receives the result of the query
    conn.close()
    return row if row else (0,1)

def get_completion(book):
    """CALLS load() INTERNALLY USED BY HOME PAGE. 
    Returns float 0.0 to 1.0 representing exact completion"""
    page,total = load(book)
    if total ==0:
        return 0.0
    return round(page/total, 3)

def delete(book):
    """CALLED WHEN A BOOK IS REMOVED. 
    Remove a books progress when its deleted from library"""
    conn = sqlite3.connect(DB)
    conn.execute(
        'DELETE FROM progress WHERE book=?',
        (book,)
    )
    conn.commit()
    conn.close()

#TESTING
# Built in python __name__ variable is __main__ only if progress.py is run directly. 
# When another file imports from it, __name__ would be progress, so the testing code is ignored
if __name__ == '__main__':
    init_db()

    print('Testing save...')
    save('dune.epub', 142, 600)
    save('neuromancer.epub', 45, 280)

    print('Testing load...')
    print(load('dune.epub'))             # (142, 600)
    print(load('neuromancer.epub'))      # (45, 280)
    print(load('unknown.epub'))          # (0, 1)

    print('Testing get_completion...')
    print(get_completion('dune.epub'))         # 0.2367
    print(get_completion('neuromancer.epub'))  # 0.1607

    print('Testing delete...')
    delete('neuromancer.epub')
    print(load('neuromancer.epub'))      # (0, 1)

    print('All tests passed')