"""Auth routes for the Lorelai API."""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token, jwt_required
from werkzeug.security import check_password_hash

from app.models import User


auth_ns = Namespace("auth", description="Authentication operations")

# Define request/response models for Swagger documentation
login_model = auth_ns.model(
    "Login",
    {
        "email": fields.String(required=True, description="User email address"),
        "password": fields.String(required=True, description="User password"),
    },
)

token_model = auth_ns.model(
    "Token",
    {
        "access_token": fields.String(description="JWT access token"),
        "message": fields.String(description="Success message"),
    },
)

error_model = auth_ns.model("Error", {"message": fields.String(description="Error message")})


@auth_ns.route("/login")
class LoginResource(Resource):
    """Resource for user login."""

    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Success", token_model)
    @auth_ns.response(401, "Authentication failed", error_model)
    def post(self) -> tuple[dict[str, str], int]:
        """Login a user and return JWT token.

        Returns
        -------
            tuple: Contains response dictionary and HTTP status code
            - On success: {'access_token': 'token', 'message': 'success'}, 200
            - On failure: {'message': 'error details'}, 401

        Raises
        ------
            AuthenticationError: If login credentials are invalid
        """
        try:
            data = request.get_json()
            email = data.get("email")
            password = data.get("password")

            # Validate input
            if not email or not password:
                return {"message": "Email and password are required"}, 401

            # Find and authenticate user
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password, password):
                raise PermissionError("Invalid email or password")

            # Create access token
            access_token = create_access_token(identity=user.id)

            return {"access_token": access_token, "message": "Login successful"}, 200

        except PermissionError as e:
            return {"message": str(e)}, 401
        except Exception as e:
            return {"message": f"An unexpected error occurred: {e}"}, 500


@auth_ns.route("/logout")
class LogoutResource(Resource):
    """Resource for user logout."""

    @jwt_required()
    @auth_ns.response(200, "Success")
    @auth_ns.response(401, "Invalid token")
    def post(self) -> tuple[dict[str, str], int]:
        """Logout a user.

        Requires a valid JWT token in the Authorization header.

        Returns
        -------
            tuple: Contains response dictionary and HTTP status code
            - On success: {'message': 'success'}, 200
            - On failure: {'message': 'error details'}, 401
        """
        try:
            # Note: You might want to add token to a blacklist here
            # if you implement token invalidation
            return {"message": "Logout successful"}, 200

        except Exception as e:
            return {"message": f"An unexpected error occurred: {e}"}, 500
