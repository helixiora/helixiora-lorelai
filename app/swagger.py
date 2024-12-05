"""Swagger authorizations."""

authorizations = {
    "Bearer Auth": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Enter your Bearer token in the format **Bearer &lt;token&gt;**",
    }
}
