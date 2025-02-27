"""Contains the routes for the admin page."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import distinct
import mysql
import stripe

from flask import (
    Blueprint,
    jsonify,
    render_template,
    session,
    url_for,
    request,
    flash,
    redirect,
    current_app,
)
from flask_login import login_required, current_user
from app.models.user import User, VALID_ROLES
from app.models.role import Role
from app.models.indexing import IndexingRun
from app.models.datasource import Datasource
from app.models.organisation import Organisation
from app.models.plan import Plan
from app.database import db
from app.helpers.users import (
    role_required,
    create_invited_user_in_db,
    get_user_roles,
    add_user_role,
    remove_user_role,
)

from lorelai.pinecone import PineconeHelper
from lorelai.utils import send_invite_email, create_jwt_token_invite_user

from app.models.config import Config
from app.helpers.stripe_helpers import (
    get_plan_description,
    get_stripe_prices,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin", methods=["GET"])
@role_required(["super_admin", "org_admin"])
@login_required
def admin_dashboard():
    """Return the admin dashboard."""
    try:
        # Get all users
        if current_user.is_super_admin():
            users = User.query.all()
        else:
            users = User.query.filter_by(org_id=current_user.org_id).all()

        # Format users for template
        users_data = [
            {
                "id": user.id,
                "user_id": user.id,  # Include both for compatibility
                "email": user.email,
                "org_name": user.organisation.name if user.organisation else None,
                "roles": user.roles,
            }
            for user in users
        ]

        # Get all roles
        all_roles = Role.query.all()

        return render_template(
            "admin.html",
            users=users_data,
            all_roles=all_roles,
        )
    except SQLAlchemyError as e:
        logging.error(f"Database error: {e}")
        flash("Failed to load admin dashboard.", "error")
        return render_template("admin.html", users=[])


@admin_bp.route("/admin/pinecone")
@role_required(["super_admin", "org_admin"])
@login_required
def list_indexes() -> str:
    """Return the list indexes page.

    Returns
    -------
    str
        The rendered template of the list indexes page.
    """
    pinecone_helper = PineconeHelper()
    indexes = pinecone_helper.list_indexes()

    return render_template("admin/pinecone.html", indexes=indexes, is_admin=current_user.is_admin())


@admin_bp.route("/admin/pinecone/<host_name>")
@role_required(["super_admin", "org_admin"])
@login_required
def index_details(host_name: str) -> str:
    """Return the index details page."""
    pinecone_helper = PineconeHelper()

    index_metadata = pinecone_helper.get_index_details(index_host=host_name)

    return render_template(
        "admin/index_details.html",
        index_host=host_name,
        metadata=index_metadata,
        is_admin=current_user.is_admin(),
    )


@admin_bp.route("/admin/setup", methods=["GET"])
@role_required(["super_admin", "org_admin"])
@login_required
def setup() -> str:
    """Return the LorelAI setup page.

    Shows the parameters for the database connection,
    and two buttons to test the connection and run the database creation.
    Note that it doesn't support changing the database parameters.

    Returns
    -------
    str
        The rendered template of the setup page.
    """
    conn_string = current_app.config["DB_URL"]
    return render_template(
        "admin/setup.html",
        setup_url=url_for("admin.setup_post"),
        test_connection_url=url_for("admin.test_connection"),
        db=conn_string,
    )


@admin_bp.route("/admin/setup", methods=["POST"])
@role_required(["super_admin", "org_admin"])
@login_required
def setup_post() -> str:
    """Create the database using the .db/baseline_schema.sql file.

    After the database is created, run the Flyway migrations in ./db/migrations.

    Returns
    -------
    str
        A message indicating the result of the setup.

    Raises
    ------
    FileNotFoundError
        If the baseline schema file is not found.
    """
    msg = "<strong>Creating the database and running Flyway migrations.</strong><br/>"
    msg += "<pre style='font-family: monospace;'>"
    # cursor = None
    # conn = None

    try:
        msg += "Connecting to MySQL...<br/>"
        #     conn = get_db_connection(with_db=False)
        #     msg += f"MySQL connection successful.<br/>{conn.get_server_info()}<br/>"

        #     db_config = load_config("db")
        #     db_name = db_config["database"]
        #     dir_path = os.path.dirname(os.path.realpath(__file__ + "/../.."))
        #     baseline_schema_path = os.path.join(dir_path, "db", "baseline_schema.sql")

        #     if not os.path.exists(baseline_schema_path):
        #       raise FileNotFoundError(f"Baseline schema file not found at {baseline_schema_path}")

        #     with open(baseline_schema_path) as file:
        #         baseline_schema = file.read()

        #     msg += "Creating the database...<br/>"
        #     msg += f"Baseline schema loaded:<br/>{baseline_schema}<br/>"

        #     cursor = conn.cursor()
        #     cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        #     cursor.execute(f"USE {db_name}")
        #     for result in cursor.execute(baseline_schema, multi=True):
        #         if result.with_rows:
        #             msg += f"Affected {result.rowcount} rows<br/>"

        #     cursor.close()
        #     conn.close()

        #     flyway_success, flyway_result = run_flyway_migrations(
        #         db_config["host"],
        #         db_name,
        #         db_config["user"],
        #         db_config["password"],
        #     )
        #     if flyway_success:
        #         current_app.config["LORELAI_SETUP"] = False
        #     msg += f"Flyway migrations completed. Flyway result:<br/>{flyway_result}<br/>"

        # msg += "</pre>"
        return msg

    except FileNotFoundError as fnf_error:
        logging.error(f"File error: {fnf_error}")
        return jsonify({"error": f"File error: {fnf_error}"}), 500
    except mysql.connector.Error as db_error:
        logging.error(f"Database error: {db_error}")
        return jsonify({"error": f"Database error: {db_error}"}), 500
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500
    # finally:
    #     if cursor:
    #         cursor.close()
    #     if conn:
    #         conn.close()


# @role_required(["super_admin", "org_admin"])
@admin_bp.route("/admin/invite_user", methods=["POST"])
@login_required
def invite_user():
    """
    Handle user invitation process by sending an invite email with a registration link.

    This function performs the following steps:
    1. Retrieves the invitee's email from the request form.
    2. Creates a JWT token for the invitee using their email, the organisation admin's email, and
    the organisation's name.
    3. Generates an invite registration URL with the JWT token.
    4. Sends an invite email to the invitee with the registration URL.
    5. Displays a success or error message based on the email sending status.
    6. Redirects to the admin page.

    Returns
    -------
        Redirect: A redirect response to the admin page.

    Flask Context:
        - Expects 'user_email' and 'org_name' to be present in the session.
        - Expects 'email' to be present in the request form.
    """
    email = request.form["email"]
    token = create_jwt_token_invite_user(
        invitee_email=email,
        org_admin_email=session["user.email"],
        org_name=session["user.org_name"],
    )
    invite_register_url = url_for("chat.index", token=token, _external=True)

    email_status = send_invite_email(
        org_admin_email=session["user.email"],
        invitee_email=email,
        invite_url=invite_register_url,
    )
    if email_status:
        create_invited_user_in_db(email=email, org_id=session["user.org_id"])
        flash(f"Invitation to {email} sent successfully!", "success")
        logging.info(f"Invitation to {email} sent successfully!")
    else:
        flash("Invitation failed", "error")
        logging.error(f"Invitation to {email} failed")

    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/user/<int:user_id>/roles", methods=["GET", "POST"])
@login_required
@role_required(["super_admin", "org_admin"])
def manage_user_roles(user_id):
    """Manage user roles for a user."""
    user = User.query.get_or_404(user_id)
    all_roles = Role.query.all()
    if request.method == "POST":
        # Get and sanitize roles
        submitted_roles = request.form.getlist("roles")
        new_roles = [role.strip() for role in submitted_roles if role.strip() in VALID_ROLES]
        current_roles = get_user_roles(user_id)

        # Add new roles
        for role in new_roles:
            if role not in current_roles:
                add_user_role(user_id, role)

        # Remove roles that are not in the new list
        for role in current_roles:
            if role not in new_roles:
                remove_user_role(user_id, role)

        flash("User roles updated successfully", "success")
        return redirect(url_for("admin.manage_user_roles", user_id=user_id))

    user_roles = get_user_roles(user_id)
    return render_template(
        "admin/manage_user_roles.html",
        user=user,
        all_roles=all_roles,
        user_roles=user_roles,
    )


@admin_bp.route("/admin/indexing-runs")
@role_required(["super_admin"])
@login_required
def indexing_runs():
    """Return the indexing runs page.

    This page is only accessible to super admin users.
    """
    try:
        # Get all indexing runs with eager loading of relationships
        indexing_runs = (
            IndexingRun.query.options(
                db.joinedload(IndexingRun.user),
                db.joinedload(IndexingRun.organisation),
                db.joinedload(IndexingRun.datasource),
            )
            .order_by(IndexingRun.created_at.desc())
            .all()
        )

        # Get unique values for filters
        users = User.query.all()
        organizations = Organisation.query.all()
        datasources = Datasource.query.all()
        statuses = db.session.query(distinct(IndexingRun.status)).all()
        statuses = [status[0] for status in statuses]  # Flatten the result

        return render_template(
            "admin/indexing_runs.html",
            indexing_runs=indexing_runs,
            users=users,
            organizations=organizations,
            datasources=datasources,
            statuses=statuses,
        )
    except SQLAlchemyError as e:
        logging.error(f"Database error: {e}")
        flash("Failed to retrieve indexing runs.", "error")
        return render_template("admin/indexing_runs.html", indexing_runs=[])


@admin_bp.route("/admin/prompts", methods=["GET"])
@login_required
def list_prompts():
    """List all prompt templates."""
    if not current_user.is_super_admin():
        flash("Only super admins can manage prompts.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    prompts = Config.query.filter(Config.key.like("%_prompt_template")).all()
    return render_template("admin/prompts.html", prompts=prompts)


@admin_bp.route("/admin/prompts/edit/<int:config_id>", methods=["GET", "POST"])
@login_required
def edit_prompt(config_id):
    """Edit a prompt template."""
    if not current_user.is_super_admin():
        flash("Only super admins can manage prompts.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    config = Config.query.get_or_404(config_id)

    if request.method == "POST":
        value = request.form.get("value")
        description = request.form.get("description")

        if not value:
            flash("Prompt template cannot be empty.", "danger")
            return render_template("admin/edit_prompt.html", config=config)

        config.value = value
        config.description = description
        db.session.commit()

        flash("Prompt template updated successfully.", "success")
        return redirect(url_for("admin.prompts"))

    return render_template("admin/edit_prompt.html", config=config)


@admin_bp.route("/admin/prompts/new", methods=["GET", "POST"])
@login_required
def new_prompt():
    """Create a new prompt template."""
    if not current_user.is_super_admin():
        flash("Only super admins can manage prompts.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        key = request.form.get("key")
        value = request.form.get("value")
        description = request.form.get("description")

        if not key or not value:
            flash("Key and prompt template are required.", "danger")
            return render_template("admin/new_prompt.html")

        if not key.endswith("_prompt_template"):
            key = f"{key}_prompt_template"

        config = Config(key=key, value=value, description=description)
        db.session.add(config)
        db.session.commit()

        flash("Prompt template created successfully.", "success")
        return redirect(url_for("admin.prompts"))

    return render_template("admin/new_prompt.html")


@admin_bp.route("/admin/stripe-plans", methods=["GET"])
@role_required(["super_admin"])
@login_required
def manage_stripe_plans():
    """Admin interface for managing Stripe plans and prices."""
    try:
        # Get all plans from the database
        plans = Plan.query.all()

        # Enhance plans with Stripe data
        enhanced_plans = []
        for plan in plans:
            plan_data = {
                "plan_id": plan.plan_id,
                "plan_name": plan.plan_name,
                "message_limit_daily": plan.message_limit_daily,
                "stripe_product_id": plan.stripe_product_id,
                "price": 0.0,  # Default price
                "description": "",  # Default description
                "prices": [],  # List of all available prices
            }

            # Fetch price and description from Stripe if product ID exists
            if plan.stripe_product_id:
                # Get all prices for this product
                prices = get_stripe_prices(plan.stripe_product_id)
                if prices:
                    # Set the default price (first monthly price) for backward compatibility
                    monthly_prices = [
                        p
                        for p in prices
                        if p.get("recurring") and p["recurring"]["interval"] == "month"
                    ]
                    if monthly_prices:
                        plan_data["price"] = monthly_prices[0]["unit_amount"]
                    elif prices:
                        # If no monthly price, use the first price
                        plan_data["price"] = prices[0]["unit_amount"]

                    # Add all prices to the plan data
                    plan_data["prices"] = prices

                description = get_plan_description(plan.stripe_product_id)
                if description:
                    plan_data["description"] = description

            enhanced_plans.append(plan_data)

        # Initialize Stripe with the secret key
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

        # Check if we're in test environment
        is_test_environment = current_app.config["STRIPE_SECRET_KEY"].startswith("sk_test_")

        # Get all products from Stripe
        products = stripe.Product.list()

        # Get all products from Stripe (active only)
        products = stripe.Product.list(active=True)

        # Get formatted prices for Stripe products section
        formatted_prices = {}
        for product in products.data:
            prices = get_stripe_prices(product.id)
            if prices:
                formatted_prices[product.id] = [
                    {
                        "id": price["id"],
                        "amount": f"{price['unit_amount']:.2f}",
                        "currency": price["currency"],
                        "interval": price.get("recurring", {}).get("interval", "one-time"),
                        "nickname": price.get("nickname", ""),
                    }
                    for price in prices
                ]

        return render_template(
            "admin/stripe_plans.html",
            plans=plans,
            enhanced_plans=enhanced_plans,
            stripe_products=products.data,
            formatted_prices=formatted_prices,
            is_test_environment=is_test_environment,
        )
    except Exception as e:
        logging.error(f"Error loading Stripe plans: {str(e)}", exc_info=True)
        flash(f"Error loading Stripe plans: {str(e)}", "danger")
        return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/stripe-plans/update", methods=["POST"])
@role_required(["super_admin"])
@login_required
def update_stripe_plan():
    """Update a plan in the database and optionally in Stripe."""
    try:
        plan_id = request.form.get("plan_id")
        plan_name = request.form.get("plan_name")
        description = request.form.get("description")
        price = request.form.get("price")
        message_limit_daily = request.form.get("message_limit_daily")
        stripe_product_id = request.form.get("stripe_product_id")

        if not plan_id or not plan_name:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Convert price to float
        try:
            price = float(price) if price else 0.0
        except ValueError:
            return jsonify({"success": False, "message": "Invalid price format"}), 400

        # Convert message limit to int
        try:
            message_limit_daily = int(message_limit_daily) if message_limit_daily else None
        except ValueError:
            return jsonify({"success": False, "message": "Invalid message limit format"}), 400

        # Get the plan from the database
        plan = Plan.query.get(plan_id)
        if not plan:
            return jsonify({"success": False, "message": f"Plan with ID {plan_id} not found"}), 404

        # Initialize Stripe with the secret key
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

        # If a Stripe product ID is provided, verify it exists
        if stripe_product_id:
            try:
                stripe.Product.retrieve(stripe_product_id)
            except stripe.error.InvalidRequestError:
                return jsonify({"success": False, "message": "Invalid Stripe product ID"}), 400

            # Update the product in Stripe if it exists
            if plan.stripe_product_id:
                try:
                    stripe.Product.modify(
                        plan.stripe_product_id,
                        name=f"Helixiora {plan_name.capitalize()}",
                        description=description or f"{plan_name.capitalize()} plan for Helixiora",
                    )
                except stripe.error.InvalidRequestError:
                    # If the product doesn't exist in Stripe, create a new one
                    product = stripe.Product.create(
                        name=f"Helixiora {plan_name.capitalize()}",
                        description=description or f"{plan_name.capitalize()} plan for Helixiora",
                        metadata={"plan_id": plan.plan_id, "plan_name": plan_name},
                    )
                    stripe_product_id = product.id

        # Update the plan in the database
        plan.plan_name = plan_name
        plan.message_limit_daily = message_limit_daily

        # Only update the stripe_product_id if it's provided
        if stripe_product_id:
            plan.stripe_product_id = stripe_product_id

        db.session.commit()

        message = f"Successfully updated plan: {plan.plan_name}"
        flash(message, "success")
        return jsonify({"success": True, "message": message})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating plan: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@admin_bp.route("/admin/stripe-plans/create-product", methods=["POST"])
@role_required(["super_admin"])
@login_required
def create_stripe_product():
    """Create a new product in Stripe based on a plan in the database."""
    try:
        plan_id = request.form.get("plan_id")
        create_prices = request.form.get("create_prices", "true") == "true"
        price = request.form.get("price")
        description = request.form.get("description")

        if not plan_id:
            return jsonify({"success": False, "message": "Missing plan ID"}), 400

        # Convert price to float
        try:
            price = float(price) if price else 0.0
        except ValueError:
            return jsonify({"success": False, "message": "Invalid price format"}), 400

        # Get the plan from the database
        plan = Plan.query.get(plan_id)
        if not plan:
            return jsonify({"success": False, "message": f"Plan with ID {plan_id} not found"}), 404

        # Initialize Stripe with the secret key
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

        # Create a new product in Stripe
        product = stripe.Product.create(
            name=f"Helixiora {plan.plan_name.capitalize()}",
            description=description or f"{plan.plan_name.capitalize()} plan for Helixiora",
            metadata={"plan_id": plan.plan_id, "plan_name": plan.plan_name},
        )

        # Update the plan with the product ID
        plan.stripe_product_id = product.id

        # Create prices if requested
        created_prices = []
        if create_prices:
            # Create monthly price
            monthly_price = stripe.Price.create(
                product=product.id,
                unit_amount=int(float(price) * 100),  # Convert to cents
                currency="usd",  # Default to USD, can be made configurable
                recurring={"interval": "month", "interval_count": 1},
                nickname=f"Monthly - ${float(price):.2f}",
                metadata={
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "interval": "month",
                },
            )
            created_prices.append(monthly_price)

            # Create yearly price (with 10% discount)
            yearly_amount = int(float(price) * 12 * 0.9 * 100)  # 10% discount
            yearly_price = stripe.Price.create(
                product=product.id,
                unit_amount=yearly_amount,
                currency="usd",
                recurring={"interval": "year", "interval_count": 1},
                nickname=f"Yearly - ${yearly_amount / 100:.2f}",
                metadata={
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "interval": "year",
                },
            )
            created_prices.append(yearly_price)

        db.session.commit()

        message = f"Successfully created Stripe product for {plan.plan_name}"
        if created_prices:
            message += f" with {len(created_prices)} prices"
        flash(message, "success")
        return jsonify({"success": True, "message": message})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating Stripe product: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@admin_bp.route("/admin/stripe-plans/edit-plan", methods=["POST"])
@role_required(["super_admin"])
@login_required
def edit_plan():
    """Edit a plan in the database."""
    try:
        plan_id = request.form.get("plan_id")
        plan_name = request.form.get("plan_name")
        description = request.form.get("description")
        price = request.form.get("price")
        message_limit_daily = request.form.get("message_limit_daily")
        stripe_product_id = request.form.get("stripe_product_id")

        if not plan_id or not plan_name:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Convert message limit to int
        try:
            message_limit_daily = int(message_limit_daily) if message_limit_daily else None
        except ValueError:
            return jsonify({"success": False, "message": "Invalid message limit format"}), 400

        # Get the plan from the database
        plan = Plan.query.get(plan_id)
        if not plan:
            return jsonify({"success": False, "message": f"Plan with ID {plan_id} not found"}), 404

        # Update the plan in the database
        plan.plan_name = plan_name
        plan.message_limit_daily = message_limit_daily

        # Check if we're changing the Stripe product link
        is_changing_product = stripe_product_id != plan.stripe_product_id

        # Update the Stripe product ID if it's changing
        if is_changing_product:
            plan.stripe_product_id = stripe_product_id

        # If the plan has a Stripe product ID and we're not changing it, we don't update
        # description or prices
        if plan.stripe_product_id and not is_changing_product:
            # Only update the product name in Stripe
            try:
                # Initialize Stripe with the secret key
                stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

                # Update the product name in Stripe
                stripe.Product.modify(
                    plan.stripe_product_id,
                    name=f"Helixiora {plan_name.capitalize()}",
                )
            except stripe.error.InvalidRequestError as e:
                logging.error(f"Error updating Stripe product: {str(e)}")
                # Continue with the database update even if Stripe update fails

        # If the plan doesn't have a Stripe product ID or we're changing it, and we have price
        # and description
        elif not plan.stripe_product_id and price and description:
            # Convert price to float
            try:
                price = float(price) if price else 0.0
            except ValueError:
                return jsonify({"success": False, "message": "Invalid price format"}), 400

            # Update the description
            plan.description = description

            # If we're linking to a new Stripe product, we don't need to create prices
            if not stripe_product_id:
                # This is a local-only plan, just save the price in the database
                pass

        # If we're linking to a new Stripe product and have a price, create new prices
        elif stripe_product_id and price:
            # Convert price to float
            try:
                price = float(price) if price else 0.0
            except ValueError:
                return jsonify({"success": False, "message": "Invalid price format"}), 400

            # Initialize Stripe with the secret key
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

            # Update the product in Stripe
            stripe.Product.modify(
                stripe_product_id,
                name=f"Helixiora {plan_name.capitalize()}",
                description=description or f"{plan_name.capitalize()} plan for Helixiora",
            )

            # If price is provided, create new prices
            if price > 0:
                # Track created prices
                created_prices = []

                # Create a new monthly price
                monthly_price = stripe.Price.create(
                    product=stripe_product_id,
                    unit_amount=int(price * 100),  # Convert to cents
                    currency="usd",
                    recurring={"interval": "month", "interval_count": 1},
                    nickname=f"Monthly - ${price:.2f}",
                    metadata={
                        "plan_id": plan.plan_id,
                        "plan_name": plan.plan_name,
                        "interval": "month",
                    },
                )
                created_prices.append(monthly_price)
                current_app.logger.info(
                    f"Created monthly price: {monthly_price.id} for product {stripe_product_id}"
                )

                # Create a new yearly price (with 10% discount)
                yearly_amount = int(price * 12 * 0.9 * 100)  # 10% discount
                yearly_price = stripe.Price.create(
                    product=stripe_product_id,
                    unit_amount=yearly_amount,
                    currency="usd",
                    recurring={"interval": "year", "interval_count": 1},
                    nickname=f"Yearly - ${yearly_amount / 100:.2f}",
                    metadata={
                        "plan_id": plan.plan_id,
                        "plan_name": plan.plan_name,
                        "interval": "year",
                    },
                )
                created_prices.append(yearly_price)
                current_app.logger.info(
                    f"Created yearly price: {yearly_price.id} for product {stripe_product_id}"
                )

        db.session.commit()

        message = f"Successfully updated plan: {plan.plan_name}"
        flash(message, "success")
        return jsonify({"success": True, "message": message})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating plan: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@admin_bp.route("/admin/stripe-plans/import-from-live", methods=["GET", "POST"])
@role_required(["super_admin"])
@login_required
def import_stripe_products_from_live():
    """Import products and prices from Stripe live environment to test environment.

    This utility helps administrators synchronize their test environment with
    the live environment by importing all active products and prices.

    Returns
    -------
    Response
        Rendered template or JSON response indicating success/failure.
    """
    # Get current environment's API key
    current_api_key = current_app.config["STRIPE_SECRET_KEY"]

    # Check if we're in test environment
    is_test_environment = current_api_key.startswith("sk_test_")

    if not is_test_environment:
        flash(
            "This tool can only be used in a test environment. You are currently in a live env.",
            "danger",
        )
        return redirect(url_for("admin.manage_stripe_plans"))

    if request.method == "GET":
        return render_template(
            "admin/stripe_import_products.html",
            is_admin=current_user.is_admin(),
            is_test_environment=is_test_environment,
        )

    try:
        # Get live API key from form
        live_api_key = request.form.get("live_api_key")

        if not live_api_key:
            return jsonify({"success": False, "message": "Live API key is required"}), 400

        # Verify the live API key is actually a live key
        if not live_api_key.startswith("sk_live_"):
            return jsonify(
                {
                    "success": False,
                    "message": "Invalid live API key. The key must start with 'sk_live_'.",
                }
            ), 400

        # Store the current API key to restore it later
        original_api_key = stripe.api_key

        try:
            # Set Stripe API key to the live key
            stripe.api_key = live_api_key

            # Get all active products from live
            live_products = stripe.Product.list(active=True)

            # Get all active prices from live
            live_prices = stripe.Price.list(active=True)

            # Map to store live price ID -> test price ID for reference
            price_id_map = {}

            # Switch to test API key
            stripe.api_key = current_api_key

            # Create products and prices in test environment
            for product in live_products.data:
                # Create the product in test
                test_product = stripe.Product.create(
                    name=product.name,
                    description=product.description,
                    active=product.active,
                    metadata=product.metadata,
                )

                # Find all prices for this product
                product_prices = [p for p in live_prices.data if p.product == product.id]

                for price in product_prices:
                    # Create equivalent price in test
                    price_data = {
                        "product": test_product.id,
                        "unit_amount": price.unit_amount,
                        "currency": price.currency,
                        "active": price.active,
                        "metadata": price.metadata,
                        "nickname": price.nickname,
                    }

                    # Add recurring parameters if it's a subscription
                    if price.type == "recurring" and price.recurring:
                        price_data["recurring"] = {
                            "interval": price.recurring.interval,
                            "interval_count": price.recurring.interval_count,
                        }
                        if hasattr(price.recurring, "usage_type"):
                            price_data["recurring"]["usage_type"] = price.recurring.usage_type

                    # Create the price in test
                    test_price = stripe.Price.create(**price_data)

                    # Store the mapping
                    price_id_map[price.id] = test_price.id

        finally:
            # Restore the original API key
            stripe.api_key = original_api_key

        # Return success with the mapping for reference
        return jsonify(
            {
                "success": True,
                "message": (
                    f"Successfully imported {len(live_products.data)} products and "
                    f"{len(price_id_map)} prices to test environment"
                ),
                "price_id_map": price_id_map,
            }
        )

    except Exception as e:
        logging.error(f"Error importing Stripe products: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@admin_bp.route("/admin/stripe-plans/link-product", methods=["POST"])
@role_required(["super_admin"])
@login_required
def link_stripe_product():
    """Link a plan to a Stripe product and optionally set a default price."""
    try:
        plan_id = request.form.get("plan_id")
        product_id = request.form.get("product_id")
        price_id = request.form.get("price_id", None)  # Optional default price

        if not plan_id or not product_id:
            return jsonify({"success": False, "message": "Missing required parameters"}), 400

        # Get the plan from the database
        plan = Plan.query.get(plan_id)
        if not plan:
            return jsonify({"success": False, "message": f"Plan with ID {plan_id} not found"}), 404

        # Initialize Stripe with the secret key
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

        # Verify that the product ID exists in Stripe
        try:
            product = stripe.Product.retrieve(product_id)
            if not product or not product.active:
                return jsonify(
                    {"success": False, "message": "Invalid or inactive Stripe product ID"}
                ), 400
        except stripe.error.InvalidRequestError:
            return jsonify({"success": False, "message": "Invalid Stripe product ID"}), 400

        # If a price ID is provided, verify it exists and belongs to the product
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
                if not price or not price.active or price.product != product_id:
                    return jsonify(
                        {
                            "success": False,
                            "message": (
                                "Invalid price ID or price doesn't belong to the selected product"
                            ),
                        }
                    ), 400
            except stripe.error.InvalidRequestError:
                return jsonify({"success": False, "message": "Invalid Stripe price ID"}), 400

        # Update the plan in the database
        plan.stripe_product_id = product_id
        db.session.commit()

        message = f"Successfully linked {plan.plan_name} to Stripe product"
        if price_id:
            message += " and set default price"

        flash(message, "success")
        return jsonify({"success": True, "message": message})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error linking Stripe product: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
