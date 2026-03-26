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
    """creates the database and table if they dont exist yet. safe to call every time the app starts."""
    conn = sqlite3.connect(DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            book        TEXT PRIMARY KEY,
            page        INTEGER DEFAULT 0,
            total_pages INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

def save(book,page,total_pages):
    """saves current page and total pages for a book"""
    conn = sqlite3.connect(DB)
    conn.execute(
        'INSERT OR REPLACE INTO progress VALUES (?,?,?)'
        (book,page,total_pages)
    )
    conn.commit()
    conn.close()

def load(book):
    """returns(page,total_pages). returns (0,1) if book has never been opened"""
    conn=sqlite3.connect(DB)
    row=conn.execute(
        'SELECT page, total_pages FROM progress WHERE book=?',
        (book,)
    ).fetchone()
    conn.close()
    return row if row else (0,1)

def get_completion(book):
    """returns float 0.0 to 1.0 representing exact completion"""
    page,total = load(book)
    if total ==0:
        return 0.0
    return round(page/total, 4)

def delete(book):
    """remove a books progress when its deleted from library"""
    conn = sqlite3.connect(DB)
    conn.execute('DELETE FROM progress WHERE book=?',(book,))
    conn.commit()
    conn.close()
    