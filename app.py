import os
import pathlib
import requests
from flask import Flask, session, abort, redirect, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

# Load .env
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

app = Flask("CollegeResellApp")
app.secret_key = os.getenv("FLASK_SECRET", "CodeSpecialist.com")

# Enable insecure transport for local testing
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# MongoDB config
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

if mongo.db is None:
    raise Exception("MongoDB connection failed. Check your MONGO_URI in .env")

# Google OAuth setup
GOOGLE_CLIENT_ID = "915436979052-kkgf8a90gdori705kusi0f5mf4urelot.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_uri="http://127.0.0.1:5000/callback"
)

# Protect routes
def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)
        return function(*args, **kwargs)
    wrapper.__name__ = function.__name__
    return wrapper

ADMIN_EMAIL = "akshatcc2@gmail.com"  # Replace with actual admin email

@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if session.get("state") != request.args.get("state"):
        abort(500)

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["email"] = id_info.get("email")
    session["is_admin"] = session["email"] == ADMIN_EMAIL

    # Save user in DB (upsert)
    mongo.db.users.update_one(
        {"google_id": session["google_id"]},
        {"$set": {
            "google_id": session["google_id"],
            "name": session["name"],
            "email": session["email"]
        }},
        upsert=True
    )

    return redirect("/protected_area")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/")
def index():
    return "Welcome to College Market! <a href='/login'><button>Login with Google</button></a>"

@app.route("/protected_area")
@login_is_required
def protected_area():
    admin_button = "<a href='/admin'><button>Admin Panel</button></a><br><br>" if session.get("is_admin") else ""
    return f"""
        <h2>Welcome, {session['name']}!</h2>
        <p>Email: {session['email']}</p>
        {admin_button}
        <a href='/buy'><button>Buy</button></a>
        <a href='/sell'><button>Sell</button></a>
        <br><br>
        <a href='/logout'><button>Logout</button></a>
    """

@app.route("/buy")
@login_is_required
def buy():
    products = mongo.db.products.find({"status": "available"})
    html = "<h2>Available Products</h2><ul>"
    for product in products:
        html += f"<li>{product.get('name', 'Unnamed')} - ₹{product.get('price', 'N/A')}<br>" \
                f"Category: {product.get('category', 'N/A')}<br>" \
                f"Seller: {product.get('seller_name', 'N/A')} | Phone: {product.get('phone', 'N/A')} | Email: {product.get('seller_email', 'N/A')}<br>"
        if "image_urls" in product:
            for url in product["image_urls"]:
                html += f"<img src='{url}' width='150'><br>"
        html += "</li><br><br>"
    html += "</ul><br><a href='/protected_area'><button>Back</button></a>"
    return html

@app.route("/sell", methods=["GET", "POST"])
@login_is_required
def sell():
    if request.method == "POST":
        category = request.form["category"]
        name = request.form["product_name"]
        description = request.form["description"]
        price = int(request.form["price"])
        seller_name = request.form["seller_name"]
        phone = request.form["phone"]

        images = request.files.getlist("image")
        image_urls = []

        for img in images:
            if img.filename != "":
                result = cloudinary.uploader.upload(img)
                image_urls.append(result['secure_url'])

        mongo.db.products.insert_one({
            "category": category,
            "name": name,
            "description": description,
            "price": price,
            "status": "pending",
            "seller_email": session["email"],
            "seller_name": seller_name,
            "phone": phone,
            "image_urls": image_urls
        })

        return f"""
            <h3>Product Submitted for Approval!</h3>
            <p>Name: {name} | Price: ₹{price}</p>
            <a href='/protected_area'><button>Back</button></a>
        """

    return '''
        <h2>Sell a Product</h2>
        <form method="post" enctype="multipart/form-data">
            <label>Category:</label>
            <select name="category">
                <option value="electronics">Electronics</option>
                <option value="groceries">Groceries</option>
                <option value="study stuff">Study Stuff</option>
                <option value="hostel stuff">Hostel Stuff</option>
                <option value="vehicles">Vehicles</option>
                <option value="others">Others</option>
            </select><br><br>

            <label>Product Name:</label>
            <input type="text" name="product_name" required><br><br>

            <label>Product Description:</label><br>
            <textarea name="description" rows="4" cols="50"></textarea><br><br>

            <label>Asking Price: ₹</label>
            <input type="number" name="price" required><br><br>

            <label>Product Images:</label>
            <input type="file" name="image" multiple><br><br>

            <label>Seller Name:</label>
            <input type="text" name="seller_name" required><br><br>

            <label>Phone Number:</label>
            <input type="tel" name="phone" required><br><br>

            <input type="submit" value="List Product">
        </form>
        <br>
        <a href='/protected_area'><button>Back</button></a>
    '''

@app.route("/admin", methods=["GET", "POST"])
@login_is_required
def admin():
    if not session.get("is_admin"):
        return abort(403)

    if request.method == "POST":
        action = request.form["action"]
        product_id = request.form["product_id"]
        from bson.objectid import ObjectId
        if action == "approve":
            mongo.db.products.update_one({"_id": ObjectId(product_id)}, {"$set": {"status": "available"}})
        elif action == "reject":
            mongo.db.products.delete_one({"_id": ObjectId(product_id)})

    pending_products = list(mongo.db.products.find({"status": "pending"}))
    html = "<h2>Pending Products</h2><ul>"
    for product in pending_products:
        html += f"""
        <li>
            <b>{product['name']}</b> - ₹{product['price']}<br>
            {product['description']}<br>
            Seller: {product['seller_name']} | {product['phone']}<br>
            <form method='post'>
                <input type='hidden' name='product_id' value='{product['_id']}'>
                <button name='action' value='approve'>Approve</button>
                <button name='action' value='reject'>Reject</button>
            </form>
        </li><br>
        """
    html += "</ul><br><a href='/protected_area'><button>Back</button></a>"
    return html

if __name__ == "__main__":
    app.run(debug=True)
