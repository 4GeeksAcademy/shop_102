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
from models import db, User
from flask_jwt_extended import JWTManager, create_access_token
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
# app.config['JWT_VERIFY_SUB'] = False
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
# End: Endpoints

# this only runs if `$ python src/app.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
