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

def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)
        return function(*args, **kwargs)
    wrapper.__name__ = function.__name__
    return wrapper

ADMIN_EMAIL = "akshatcc2@gmail.com"

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
        <a href='/wanted_list'><button>View Wanted Items</button></a>
        <br><br>
        <a href='/logout'><button>Logout</button></a>
    """

@app.route("/buy", methods=["GET", "POST"])
@login_is_required
def buy():
    if request.method == "POST":
        product_name = request.form["wanted_name"]
        description = request.form["wanted_desc"]
        phone = request.form["contact"]
        mongo.db.wanted.insert_one({
            "name": product_name,
            "description": description,
            "contact": phone,
            "email": session["email"],
            "buyer_name": session["name"],
            "status": "pending"
        })
        return "<p>Wanted item submitted for approval!</p><a href='/buy'><button>Back</button></a>"

    products = mongo.db.products.find({"status": "available"})
    html = "<h2>Available Products</h2><ul>"
    for product in products:
        html += f"<li>{product.get('name')} - ₹{product.get('price')}<br>" \
                f"Category: {product.get('category')}<br>" \
                f"Seller: {product.get('seller_name')} | Phone: {product.get('phone')} | Email: {product.get('seller_email')}<br>"
        if "image_urls" in product:
            for url in product["image_urls"]:
                html += f"<img src='{url}' width='150'><br>"
        html += "</li><br><br>"
    html += "</ul><hr>"

    html += """
    <h3>Can't find the item? List the item you want:</h3>
    <form method='POST'>
        <label>Item Name:</label><br>
        <input type='text' name='wanted_name' required><br><br>
        <label>Description:</label><br>
        <textarea name='wanted_desc' rows='3' cols='50'></textarea><br><br>
        <label>Contact Number:</label><br>
        <input type='text' name='contact' required><br><br>
        <input type='submit' value='Submit Wanted Item'>
    </form>
    <br><a href='/protected_area'><button>Back</button></a>
    """
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

        return f"<h3>Product Submitted for Approval!</h3><a href='/protected_area'><button>Back</button></a>"

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
            <label>Product Name:</label><input type="text" name="product_name" required><br><br>
            <label>Product Description:</label><textarea name="description" rows="4" cols="50"></textarea><br><br>
            <label>Asking Price: ₹</label><input type="number" name="price" required><br><br>
            <label>Product Images:</label><input type="file" name="image" multiple><br><br>
            <label>Seller Name:</label><input type="text" name="seller_name" required><br><br>
            <label>Phone Number:</label><input type="tel" name="phone" required><br><br>
            <input type="submit" value="List Product">
        </form>
        <br><a href='/protected_area'><button>Back</button></a>
    '''

@app.route("/admin", methods=["GET", "POST"])
@login_is_required
def admin():
    if not session.get("is_admin"):
        return abort(403)

    from bson.objectid import ObjectId

    if request.method == "POST":
        action = request.form["action"]
        item_type = request.form["type"]
        item_id = request.form["item_id"]

        if item_type == "product":
            if action == "approve":
                mongo.db.products.update_one({"_id": ObjectId(item_id)}, {"$set": {"status": "available"}})
            elif action == "reject":
                mongo.db.products.delete_one({"_id": ObjectId(item_id)})
        elif item_type == "wanted":
            if action == "approve":
                mongo.db.wanted.update_one({"_id": ObjectId(item_id)}, {"$set": {"status": "approved"}})
            elif action == "reject":
                mongo.db.wanted.delete_one({"_id": ObjectId(item_id)})

    pending_products = list(mongo.db.products.find({"status": "pending"}))
    pending_wanted = list(mongo.db.wanted.find({"status": "pending"}))

    html = "<h2>Pending Products</h2><ul>"
    for product in pending_products:
        html += f"<li><b>{product['name']}</b> - ₹{product['price']}<br>{product['description']}<br>" \
                f"Seller: {product['seller_name']} | {product['phone']}<br>"
        for url in product.get("image_urls", []):
            html += f"<img src='{url}' width='150'><br>"
        html += f"""
            <form method='post'>
                <input type='hidden' name='item_id' value='{product['_id']}'>
                <input type='hidden' name='type' value='product'>
                <button name='action' value='approve'>Approve</button>
                <button name='action' value='reject'>Reject</button>
            </form></li><br>
        """
    html += "</ul><hr><h2>Pending Wanted Items</h2><ul>"
    for item in pending_wanted:
        html += f"<li><b>{item['name']}</b><br>{item['description']}<br>Contact: {item['contact']}<br>Buyer: {item.get('buyer_name', 'Unknown')}<br>" \
                f"<form method='post'>" \
                f"<input type='hidden' name='item_id' value='{item['_id']}'>" \
                f"<input type='hidden' name='type' value='wanted'>" \
                f"<button name='action' value='approve'>Approve</button>" \
                f"<button name='action' value='reject'>Reject</button>" \
                f"</form></li><br>"
    html += "</ul><br><a href='/protected_area'><button>Back</button></a>"
    return html

@app.route("/wanted_list")
@login_is_required
def wanted_list():
    wanted_items = mongo.db.wanted.find({"status": "approved"})
    html = "<h2>Wanted Products (Approved)</h2><ul>"
    for item in wanted_items:
        html += f"<li><b>{item['name']}</b><br>{item['description']}<br>Contact: {item['contact']}<br>Buyer: {item.get('buyer_name', 'Unknown')}</li><br>"
    html += "</ul><br><a href='/protected_area'><button>Back</button></a>"
    return html

if __name__ == "__main__":
    app.run(debug=True)
