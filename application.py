from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import sys


from helpers import *

# configure application
app = Flask(__name__)
app.config['SECRET_KEY']='thisismysecret'

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
# path is to the database in c:\users\kendsr\desktop\working\cs50\finance\finance.db
db = SQL("sqlite:///finance//finance.db")

@app.route("/")
@login_required
def index():
    # Get current cash ballance fro current user
    cash = db.execute("select cash from users where id = :id", id=session["user_id"])
    cashBal = cash[0]['cash']
    portTotal = cash[0]['cash']
    # Get stock portfolio for user and display with totals
    data=[]
    portfolio = db.execute('select * from portfolio where owner_id = :owner_id order by symbol', owner_id=session['user_id'])
    for record in portfolio:
        share = lookup(record['symbol'])
        symbol = share['symbol']
        name = share['name']
        shares = record['shares']
        price = share['price']
        shareTotal = shares * price
        portTotal += shareTotal
        price = usd(price)
        total = usd(shareTotal)
        # List Data values
        lst=[symbol, name, shares, price, total]
        # List Key names
        keys=['Symbol','Name','Shares','Price','Total']
        # Build list of dictionaries
        data.append(dict(zip(keys, lst)))
    cashBal = usd(cashBal)
    total = usd(portTotal)
    return render_template('index.html', cashBal=cashBal, total=total, data=data)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == 'GET':
        # User provides stock sybol and # of shares tp purchase
        return render_template("buy.html")
    if request.method == "POST":
        current_user = int(session["user_id"])
        # Validate user input
        if not request.form['symbol'] or not request.form['shares'] or int(request.form['shares']) < 0:
            flash("You must povide a stock symbol and/or number of shares as a positive integer) to purchase")
            return redirect(url_for("index"))
        # Get current cash balance for user
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=current_user)
        # Lookup stock symbol to get current price per share
        stock = lookup(request.form['symbol'])
        if stock:
            numShares = int(request.form['shares'])
            # Compute total purchase price
            purchase = numShares * stock['price']
            # Verify there is enough cash in account to fund transaction
            if purchase > cash[0]['cash']:
                flash("You do not have enough cash to fund this transction." + usd(purchase) + " is needed. Current balance is " + usd(cash[0]['cash']))
                return redirect(url_for("index"))
            else:
                # Calculate new available cash balance
                cashBal = cash[0]['cash'] - purchase
                # Add transaction to trans table
                db.execute("insert into trans (tran_type, owner_id, symbol, shares, price) \
                    values(:tran_type, :owner_id, :symbol, :shares, :price)", \
                    tran_type='buy', owner_id=current_user, symbol=stock['symbol'], shares=numShares, price=purchase)
                # Update user cash account balance
                db.execute("update users set cash = :cashBal where id = :id", cashBal=cashBal, id=current_user)
                # Add/update user stock portfolio
                #   If user has stock in portfolio update the shares owned 
                current_shares = db.execute("select id, shares from portfolio where owner_id = :id and symbol = :symbol", \
                    id=current_user, symbol=stock['symbol'])
                if current_shares:
                    # Update stock portfolio share count
                    newShares = current_shares[0]['shares'] + numShares
                    db.execute("update portfolio set shares = :newShares where id = :id", newShares=newShares, id=current_shares[0]['id'])
                else:
                    # Add the stock to the portfolio
                    db.execute("insert into portfolio (owner_id, symbol, shares) values(:owner_id, :symbol, :shares)", owner_id=current_user, symbol=stock['symbol'], shares=numShares)
        else:
            flash("Stock Symbol not found")
            return render_template('apology.html')
        flash(str(numShares) + " shares of " + stock['symbol'] + " for a total cost of " + usd(purchase) \
            + " at " + usd(stock['price']) + " per share.")
        flash("Your current cash balance is " + usd(cashBal))
        return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    data = []
    log = db.execute('select * from trans where owner_id = :owner_id', owner_id=session['user_id'])
    for row in log:
        tran = row['tran_type']
        symbol = row['symbol']
        price = usd(row['price'])
        shares = row['shares']
        date = row['date']
        # List Data values
        lst=[tran, symbol, price, shares, date]
        # List Key names
        keys=['Transaction', 'Symbol', 'Price', 'Shares', 'Date']
        # Build list of dictionaries
        data.append(dict(zip(keys, lst)))
    return render_template('history.html', data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Username not provided")
            return render_template("apology.html")
            # return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Password not provided")
            return render_template("apology.html")
            # return apology("must provide password")

        # query database for username
        
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        flash("Welcome " + rows[0]["username"] + ". you have been logged in")
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to index form
    flash("You have been logged out. -- Log back in to continue")
    return redirect(url_for("index"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        # Validate User input
        if request.form.get("symbol") == "" or request.form.get("symbol").startswith("^") or "," in request.form.get("symbol"):
            return apology("Stock Symbol can't be empty, start with ^ or contain comma")
        # lookup stock symbol
        data = lookup(request.form.get("symbol"))
        if not data:
            flash(request.form.get("symbol") + " not found")
            return render_template("apology.html")
        # show quote
        return render_template("quoted.html", data=data)
    else:
        return apology("Method not supported")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        # Validate user input
        if request.form.get("username") == "" or request.form.get("password") == "":
            return apology("Username and/or Password must be provided")
        if request.form.get("confirm") == "":
            return apology("Please confirm the Passowrd entered")
        if request.form.get("password") != request.form.get("confirm"):
            return apology("Confirmed Password not the same as Password entered")
        # check for user already exists
        rows = db.execute("select 1 from users where username=:username", \
         username=request.form.get("username"))
        if len(rows) != 0:
            return apology("Username already in use. Please choose another.")
        # Encrypt password
        hash = pwd_context.hash(request.form.get("password"))
        # Insert user into table
        rows = db.execute("insert into users (username, hash) values(:username, :hash)", \
         username=request.form.get("username"), hash=hash)
        # Log user in
        session["user_id"] = rows
        flash("Welcome " + request.form.get("username") + ". You have been registered")
        return redirect(url_for("index"))
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "GET":
        return render_template("sell.html")
    if request.method == "POST":
        if not request.form['symbol']:
            flash("Stock Symbol must be provided")
            return redirecturl_for("index"))
        # Get current cash balance for user
        cash = db.execute('select cash from users where id=:id', id=session['user_id'])
        cashBal = cash[0]['cash']
        # Get Stock to be sold from user portfolio
        portfolio = db.execute('select * from portfolio where owner_id = :owner_id and symbol = :symbol', \
            owner_id=session['user_id'], symbol=request.form['symbol'].upper())
        if not portfolio:
            flash(request.form['symbol'] + " is not in portfolio for this user")
            return redirect(url_for("index"))
        # lookup symbol to get current market price
        data = lookup(request.form['symbol'])
        # Calculate sale price
        market_price = data['price']
        shares = portfolio[0]['shares']
        proceeds = shares * market_price
        # Remove stock from portfolio
        db.execute('delete from portfolio where id = :id', id=portfolio[0]['id'])
        # Record sell transactio in log table
        db.execute("insert into trans (tran_type, owner_id, symbol, shares, price) \
                    values(:tran_type, :owner_id, :symbol, :shares, :price)", \
                    tran_type='sell', owner_id=session['user_id'], symbol=data['symbol'], shares=shares, price=proceeds)
        cashBal += proceeds
        # Update user cash adding in sale proceeds
        db.execute('update users set cash=:cashBal where id=:id', cashBal=cashBal, id=session['user_id'])
        
        flash(str(shares) + " of " + data['symbol'] + " were sold at " + usd(market_price) + " per share. Total proceeds of sale is "+ usd(proceeds))
        return redirect(url_for("index"))

if __name__=='__main__':
    # app.run(host='0.0.0.0') # allow remote access
    app.run(debug=True)