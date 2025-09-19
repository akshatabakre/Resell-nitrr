import os
import pathlib
import requests
from flask import Flask, session, abort, redirect, request, render_template, flash
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from bson.objectid import ObjectId

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
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_uri="https://resell-nitrr-67.onrender.com/callback"
)

def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)
        return function(*args, **kwargs)
    wrapper.__name__ = function.__name__
    return wrapper

ADMIN_EMAIL = os.getenv("ADMIN")

@app.route("/")
def index():
    return render_template("index.html")

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
@app.route('/google6d6e61f3e6df070.html')
def google_verification():
    """Serves the Google verification file."""
    return send_from_directory('.', 'google6d6e61f3e6df070.html')

@app.route("/protected_area")
@login_is_required
def protected_area():
    return render_template("protected_area.html", name=session['name'], email=session['email'], is_admin=session.get("is_admin"))

@app.route("/buy", methods=["GET", "POST"])
@login_is_required
def buy():
    if request.method == "POST":
        buyer_name = request.form.get("buyer_name")
        product_name = request.form.get("product_name", "")
        description = request.form.get("description", "")
        phone = request.form.get("contact", "")

        if not product_name or not phone:
            return "Missing required fields", 400

        mongo.db.wanted.insert_one({
            "buyer_name":buyer_name,
            "name": product_name,
            "description": description,
            "contact": phone,
            "email": session["email"],
            "status": "pending"
        })

        return render_template("wanted_submitted.html")

    # GET method — handle search and filtering
    search_query = request.args.get("search", "").strip().lower()
    category_filter = request.args.get("category", "").strip()

    query = {"status": "available"}

    if search_query:
        query["name"] = {"$regex": search_query, "$options": "i"}  # case-insensitive

    if category_filter:
        query["category"] = category_filter

    products = list(mongo.db.products.find(query))
    categories = mongo.db.products.distinct("category")  # for dropdown

    return render_template("buy.html", products=products, categories=categories, selected_category=category_filter, search_query=search_query)


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

        return render_template("product_submitted.html")

    return render_template("sell.html")

@app.route("/admin", methods=["GET", "POST"])
@login_is_required
def admin():
    if not session.get("is_admin"):
        return abort(403)

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

    return render_template("admin.html", pending_products=pending_products, pending_wanted=pending_wanted)

@app.route("/wanted_list")
@login_is_required
def wanted_list():
    wanted_items = list(mongo.db.wanted.find({"status": "approved"}))
    return render_template("wanted_list.html", wanted_items=wanted_items)

# @app.route("/my_listings")
# @login_is_required
# def my_listings():
#     products = list(mongo.db.products.find({
#         "seller_email": session["email"],
#         "status": {"$in": ["available", "pending"]}
#     }))
#     return render_template("my_listings.html", products=products)


@app.route("/my_listings")
@login_is_required
def my_listings():
    products = list(mongo.db.products.find({
        "seller_email": session["email"],
        "status": {"$in": ["available", "pending"]}
    }))
    wanted_items = list(mongo.db.wanted.find({
        "email": session["email"],
        "status": {"$in": ["approved", "pending"]}
    }))
    return render_template("my_listings.html", products=products, wanted_items=wanted_items)


@app.route("/my_listings/<product_id>", methods=["GET", "POST"])
@login_is_required
def edit_listing(product_id):
    product = mongo.db.products.find_one({"_id": ObjectId(product_id), "seller_email": session["email"]})
    if not product:
        abort(404)

    if request.method == "POST":
        updated_data = {
            "category": request.form["category"],
            "name": request.form["product_name"],
            "description": request.form["description"],
            "price": int(request.form["price"]),
            "seller_name": request.form["seller_name"],
            "phone": request.form["phone"],
            "status": "pending"  # 🔥 Important: this makes admin reapprove the listing
        }

        # Handle image updates
        current_images = product.get("image_urls", [])
        delete_images = request.form.getlist("delete_images")
        updated_images = [img for img in current_images if img not in delete_images]

        new_images = request.files.getlist("new_images")
        for img in new_images:
            if img and img.filename != "":
                result = cloudinary.uploader.upload(img)
                updated_images.append(result['secure_url'])

        updated_data["image_urls"] = updated_images

        mongo.db.products.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        flash("Listing updated and sent for admin approval.")
        return redirect("/my_listings")

    return render_template("edit_listing.html", product=product)


@app.route("/mark_sold/<product_id>", methods=["POST"])
@login_is_required
def mark_sold(product_id):
    product = mongo.db.products.find_one({"_id": ObjectId(product_id), "seller_email": session["email"]})
    if not product:
        abort(404)

    mongo.db.products.update_one({"_id": ObjectId(product_id)}, {"$set": {"status": "sold"}})
    flash("Product marked as sold.")
    return redirect("/my_listings")

@app.route("/product/<product_id>")
@login_is_required
def product_detail(product_id):
    product = mongo.db.products.find_one({"_id": ObjectId(product_id), "status": "available"})
    if not product:
        abort(404)
    return render_template("product_detail.html", product=product)

@app.route("/edit_wanted/<wanted_id>", methods=["GET", "POST"])
@login_is_required
def edit_wanted(wanted_id):
    wanted = mongo.db.wanted.find_one({"_id": ObjectId(wanted_id), "email": session["email"]})
    if not wanted:
        abort(404)

    if request.method == "POST":
        if request.form.get("mark_fulfilled") == "yes":
            mongo.db.wanted.delete_one({"_id": ObjectId(wanted_id)})
            flash("Wanted item marked as fulfilled and removed.")
            return redirect("/my_listings")

        updated_data = {
            "name": request.form["name"],
            "product_name": request.form["product_name"],
            "description": request.form["description"],
            "contact": request.form["contact"],
            "status": "pending"  # Reapproval
        }

        mongo.db.wanted.update_one({"_id": ObjectId(wanted_id)}, {"$set": updated_data})
        flash("Wanted item updated and sent for admin approval.")
        return redirect("/my_listings")

    return render_template("edit_wanted.html", wanted=wanted)


if __name__ == "__main__":
    app.run(debug=True)
