"""Utility functions for the application."""

import logging
import uuid
import os
from datetime import datetime, date
from functools import wraps

from flask import abort, current_app
from flask_login import current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


def role_required(*roles):
    """Decorator to restrict access to specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_week_number(d=None, school=None):
    """Get the week number for a given date.
    
    If school has week_start_date configured, calculates weeks from that date.
    Otherwise, uses ISO week number.
    """
    if d is None:
        d = date.today()
    
    # If school has custom week start date, use it
    if school and school.week_start_date:
        if d >= school.week_start_date:
            delta = d - school.week_start_date
            week_num = (delta.days // 7) + 1
            return max(1, week_num)
        else:
            # Date is before week start date
            return 1
    
    # Default: ISO week number
    return d.isocalendar()[1]


def generate_receipt_number():
    """Generate a unique receipt number."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"RCP-{timestamp}-{unique_id}"


def allowed_image_file(filename):
    """Check if the file has an allowed image extension."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = current_app.config.get(
        'ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    )
    return ext in allowed


def save_upload_file(file_storage, subfolder=''):
    """Save an uploaded file securely.

    Args:
        file_storage: werkzeug FileStorage object
        subfolder: optional subfolder within uploads directory

    Returns:
        str: relative path from static/ or None on failure
    """
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_image_file(file_storage.filename):
        return None

    filename = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"

    upload_dir = current_app.config['UPLOAD_FOLDER']
    if subfolder:
        upload_dir = os.path.join(upload_dir, subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, unique_name)
    file_storage.save(filepath)

    # Return path relative to static/ for url_for('static', ...)
    rel_path = os.path.relpath(filepath, os.path.join(
        current_app.root_path, 'static'
    ))
    return rel_path


def generate_pdf_receipt(payment, student, school):
    """Generate a PDF receipt for a payment.

    Args:
        payment: Payment model instance
        student: Student model instance
        school: School model instance

    Returns:
        str: Path to the generated PDF file
    """
    receipts_folder = current_app.config['RECEIPTS_FOLDER']
    os.makedirs(receipts_folder, exist_ok=True)

    filename = f"{payment.receipt_number}.pdf"
    filepath = os.path.join(receipts_folder, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 40 * mm, "PAYMENT RECEIPT")

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 52 * mm, school.name)

    if school.address:
        c.setFont("Helvetica", 10)
        c.drawCentredString(width / 2, height - 60 * mm, school.address)

    # Divider line
    c.setStrokeColorRGB(0.2, 0.4, 0.2)
    c.setLineWidth(2)
    c.line(30 * mm, height - 65 * mm, width - 30 * mm, height - 65 * mm)

    # Receipt details
    y_pos = height - 80 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Receipt Number:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, payment.receipt_number)

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Date:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, payment.payment_date.strftime('%B %d, %Y'))

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Student Name:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, student.full_name)

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Student ID:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, student.student_id)

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Amount Paid:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, f"GH\u20b5 {payment.amount:.2f}")

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Week Number:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, str(payment.week_number))

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Month:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, payment.month)

    y_pos -= 10 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y_pos, "Year:")
    c.setFont("Helvetica", 11)
    c.drawString(80 * mm, y_pos, str(payment.year))

    # Divider
    y_pos -= 8 * mm
    c.setStrokeColorRGB(0.2, 0.4, 0.2)
    c.setLineWidth(1)
    c.line(30 * mm, y_pos, width - 30 * mm, y_pos)

    # Footer
    y_pos -= 15 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, y_pos, "This is a computer-generated receipt. No signature required.")

    y_pos -= 8 * mm
    c.setFont("Helvetica", 8)
    generated_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    c.drawCentredString(width / 2, y_pos, f"Generated by Madrassatu Taqwa ISPMS on {generated_at}")

    c.save()
    return filepath
