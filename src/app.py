"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from sqlalchemy import and_, select
from utils import APIException, generate_sitemap
from admin import setup_admin
from models import Product, Sale, Sale_Detail, Shop, db, User
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.url_map.strict_slashes = False

db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config["JWT_SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config['JWT_VERIFY_SUB'] = False
jwt = JWTManager(app)

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)
setup_admin(app)

# Handle/serialize errors like a JSON object

@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints

@app.route('/')
def sitemap():
    return generate_sitemap(app)

# Start: Endpoints
@app.route('/user', methods = ['POST'])
def register_user():
    body = request.get_json(silent = True)

    if body is None:
        return { "message": "Debes enviarme el body" }, 404
    
    if 'email' not in body or 'password' not in body or 'name' not in body:
        return { "message": "Datos incompletos" }, 404
    
    new_lastname = ''
    if 'lastname' in body:
        new_lastname = body['lastname']
    
    new_pwd = bcrypt.generate_password_hash(body['password']).decode('utf-8')

    user = User(email = body['email'], password = new_pwd, name = body['name'], lastname = new_lastname)
    db.session.add(user)
    db.session.commit()

    return { "message": "El usuario ha sido registrado exitosamente" }, 200
    
@app.route('/login', methods = ['POST'])
def login():
    body = request.get_json(silent = True)

    if body is None:
        return { "message": "Debes enviarme un body" }, 404
    
    if 'email' not in body or 'password' not in body:
        return { "message": "Datos incompletos" }, 404

    user = db.session.execute(select(User).where(User.email == body['email'])).scalar_one_or_none()
    if user is None:
        return { "message": "El usuario no existe" }, 404

    if not bcrypt.check_password_hash(user.password, body['password']):
        return { "message": "Usuario o contraseña no válida" }, 404
    
    access_token = create_access_token(identity = user.id)
    return { "token": access_token, "user_id": user.id }, 200

@app.route('/shops')
def get_all_shops():
    all_shops = db.session.execute(select(Shop))
    all_shops = list(map(lambda shop: shop.serialize(), all_shops))

    return { "shops": all_shops }, 200

@app.route('/shops/<int:shop_id>/products')
def get_shop_products(shop_id):
    shop = db.session.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()

    if shop is None:
        return { "message": "La tienda no existe" }, 404
    
    products = []
    for product in shop.products_qty:
        products.append(product.serialize())

    return { "products": products }, 200

@app.route('/sale', methods = ['POST'])
@jwt_required()
def make_sale():
    body = request.get_json(silent = True)

    if body is None:
        return { "message": "Debes enviarme los productos para la compra" }, 404
    
    if 'products' not in body:
        return { "message": "No hay productos en el carrito" }, 404
    
    user_id = get_jwt_identity()
    user = db.session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    if user is None:
        return { "message": "El usuario no existe" }, 404

    sale = Sale()
    db.session.add(sale)
    db.session.commit()

    for product in body['products']:
        sale_detail = Sale_Detail(user_id = user_id, product_id = product['product_id'], shop_id = product['shop_id'], sale_id = sale.id, qty = product['qty'])
        sale.sale_detail.append(sale_detail)

    db.session.commit()
    return { "message": "Se ha creado la compra exitosamente", "sale_id": sale.id }, 200

@app.route('/sale/<int:sale_id>')
@jwt_required()
def get_sale(sale_id):
    sale = db.session.execute(select(Sale).where(Sale.id == sale_id)).scalar_one_or_none()

    if sale is None:
        return { "message": "La compra no existe" }, 404
    
    products = []
    for detail in sale.sale_detail:
        det = {
            "product": db.session.execute(select(Product).where(Product.id == detail.product_id)).scalar_one_or_none().serialize(),
            "shop": db.session.execute(select(Shop).where(Shop.id == detail.shop_id)).scalar_one_or_none().serialize(),
            "qty": detail.qty
        }
        products.append(det)

    return { "sale_detail": products }, 200
# End: Endpoints

# this only runs if `$ python src/app.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
