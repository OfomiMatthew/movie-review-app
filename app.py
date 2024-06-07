from flask import Flask, render_template, request, session, redirect, url_for,flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import requests

app = Flask(__name__)
app.secret_key = '41d43a2e1b4e3a7829a93b26af7c437bc632a36637e3d65b3b3e2ff1b4d2af94'
DATABASE = os.path.join(app.root_path, 'users.db')

# Function to enable foreign keys in SQLite
def enable_foreign_keys(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

# Setting up the database
def create_table():
    with sqlite3.connect(DATABASE) as conn:
        enable_foreign_keys(conn) 
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                movie_title TEXT,
                review TEXT,
                FOREIGN KEY(username) REFERENCES users(username)
            )
        ''')
create_table()

# Defining User model 
class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password
    
    def save(self):
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (self.username, self.password))
            conn.commit()

    @staticmethod
    def get_by_username(username):
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            return cursor.fetchone()

# Defining Review model
class Review:
    def __init__(self, id, username, movie_title, review):
        self.id = id
        self.username = username
        self.movie_title = movie_title
        self.review = review 

    def save(self):
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO reviews (username, movie_title, review) VALUES (?, ?, ?)",
                           (self.username, self.movie_title, self.review))
            conn.commit()

    @staticmethod
    def get_reviews_by_movie_title(movie_title):
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, review FROM reviews WHERE movie_title = ?", (movie_title,))
            return cursor.fetchall()

@app.route('/', methods=['GET', 'POST'])
def main():
    if request.method == 'POST':
        if 'username' in session:
            query = request.form.get('query')
            year = request.form.get('year')
            data = requests.get(f"https://www.omdbapi.com/?apikey=89553bad&s={query}&y={year}")
            movies = data.json()
            return render_template('home.html', movies=movies)
        else:
            return redirect(url_for('login'))
    else:
        data = requests.get("https://www.omdbapi.com/?apikey=89553bad&s=batman")
        movies = data.json()
        return render_template('home.html', movies=movies)

# view a moview page
@app.route('/movie/<title>', methods=['GET', 'POST'])
def single_movie(title):
    if request.method == 'POST':
        if 'username' in session:
            review_text = request.form.get('review')
            review = Review(None, session['username'], title, review_text)
            review.save()
            return redirect(url_for('single_movie', title=title))
        else:
            return redirect(url_for('login'))
    
    data = requests.get(f"https://www.omdbapi.com/?apikey=89553bad&t={title}")
    movie = data.json()
    reviews_data = Review.get_reviews_by_movie_title(title)
    reviews = [{'id': r[0], 'username': r[1], 'review': r[2]} for r in reviews_data]
    return render_template('movie.html', movie=movie, reviews=reviews)

# Add reviews
@app.route('/add_review/<title>', methods=['POST'])
def add_review(title):
    if 'username' in session:
        review_text = request.form['review']
        new_review = Review(None, session['username'], title, review_text)
        new_review.save()
        return redirect(url_for('single_movie', title=title))
    else:
        return redirect(url_for('login'))


# Editing Reviews
@app.route('/edit_review/<int:review_id>', methods=['GET', 'POST'])
def edit_review(review_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_review_text = request.form['review']
        movie_title = request.form['movie_title']
        with sqlite3.connect(DATABASE) as conn:
            enable_foreign_keys(conn)
            cursor = conn.cursor()
            cursor.execute("UPDATE reviews SET review = ? WHERE id = ? AND username = ?",
                           (new_review_text, review_id, session['username']))
            conn.commit()
        return redirect(url_for('single_movie', title=movie_title))
    
    with sqlite3.connect(DATABASE) as conn:
        enable_foreign_keys(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT review, movie_title FROM reviews WHERE id = ? AND username = ?",
                       (review_id, session['username']))
        review_data = cursor.fetchone()
        if review_data is None:
            return "Review not found or you do not have permission to edit this review."
    
    review = {'review': review_data[0], 'movie_title': review_data[1]}
    return render_template('edit_review.html', review=review, review_id=review_id)


# Deleting Reviews
@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect(DATABASE) as conn:
        enable_foreign_keys(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = ? AND username = ?",
                       (review_id, session['username']))
        conn.commit()
    return redirect(url_for('single_movie', title=request.form['movie_title']))

# sign up users
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.get_by_username(username)
        if existing_user:
            return "Username already exists!"
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username, hashed_password)
            new_user.save()
            return redirect(url_for('login'))
    return render_template('signup.html')

# login users
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.get_by_username(username)
        if user and check_password_hash(user[2], password): # hashpassword column user[2]
            session['username'] = username
            return redirect(url_for('main'))
        else:
            return render_template('invalid.html')
    return render_template('login.html')

# user logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('main'))

# about page
@app.route('/about')
def about():
    return render_template('about.html')


# favorite movie page
@app.route('/favorite')
def favorite_list():
    favorite_list = session.get('favorite', [])
    if not favorite_list:
        if 'username' in session:  # Check if the user is logged in
            flash('The favorite list is empty! Add a new favorite movie.', 'warning')
        else:
            flash('The favorite list is empty! Signup & Login to add a new favorite movie.', 'danger')
        
        return redirect(url_for('main'))
    else:
        return render_template('favorite.html', favorite_list=favorite_list)


# adding favorite movie   
@app.route('/add_favorite/<title>')
def add_to_favorite(title):
    favorite_list = {}
    if "favorite" in session:
        favorite_list = session.get('favorite')
    else:
        session["favorite"] = {}
    favorite_list[title] = title
    session['favorite'] = favorite_list
    flash(f'{title} has been added to your favorites!', 'success')
    return redirect(url_for('main'))


# remove favorite movie from favorite page
@app.route('/remove_from_list/<title>')
def remove_from_list(title):
    favorite_list = session.get('favorite')
    favorite_list.pop(title,None)
    session['favorite'] = favorite_list
    flash(f'{title} has been removed from your favorites!', 'success')
    return redirect(url_for('favorite_list'))



if __name__ == '__main__':
    app.run(debug=True)

















          




















   





