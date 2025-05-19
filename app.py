import os
import pathlib
import requests
from flask import Flask, session, abort, redirect, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

app = Flask("Google Login App")
app.secret_key = "CodeSpecialist.com"

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "915436979052-kkgf8a90gdori705kusi0f5mf4urelot.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)
        else:
            return function()
    wrapper.__name__ = function.__name__
    return wrapper


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
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
    return redirect("/protected_area")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/")
def index():
    return "Hello World <a href='/login'><button>Login with Google</button></a>"


@app.route("/protected_area")
@login_is_required
def protected_area():
    return f"""
        <h2>Welcome, {session['name']}!</h2>
        <p>Email: {session['email']}</p>
        <a href='/buy'><button>Buy</button></a>
        <a href='/sell'><button>Sell</button></a>
        <br><br>
        <a href='/logout'><button>Logout</button></a>
    """


@app.route("/buy")
@login_is_required
def buy():
    products = [
        {"name": "Calculator", "price": "₹300"},
        {"name": "Textbook: Data Structures", "price": "₹450"},
        {"name": "Headphones", "price": "₹700"},
    ]
    html = "<h2>Buy Products</h2><ul>"
    for product in products:
        html += f"<li>{product['name']} - {product['price']}</li>"
    html += "</ul><br><a href='/protected_area'><button>Back</button></a>"
    return html


@app.route("/sell", methods=["GET", "POST"])
@login_is_required
def sell():
    if request.method == "POST":
        name = request.form["product_name"]
        price = request.form["price"]
        return f"""
            <h3>Product Listed!</h3>
            <p>Product: {name}<br>Price: ₹{price}</p>
            <a href='/protected_area'><button>Back</button></a>
        """

    return '''
        <h2>Sell a Product</h2>
        <form method="post">
            Product Name: <input type="text" name="product_name"><br><br>
            Price: ₹<input type="number" name="price"><br><br>
            <input type="submit" value="List Product">
        </form>
        <br>
        <a href='/protected_area'><button>Back</button></a>
    '''


if __name__ == "__main__":
    app.run(debug=True)
