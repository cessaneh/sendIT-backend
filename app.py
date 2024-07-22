import logging
import datetime
import jwt
from flask import Flask, make_response, request, jsonify
from flask_migrate import Migrate
from flask_restful import Api, Resource, reqparse
from flask_bcrypt import Bcrypt
from database import db
from models import User, Order, Feedback, Parcel, Profile

# Configure Flask application
app = Flask(__name__, instance_relative_config=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '9d970c5fb1d04ea380828d9c491448ce'

# Initialize Flask extensions
db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)
bcrypt = Bcrypt(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Error Handling
@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'message': 'Bad Request', 'details': str(error)}), 400)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'message': 'Not Found', 'details': str(error)}), 404)

@app.errorhandler(500)
def internal_error(error):
    return make_response(jsonify({'message': 'Internal Server Error', 'details': str(error)}), 500)

@app.route('/')
def index():
    return "<h1>Welcome to Sendit App</h1>"

# Parsers
register_args = reqparse.RequestParser()
register_args.add_argument('email', type=str, required=True, help='Email address is required')
register_args.add_argument('password', type=str, required=True, help='Password is required')
register_args.add_argument('username', type=str, required=True, help='Username is required')
register_args.add_argument('role', type=str, default='customer', help='Role of the user')

login_args = reqparse.RequestParser()
login_args.add_argument('email', type=str, required=True, help='Email address is required')
login_args.add_argument('password', type=str, required=True, help='Password is required')

class Signup(Resource):
    def post(self):
        data = register_args.parse_args()
        role = data.get('role', 'customer')
        hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')  # Hash the password
        new_user = User(
            email=data['email'],
            username=data['username'],
            role=role,
            password=hashed_password  # Store the hashed password
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"User created successfully: {data['username']}")
            return {"msg": 'User created successfully'}, 201
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating user: {e}", exc_info=True)
            return {"msg": "An error occurred while creating the user"}, 500

class Login(Resource):
    def post(self):
        data = login_args.parse_args()
        email = data.get('email')
        password = data.get('password')

        # Fetch user from the database
        user = User.query.filter_by(email=email).first()
        
        if not user:
            logger.info(f'Login attempt with non-existent email: {email}')
            return {"msg": "User does not exist in our database"}, 404
        
        # Compare the provided password with the stored hashed password
        if not bcrypt.check_password_hash(user.password, password):
            logger.info(f'Failed password attempt for email: {email}')
            return {"msg": "Password is incorrect!"}, 401
        
        # Generate JWT token
        try:
            token = jwt.encode({
                'identity': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            }, app.config['SECRET_KEY'], algorithm='HS256')

            # Generate refresh token
            refresh_token = jwt.encode({
                'identity': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
            }, app.config['SECRET_KEY'], algorithm='HS256')
        except Exception as e:
            logger.error(f"Error generating tokens: {e}", exc_info=True)
            return {"msg": "An error occurred while generating tokens"}, 500

        logger.info(f'Successful login for email: {email}')
        return {"token": token, "refresh_token": refresh_token}, 200

class Users(Resource):
    def get(self):
        users = User.query.all()
        users_list = [user.to_dict() for user in users]
        return make_response(jsonify({"count": len(users_list), "users": users_list}), 200)

    def post(self):
        new_user = User(
            username=request.json.get("username"),
            email=request.json.get("email"),
            password=request.json.get("password"),
            role=request.json.get("role")
        )
        db.session.add(new_user)
        db.session.commit()
        logger.info(f"New user created: {new_user.username}")
        return make_response(jsonify(new_user.to_dict()), 201)

class UserByID(Resource):
    def get(self, id):
        user = User.query.get(id)
        if user is None:
            logger.warning(f"User not found with ID: {id}")
            return make_response(jsonify({"message": "User not found"}), 404)
        return make_response(jsonify(user.to_dict()), 200)

    def patch(self, id):
        user = User.query.get(id)
        if user is None:
            logger.warning(f"User not found for update with ID: {id}")
            return make_response(jsonify({"message": "User not found"}), 404)
        for attr in request.json:
            setattr(user, attr, request.json.get(attr))
        db.session.commit()
        logger.info(f"User updated successfully with ID: {id}")
        return make_response(jsonify(user.to_dict()), 200)

    def delete(self, id):
        user = User.query.get(id)
        if user is None:
            logger.warning(f"User not found for deletion with ID: {id}")
            return make_response(jsonify({"message": "User not found"}), 404)
        db.session.delete(user)
        db.session.commit()
        logger.info(f"User deleted successfully with ID: {id}")
        return make_response(jsonify({"message": "User deleted"}), 200)

class Orders(Resource):
    def get(self):
        orders = Order.query.all()
        orders_list = [order.to_dict() for order in orders]
        return make_response(jsonify({"count": len(orders_list), "orders": orders_list}), 200)

    def post(self):
        new_order = Order(
            pickup_address=request.json.get("pickup_address"),
            delivery_address=request.json.get("delivery_address"),
            status=request.json.get("status"),
            user_id=request.json.get("user_id")
        )
        db.session.add(new_order)
        db.session.commit()
        logger.info(f"New order created with ID: {new_order.id}")
        return make_response(jsonify(new_order.to_dict()), 201)

class OrderByID(Resource):
    def get(self, id):
        order = Order.query.get(id)
        if order is None:
            logger.warning(f"Order not found with ID: {id}")
            return make_response(jsonify({"message": "Order not found"}), 404)
        return make_response(jsonify(order.to_dict()), 200)

    def patch(self, id):
        order = Order.query.get(id)
        if order is None:
            logger.warning(f"Order not found for update with ID: {id}")
            return make_response(jsonify({"message": "Order not found"}), 404)
        for attr in request.json:
            setattr(order, attr, request.json.get(attr))
        db.session.commit()
        logger.info(f"Order updated successfully with ID: {id}")
        return make_response(jsonify(order.to_dict()), 200)

    def delete(self, id):
        order = Order.query.get(id)
        if order is None:
            logger.warning(f"Order not found for deletion with ID: {id}")
            return make_response(jsonify({"message": "Order not found"}), 404)
        db.session.delete(order)
        db.session.commit()
        logger.info(f"Order deleted successfully with ID: {id}")
        return make_response(jsonify({"message": "Order deleted"}), 200)

class FeedbackResource(Resource):
    def get(self):
        feedbacks = Feedback.query.all()
        feedbacks_list = [feedback.to_dict() for feedback in feedbacks]
        return make_response(jsonify({"count": len(feedbacks_list), "feedbacks": feedbacks_list}), 200)

    def post(self):
        new_feedback = Feedback(
            rating=request.json.get("rating"),
            comments=request.json.get("comments"),
            user_id=request.json.get("user_id")
        )
        db.session.add(new_feedback)
        db.session.commit()
        logger.info(f"New feedback created with ID: {new_feedback.id}")
        return make_response(jsonify(new_feedback.to_dict()), 201)

class Parcels(Resource):
    def get(self):
        parcels = Parcel.query.all()
        parcels_list = [parcel.to_dict() for parcel in parcels]
        return make_response(jsonify({"count": len(parcels_list), "parcels": parcels_list}), 200)

    def post(self):
        new_parcel = Parcel(
            description=request.json.get("description"),
            weight=request.json.get("weight"),
            dimensions=request.json.get("dimensions"),
            order_id=request.json.get("order_id")
        )
        db.session.add(new_parcel)
        db.session.commit()
        logger.info(f"New parcel created with ID: {new_parcel.id}")
        return make_response(jsonify(new_parcel.to_dict()), 201)

class Profiles(Resource):
    def get(self):
        profiles = Profile.query.all()
        profiles_list = [profile.to_dict() for profile in profiles]
        return make_response(jsonify({"count": len(profiles_list), "profiles": profiles_list}), 200)

    def post(self):
        new_profile = Profile(
            user_id=request.json.get("user_id"),
            bio=request.json.get("bio"),
            profile_picture=request.json.get("profile_picture")
        )
        db.session.add(new_profile)
        db.session.commit()
        logger.info(f"New profile created with ID: {new_profile.id}")
        return make_response(jsonify(new_profile.to_dict()), 201)

# Add Resources to API
api.add_resource(Signup, '/signup')
api.add_resource(Login, '/login')
api.add_resource(Users, '/users')
api.add_resource(UserByID, '/users/<int:id>')
api.add_resource(Orders, '/orders')
api.add_resource(OrderByID, '/orders/<int:id>')
api.add_resource(FeedbackResource, '/feedback')
api.add_resource(Parcels, '/parcels')
api.add_resource(Profiles, '/profiles')

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
