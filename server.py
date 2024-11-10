from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
import sqlite3

app = Flask(__name__)
socketio = SocketIO(app)

conn = sqlite3.connect('reviews.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS reviews (
    reviewer_id TEXT,
    reviewee_id TEXT,
    rating INTEGER,
    review TEXT,
    guild_id TEXT,
    guild_name TEXT,
    FOREIGN KEY (reviewer_id) REFERENCES users (user_id),
    FOREIGN KEY (reviewee_id) REFERENCES users (user_id)
)
''')
conn.commit()

def add_user(user_id, username):
    c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

add_user("User123", "Alice")
add_user("User456", "Bob")

def fetch_reviews(guild_name=None):
    query = '''
        SELECT u1.username AS reviewer, u2.username AS reviewee, r.rating, r.review 
        FROM reviews r
        JOIN users u1 ON r.reviewer_id = u1.user_id
        JOIN users u2 ON r.reviewee_id = u2.user_id
    '''
    if guild_name:
        query += ' WHERE r.guild_name = ?'
        c.execute(query, (guild_name,))
    else:
        c.execute(query)
    
    rows = c.fetchall()
    return [{"reviewer": row[0], "reviewee": row[1], "rating": row[2], "review": row[3]} for row in rows]



@app.route('/reviews', methods=['GET'])
def get_reviews():
    guild_name = request.args.get('guild')
    user_id = request.args.get('userId')
    
    if user_id:
        return jsonify(fetch_reviews_by_user(user_id))
    
    return jsonify(fetch_reviews(guild_name))

def fetch_reviews_by_user(user_id):
    query = '''
        SELECT u1.user_id AS reviewer_id, u2.user_id AS reviewee_id, r.rating, r.review, 
               u1.username AS reviewer_name, u2.username AS reviewee_name -- Fetch usernames
        FROM reviews r
        JOIN users u1 ON r.reviewer_id = u1.user_id
        JOIN users u2 ON r.reviewee_id = u2.user_id
        WHERE u1.user_id = ? OR u2.user_id = ?
    '''
    c.execute(query, (user_id, user_id))
    
    rows = c.fetchall()
    return [{
        "reviewer_id": row[0],
        "reviewee_id": row[1],
        "rating": row[2],
        "review": row[3],
        "reviewer": row[4], 
        "reviewee": row[5],  
    } for row in rows]

@app.route('/guilds', methods=['GET'])
def get_guilds():
    c.execute("SELECT DISTINCT guild_name FROM reviews")
    guilds = [row[0] for row in c.fetchall()]
    return jsonify(guilds)

@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

def broadcast_new_review(review):
    socketio.emit('new_review', review)

@app.route('/add_review', methods=['POST'])
def add_review():
    data = request.json
    reviewer_id = data['reviewer_id']
    reviewee_id = data['reviewee_id']
    rating = data['rating']
    review = data['review']
    guild_id = data['guild_id']
    guild_name = data['guild_name']

    c.execute('INSERT INTO reviews (reviewer_id, reviewee_id, rating, review, guild_id, guild_name) VALUES (?, ?, ?, ?, ?, ?)',
              (reviewer_id, reviewee_id, rating, review, guild_id, guild_name))
    conn.commit()

    review_with_usernames = {
        "reviewer": reviewer_id,  
        "reviewee": reviewee_id,  
        "rating": rating,
        "review": review
    }
    broadcast_new_review(review_with_usernames)

    return jsonify({"status": "success", "message": "Review added successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
