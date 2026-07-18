import os
import logging
import time
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import boto3
import watchtower
from werkzeug.utils import secure_filename
from uuid import uuid4
from prometheus_flask_exporter import PrometheusMetrics

# --- Configuration ---
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "landmark-app-bucket-dev")
LOG_GROUP = os.environ.get("LOG_GROUP", "/landmark/employee-app")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# --- App Setup ---
app = Flask(__name__)
CORS(app)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/employees"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 10,
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)
s3 = boto3.client("s3", region_name=AWS_REGION)

# --- Logging Setup (stdout + CloudWatch) ---
logger = logging.getLogger("employee-app")
logger.setLevel(logging.INFO)

# Stdout handler - JSON format for container logs
stdout_handler = logging.StreamHandler()
stdout_handler.setFormatter(logging.Formatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}'
))
logger.addHandler(stdout_handler)

# CloudWatch handler - streams to /landmark/employee-app log group
try:
    cw_handler = watchtower.CloudWatchLogHandler(
        log_group_name=LOG_GROUP,
        stream_name=f"{ENVIRONMENT}-{os.environ.get('HOSTNAME', 'local')}",
        boto3_client=boto3.client("logs", region_name=AWS_REGION),
    )
    logger.addHandler(cw_handler)
    logger.info("CloudWatch logging enabled")
except Exception as e:
    logger.warning(f"CloudWatch logging unavailable: {e}")


# --- Models ---
class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(10))
    photo_url = db.Column(db.String(500))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "department": self.department,
            "dob": self.dob,
            "photo_url": self.photo_url,
        }


# Prometheus metrics
PrometheusMetrics(app)

# Create tables on startup
with app.app_context():
    db.create_all()
    logger.info("Database tables initialized")


# --- Middleware ---
@app.before_request
def before_request():
    g.start_time = time.time()


@app.after_request
def after_request(response):
    duration = round((time.time() - g.start_time) * 1000, 2)
    logger.info(
        f"{request.method} {request.path} - {response.status_code} - {duration}ms"
    )
    return response


# --- Error Handlers ---
@app.errorhandler(400)
def bad_request(e):
    logger.warning(f"Bad request: {request.path} - {e}")
    return jsonify({"error": "Bad request", "message": str(e)}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {request.path} - {e}")
    return jsonify({"error": "Internal server error"}), 500


# --- Helper ---
def upload_photo(file):
    """Upload a file to S3 and return the URL."""
    filename = f"photos/{uuid4()}-{secure_filename(file.filename)}"
    s3.upload_fileobj(file, S3_BUCKET, filename, ExtraArgs={"ContentType": file.content_type})
    url = f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
    logger.info(f"Photo uploaded: {filename}")
    return url


# --- Routes ---
@app.route("/api/health", methods=["GET"])
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "db": "connected"})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "db": "disconnected"}), 503


@app.route("/api/employees", methods=["GET"])
def get_employees():
    employees = Employee.query.order_by(Employee.name).all()
    logger.info(f"Listed {len(employees)} employees")
    return jsonify([e.to_dict() for e in employees])


@app.route("/api/employees/<int:id>", methods=["GET"])
def get_employee(id):
    employee = Employee.query.get_or_404(id)
    return jsonify(employee.to_dict())


@app.route("/api/employees", methods=["POST"])
def create_employee():
    data = request.form
    if not all(k in data for k in ("name", "email", "role", "department")):
        return jsonify({"error": "Missing required fields"}), 400

    # Check for duplicate email
    if Employee.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 409

    photo_url = None
    if "photo" in request.files and request.files["photo"].filename:
        photo_url = upload_photo(request.files["photo"])

    employee = Employee(
        name=data["name"],
        email=data["email"],
        role=data["role"],
        department=data["department"],
        dob=data.get("dob"),
        photo_url=photo_url,
    )
    db.session.add(employee)
    db.session.commit()
    logger.info(f"Employee created: id={employee.id} email={employee.email}")
    return jsonify(employee.to_dict()), 201


@app.route("/api/employees/<int:id>", methods=["PUT"])
def update_employee(id):
    employee = Employee.query.get_or_404(id)
    data = request.form

    employee.name = data.get("name", employee.name)
    employee.email = data.get("email", employee.email)
    employee.role = data.get("role", employee.role)
    employee.department = data.get("department", employee.department)
    employee.dob = data.get("dob", employee.dob)

    if "photo" in request.files and request.files["photo"].filename:
        employee.photo_url = upload_photo(request.files["photo"])

    db.session.commit()
    logger.info(f"Employee updated: id={employee.id}")
    return jsonify(employee.to_dict())


@app.route("/api/employees/<int:id>", methods=["DELETE"])
def delete_employee(id):
    employee = Employee.query.get_or_404(id)
    db.session.delete(employee)
    db.session.commit()
    logger.info(f"Employee deleted: id={id} email={employee.email}")
    return jsonify({"message": "Employee deleted"})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Returns employee stats: total count, department breakdown, latest hire."""
    total = Employee.query.count()
    departments = db.session.query(
        Employee.department, db.func.count(Employee.id)
    ).group_by(Employee.department).all()
    latest = Employee.query.order_by(Employee.id.desc()).first()

    stats = {
        "total_employees": total,
        "departments": {dept: count for dept, count in departments},
        "latest_hire": latest.to_dict() if latest else None,
        "version": "2.0.0",
    }
    logger.info(f"Stats requested: {total} employees across {len(departments)} departments")
    return jsonify(stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
