"""School management routes (Super Admin only)."""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import School, User, AuditLog
from app.utils import role_required, save_upload_file, allowed_image_file

logger = logging.getLogger(__name__)

schools_bp = Blueprint('schools', __name__, template_folder='../templates')


@schools_bp.route('/')
@login_required
@role_required('super_admin')
def list_schools():
    """List all schools."""
    schools = School.query.order_by(School.created_at.desc()).all()
    return render_template('schools.html', schools=schools)


@schools_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def create_school():
    """Create a new school."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()

        if not name:
            flash('School name is required.', 'danger')
            return render_template('create_school.html')

        school = School(name=name, address=address)

        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if not allowed_image_file(file.filename):
                    flash('Invalid logo file. Only images allowed.', 'danger')
                    return render_template('create_school.html')
                saved_path = save_upload_file(file, subfolder='logos')
                if saved_path:
                    school.logo_path = saved_path

        db.session.add(school)
        db.session.flush()  # Get the school ID

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=f'Created school: {school.name} (ID: {school.id})'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'School "{school.name}" created successfully.', 'success')
        return redirect(url_for('schools.list_schools'))

    return render_template('create_school.html')


@schools_bp.route('/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def edit_school(school_id):
    """Edit a school's details."""
    school = db.session.get(School, school_id)
    if not school:
        flash('School not found.', 'danger')
        return redirect(url_for('schools.list_schools'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()

        if not name:
            flash('School name is required.', 'danger')
            return render_template('edit_school.html', school=school)

        old_name = school.name
        school.name = name
        school.address = address

        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if not allowed_image_file(file.filename):
                    flash('Invalid logo file. Only images allowed.', 'danger')
                    return render_template('edit_school.html', school=school)
                saved_path = save_upload_file(file, subfolder='logos')
                if saved_path:
                    school.logo_path = saved_path

        audit = AuditLog(
            user_id=current_user.id,
            action=f'Updated school: {old_name} -> {school.name}'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'School "{school.name}" updated successfully.', 'success')
        return redirect(url_for('schools.list_schools'))

    return render_template('edit_school.html', school=school)


@schools_bp.route('/<int:school_id>/assign-admin', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def assign_admin(school_id):
    """Assign a school admin to a school."""
    school = db.session.get(School, school_id)
    if not school:
        flash('School not found.', 'danger')
        return redirect(url_for('schools.list_schools'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()

        if not all([username, full_name, password]):
            flash('All fields are required.', 'danger')
            return render_template('assign_admin.html', school=school)

        # Check if username exists
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already taken.', 'danger')
            return render_template('assign_admin.html', school=school)

        admin = User(
            username=username,
            full_name=full_name,
            role=User.ROLE_SCHOOL_ADMIN,
            school_id=school.id
        )
        admin.set_password(password)
        db.session.add(admin)

        audit = AuditLog(
            user_id=current_user.id,
            action=f'Assigned admin {username} to school: {school.name}'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'Admin "{username}" assigned to {school.name}.', 'success')
        return redirect(url_for('schools.list_schools'))

    return render_template('assign_admin.html', school=school)


@schools_bp.route('/deactivate_school/<int:school_id>', methods=['POST'])
@role_required('super_admin')
def deactivate_school(school_id):

    school = School.query.get_or_404(school_id)

    school.is_active = False

    db.session.commit()

    flash("School has been deactivated", "warning")

    return redirect(url_for('schools.list_schools'))
    

@schools_bp.route('/<int:school_id>/details')
@login_required
@role_required('super_admin')
def school_details(school_id):
    """View school details."""
    school = db.session.get(School, school_id)
    if not school:
        flash('School not found.', 'danger')
        return redirect(url_for('schools.list_schools'))

    admins = User.query.filter_by(school_id=school.id, role=User.ROLE_SCHOOL_ADMIN).all()
    student_count = school.students.count()
    payment_count = school.payments.count()

    return render_template('school_details.html', school=school, admins=admins,
                           student_count=student_count, payment_count=payment_count)


@schools_bp.route('/upload-logo', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def upload_logo():
    """Upload school logo (for school admin)."""
    if not current_user.school_id:
        flash('No school associated with your account.', 'danger')
        return redirect(url_for('main.dashboard'))

    school = db.session.get(School, current_user.school_id)
    if not school:
        flash('School not found.', 'danger')
        return redirect(url_for('main.dashboard'))

    if 'logo' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('main.dashboard'))

    file = request.files['logo']
    if not file or not file.filename:
        flash('No file selected.', 'warning')
        return redirect(url_for('main.dashboard'))

    if not allowed_image_file(file.filename):
        flash(
            'Invalid file type. Only images (PNG, JPG, GIF, WEBP) allowed.',
            'danger'
        )
        return redirect(url_for('main.dashboard'))

    try:
        saved_path = save_upload_file(file, subfolder='logos')
        if saved_path:
            school.logo_path = saved_path
            audit = AuditLog(
                user_id=current_user.id,
                action=f'Uploaded logo for school: {school.name}'
            )
            db.session.add(audit)
            db.session.commit()
            flash('School logo updated successfully.', 'success')
        else:
            flash('Failed to save logo file.', 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('Logo upload failed: %s', e)
        flash('Failed to upload logo. Please try again.', 'danger')

    return redirect(url_for('main.dashboard'))


@schools_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('school_admin')
def school_settings():
    """School Admin settings page - configure school-specific settings."""
    school = db.session.get(School, current_user.school_id)
    if not school:
        flash('School not found.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        week_start_date_str = request.form.get(
            'week_start_date', ''
        ).strip()

        if week_start_date_str:
            try:
                from datetime import datetime
                school.week_start_date = datetime.strptime(
                    week_start_date_str, '%Y-%m-%d'
                ).date()
            except ValueError:
                flash(
                    'Invalid date format. Please use YYYY-MM-DD.',
                    'danger'
                )
                return render_template(
                    'school_settings.html', school=school
                )
        else:
            school.week_start_date = None

        audit = AuditLog(
            user_id=current_user.id,
            action=(
                f'Updated school settings: '
                f'week_start_date = {school.week_start_date}'
            )
        )
        db.session.add(audit)
        db.session.commit()

        flash('School settings updated successfully.', 'success')
        return redirect(url_for('schools.school_settings'))

    return render_template('school_settings.html', school=school)
