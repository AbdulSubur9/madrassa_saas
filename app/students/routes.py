"""Student management routes."""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import pandas as pd
from app.extensions import db
from app.models import Student, SchoolClass, AuditLog, Payment
from app.students.forms import StudentForm, ClassForm
from app.utils import role_required

logger = logging.getLogger(__name__)

students_bp = Blueprint('students', __name__, template_folder='../templates')

ALLOWED_EXTENSIONS = {'xlsx', 'csv'}


def generate_student_id(school_id, year=None):
    """
    Generate a unique student ID in the format TAQWA-{year}-{number}.
    
    Args:
        school_id: The ID of the school
        year: The academic year (defaults to current year)
    
    Returns:
        A unique student ID string
    """
    if year is None:
        year = datetime.now().year
    
    # Query for existing TAQWA IDs for this school and year
    prefix = f'TAQWA-{year}-'
    existing_ids = Student.query.filter(
        Student.school_id == school_id,
        Student.student_id.like(f'{prefix}%')
    ).all()
    
    # Find the highest number
    max_num = 0
    for student in existing_ids:
        try:
            # Extract the number after TAQWA-YYYY-
            num_part = student.student_id.replace(prefix, '')
            num = int(num_part)
            if num > max_num:
                max_num = num
        except (ValueError, AttributeError):
            continue
    
    # Generate the next ID
    new_num = max_num + 1
    return f'{prefix}{new_num:04d}'


def validate_student_data(row, idx):
    """
    Validate a single row of student data.
    
    Args:
        row: A pandas Series row from the Excel file
        idx: The row index (for error reporting)
    
    Returns:
        A tuple (is_valid, error_message)
    """
    # Validate required fields
    first_name = str(row.get('first_name', '')).strip()
    last_name = str(row.get('last_name', '')).strip()
    
    if not first_name or first_name.lower() == 'nan':
        return False, 'Missing first_name'
    if not last_name or last_name.lower() == 'nan':
        return False, 'Missing last_name'
    
    # Validate gender
    gender = str(row.get('gender', '')).strip().lower()
    if gender not in ['male', 'female']:
        return False, f'Invalid gender: {row.get("gender", "")}. Must be Male or Female'
    
    # Contact is optional for import
    
    # Validate DOB if provided (optional)
    dob = row.get('dob', '')
    if dob and str(dob).strip() and str(dob).lower() != 'nan':
        try:
            if isinstance(dob, str):
                datetime.strptime(dob, '%Y-%m-%d').date()
            else:
                dob.date()
        except (ValueError, AttributeError):
            return False, f'Invalid date format for dob: {dob}. Use YYYY-MM-DD'
    
    return True, None


@students_bp.route('/')
@login_required
@role_required('super_admin', 'school_admin')
def list_students():
    """List all students for the current school."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()
    class_filter = request.args.get('class_id', 0, type=int)
    status_filter = request.args.get('status', '', type=str)

    query = Student.query.filter_by(school_id=current_user.school_id)

    # Apply search filters
    if search:
        query = query.filter(
            db.or_(
                Student.full_name.ilike(f'%{search}%'),
                Student.student_id.ilike(f'%{search}%')
            )
        )

    if class_filter:
        query = query.filter_by(class_id=class_filter)

    if status_filter:
        query = query.filter_by(status=status_filter)

    students = query.order_by(Student.full_name).paginate(
        page=page, per_page=20, error_out=False
    )
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).all()

    return render_template('students.html', students=students, classes=classes,
                           search=search, class_filter=class_filter, status_filter=status_filter)


@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'school_admin')
def add_student():
    """Add a new student."""
    form = StudentForm()
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).all()
    form.class_id.choices = [(0, '-- Select Class --')] + [(c.id, c.class_name) for c in classes]

    if form.validate_on_submit():
        # Generate student ID if not provided
        student_id = form.student_id.data.strip() if form.student_id.data else ''
        if not student_id:
            student_id = generate_student_id(current_user.school_id)
        
        # Check for duplicate student ID within the school
        existing = Student.query.filter_by(
            school_id=current_user.school_id,
            student_id=student_id
        ).first()
        if existing:
            flash('A student with this ID already exists in your school.', 'danger')
            return render_template('student_form.html', form=form, title='Add Student')

        student = Student(
            school_id=current_user.school_id,
            student_id=student_id,
            full_name=form.full_name.data.strip(),
            gender=form.gender.data,
            class_id=form.class_id.data if form.class_id.data != 0 else None,
            guardian_name=form.guardian_name.data.strip() if form.guardian_name.data else None,
            guardian_phone=form.guardian_phone.data.strip() if form.guardian_phone.data else None
        )
        db.session.add(student)

        audit = AuditLog(
            user_id=current_user.id,
            action=f'Added student: {student.full_name} (ID: {student.student_id})'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'Student "{student.full_name}" added successfully.', 'success')
        return redirect(url_for('students.list_students'))

    return render_template('student_form.html', form=form, title='Add Student')


@students_bp.route('/<int:student_pk>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'school_admin')
def edit_student(student_pk):
    """Edit an existing student."""
    student = db.session.get(Student, student_pk)
    if not student or student.school_id != current_user.school_id:
        flash('Student not found.', 'danger')
        return redirect(url_for('students.list_students'))

    form = StudentForm(obj=student)
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).all()
    form.class_id.choices = [(0, '-- Select Class --')] + [(c.id, c.class_name) for c in classes]

    if form.validate_on_submit():
        # Check for duplicate student_id (excluding current student)
        existing = Student.query.filter(
            Student.school_id == current_user.school_id,
            Student.student_id == form.student_id.data,
            Student.id != student_pk
        ).first()
        if existing:
            flash('A student with this ID already exists in your school.', 'danger')
            return render_template('student_form.html', form=form, title='Edit Student')

        student.student_id = form.student_id.data.strip()
        student.full_name = form.full_name.data.strip()
        student.gender = form.gender.data
        student.class_id = form.class_id.data if form.class_id.data != 0 else None
        student.guardian_name = form.guardian_name.data.strip() if form.guardian_name.data else None
        student.guardian_phone = form.guardian_phone.data.strip() if form.guardian_phone.data else None

        audit = AuditLog(
            user_id=current_user.id,
            action=f'Updated student: {student.full_name} (ID: {student.student_id})'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'Student "{student.full_name}" updated successfully.', 'success')
        return redirect(url_for('students.list_students'))

    return render_template('student_form.html', form=form, title='Edit Student')


@students_bp.route('/<int:student_pk>/toggle-status', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def toggle_student_status(student_pk):
    """Activate or deactivate a student."""
    student = db.session.get(Student, student_pk)
    if not student or student.school_id != current_user.school_id:
        flash('Student not found.', 'danger')
        return redirect(url_for('students.list_students'))

    student.status = 'inactive' if student.status == 'active' else 'active'

    audit = AuditLog(
        user_id=current_user.id,
        action=f'Changed student status to {student.status}: {student.full_name}'
    )
    db.session.add(audit)
    db.session.commit()

    flash(f'Student "{student.full_name}" is now {student.status}.', 'success')
    return redirect(url_for('students.list_students'))


@students_bp.route('/<int:student_pk>/details')
@login_required
@role_required('super_admin', 'school_admin', 'collector', 'accountant')
def student_details(student_pk):
    """View student details and payment history."""
    student = db.session.get(Student, student_pk)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students.list_students'))

    # School isolation
    if not current_user.is_super_admin and student.school_id != current_user.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    payments = student.payments.order_by(db.desc('payment_date')).all()
    return render_template('student_details.html', student=student, payments=payments)


# ---- Class Management ----

@students_bp.route('/classes')
@login_required
@role_required('super_admin', 'school_admin')
def list_classes():
    """List all classes for the current school."""
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).order_by(SchoolClass.class_name).all()
    form = ClassForm()
    return render_template('classes.html', classes=classes, form=form)


@students_bp.route('/classes/add', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def add_class():
    """Add a new class."""
    form = ClassForm()
    if form.validate_on_submit():
        existing = SchoolClass.query.filter_by(
            school_id=current_user.school_id,
            class_name=form.class_name.data.strip()
        ).first()
        if existing:
            flash('A class with this name already exists.', 'danger')
            return redirect(url_for('students.list_classes'))

        school_class = SchoolClass(
            school_id=current_user.school_id,
            class_name=form.class_name.data.strip()
        )
        db.session.add(school_class)

        audit = AuditLog(
            user_id=current_user.id,
            action=f'Created class: {school_class.class_name}'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'Class "{school_class.class_name}" created successfully.', 'success')
    else:
        flash('Invalid class name.', 'danger')

    return redirect(url_for('students.list_classes'))


@students_bp.route('/classes/<int:class_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def delete_class(class_id):
    """Delete a class."""
    school_class = db.session.get(SchoolClass, class_id)
    if not school_class or school_class.school_id != current_user.school_id:
        flash('Class not found.', 'danger')
        return redirect(url_for('students.list_classes'))

    # Check if there are students in this class
    if school_class.students.count() > 0:
        flash('Cannot delete a class that has students assigned to it.', 'danger')
        return redirect(url_for('students.list_classes'))

    class_name = school_class.class_name
    db.session.delete(school_class)

    audit = AuditLog(
        user_id=current_user.id,
        action=f'Deleted class: {class_name}'
    )
    db.session.add(audit)
    db.session.commit()

    flash(f'Class "{class_name}" deleted successfully.', 'success')
    return redirect(url_for('students.list_classes'))


@students_bp.route('/<int:student_pk>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def delete_student(student_pk):
    """Delete a student and their payment records (admin only)."""
    student = db.session.get(Student, student_pk)
    if not student or student.school_id != current_user.school_id:
        flash('Student not found.', 'danger')
        return redirect(url_for('students.list_students'))

    try:
        student_name = student.full_name
        student_sid = student.student_id

        # Delete associated payments first
        payment_count = Payment.query.filter_by(
            student_id=student.id,
            school_id=current_user.school_id
        ).delete()

        audit = AuditLog(
            user_id=current_user.id,
            action=(
                f'Deleted student {student_name} (ID: {student_sid}) '
                f'and {payment_count} associated payments'
            )
        )
        db.session.add(audit)
        db.session.delete(student)
        db.session.commit()

        flash(
            f'Student "{student_name}" and {payment_count} '
            f'payment record(s) deleted successfully.',
            'success'
        )
    except Exception as e:
        db.session.rollback()
        logger.error('Student deletion failed: %s', e)
        flash('Failed to delete student. Please try again.', 'danger')

    return redirect(url_for('students.list_students'))
