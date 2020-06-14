import os
import requests

from flask import Flask, session, render_template, redirect, jsonify
from flask import request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from helpers import apology,login_required

from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

if not os.getenv("GOODREADS_API_KEY"):
    raise RuntimeError("Goodreads api key is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET","POST"])
def login():
    # Clear all users 
    session.clear()
    # load login form if method is get
    if request.method == "GET":
        return render_template("login.html")
    # if method is post
    else:
        # Ensure username and password are not empty
        if not request.form.get("username"):
            return apology("Username cannot be empty", 403)
        if not request.form.get("password"):
            return apology("Password cannot be empty", 403)
        # Query the database 
        rows = db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")}).fetchall()
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], request.form.get("password")):
            return apology("Invalid username or password", 403)

        # Remember which user has logged in
        session["user_name"] = rows[0]["username"]

        # Redirect user to search page
        return redirect("/search")
        


@app.route("/register" ,methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        
        if not request.form.get("name"):
            return apology("Must provide name", 403)

        elif not request.form.get("username"):
            return apology("Must provide username", 403)

        elif not request.form.get("password"):
            return apology("Password cannot be empty", 403)

            

        elif request.form.get("password") != request.form.get("c_password"):
            return apology("Passwords do not match", 403)

        
        rows = db.execute("select * from users").fetchall()
        for row in rows:
            if request.form.get("username") ==  row["username"]:
                return apology("Username already exists", 403)
                
        hash_p = generate_password_hash(request.form.get('password'))
        db.execute("INSERT INTO users(username,name,password) VALUES (:username, :name, :password)",
                    {"username": request.form.get('username'), "name": request.form.get('name'), "password": hash_p} )
        db.commit()
        return render_template("login.html")




@app.route("/search" ,methods=["GET", "POST"])
@login_required
def search():
    if request.method == "GET":
        return render_template("search.html")
    else:
        search = request.form.get("search")
        # Ensure search is not empty
        if search ==  "":
            return apology("Please enter a book name", 403)
        # Query books DB 
        search = "%" + search + "%"
        rows = db.execute("SELECT * FROM books WHERE isbn LIKE :search OR title LIKE :search OR author LIKE :search",
                            {"search":search}).fetchall()
        return render_template("book_list.html", rows=rows)



@app.route("/reviews/<isbn>", methods=["GET","POST"])
@login_required
def reviews(isbn):
    rows = db.execute("SELECT * FROM books where isbn=:isbn",{"isbn":isbn}).fetchall()
    if request.method == "GET":
        # Make API Request to GoodReads for rating and query  database for book info
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_API_KEY"), "isbns": isbn})
        review = res.json()
        # return review["books"][0]["average_rating"]
        user_review = db.execute("SELECT * FROM reviews where book_title=:book_title",{"book_title":rows[0]['title']})
        return render_template("reviews.html",review=review, rows=rows, user_review = user_review)
    else:
        user_input = request.form.get("user_input")
        if not user_input:
            return apology("Review cannot be blank", 403)
        rating = request.form.get("rating")
        # Check if user has already submitted  review
        review_count = db.execute("SELECT * FROM reviews WHERE book_title=:title",{"title":rows[0]['title']}).fetchall()
        if len(review_count) != 0:
            if session["user_name"] == review_count[0]["username"]:
                return apology("You can submit only 1 review", 403)
        else:
            # Insert review in DB
            db.execute("INSERT INTO reviews VALUES(:username,:book_title,:review,:rating)",
                        {"username":session['user_name'],"book_title":rows[0]['title'],"review":user_input,
                        "review":user_input,"rating":rating})
            db.commit()
             # Redirect to reviews pages
            return redirect("/reviews/"+isbn)
            
            
@app.route("/api/<isbn>", methods=["GET","POST"])  
def api(isbn):
    if request.method == "GET":
        api_json = {}
        # Query books DB and store book title in variable 
        book_info = db.execute("SELECT * FROM books WHERE isbn=:isbn",{"isbn":isbn}).fetchall()
        if len(book_info) == 0:
            return jsonify({"Error":"Invalid Book ISBN"}), 404
        book_title = book_info[0]['title']
        # Query review DB to get average rating and no. of reviews 
        review_info = db.execute("SELECT COUNT(username) as rating_count,AVG(rating) average_rating FROM reviews where book_title=:title",{"title":book_title}).fetchall()
        # if there are no reviews 
        if review_info[0]["rating_count"] == 0:
            # initialize dictonary 
            api_json = {
                "title": book_title,
                "author": book_info[0]['author'],
                "year": book_info[0]['year'],
                "isbn": book_info[0]['isbn'],
                "review_count": 0,
                "average_score": 0
            }
        else :
            #initialize dictonary
            api_json = {
                "title": book_title,
                "author": book_info[0]['author'],
                "year": book_info[0]['year'],
                "isbn": book_info[0]['isbn'],
                "review_count": review_info[0]["rating_count"],
                "average_score": float('%.2f'%(review_info[0]['average_rating']))
            }
        return jsonify(api_json)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")
                

