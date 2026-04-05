"""Payment recording routes."""

import logging
from datetime import date, datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, jsonify, current_app)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Payment, Student, School, SchoolClass, AuditLog, User
from app.utils import (role_required, get_week_number,
                       generate_receipt_number, generate_pdf_receipt)

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__, template_folder='../templates')


@payments_bp.route('/')
@login_required
@role_required('super_admin', 'school_admin', 'collector', 'accountant')
def list_payments():
    """List recent payments for the current school."""
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '', type=str)
    week_filter = request.args.get('week', 0, type=int)
    collector_filter = request.args.get('collector', 0, type=int)

    query = Payment.query.filter_by(school_id=current_user.school_id)

    # Collector can only see their own payments
    if current_user.is_collector:
        query = query.filter_by(recorded_by=current_user.id)

    # Admin filter by collector
    if collector_filter and not current_user.is_collector:
        query = query.filter_by(recorded_by=collector_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(payment_date=filter_date)
        except ValueError:
            pass

    if week_filter:
        current_year = date.today().year
        query = query.filter_by(week_number=week_filter, year=current_year)

    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    # Get collectors for filter dropdown (admin only)
    collectors = []
    if not current_user.is_collector:
        collectors = User.query.filter(
            User.school_id == current_user.school_id,
            User.role.in_([User.ROLE_COLLECTOR, User.ROLE_SCHOOL_ADMIN])
        ).order_by(User.full_name).all()

    return render_template('payments.html', payments=payments,
                           date_filter=date_filter, week_filter=week_filter,
                           collector_filter=collector_filter,
                           collectors=collectors)


@payments_bp.route('/record', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'school_admin', 'collector')
def record_payment():
    """Record a new payment."""
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).order_by(SchoolClass.class_name).all()

    if request.method == 'POST':
        try:
            student_pk = request.form.get('student_id', type=int)
            amount = request.form.get('amount', 5.0, type=float)
            payment_date_str = request.form.get('payment_date', '')

            if not student_pk:
                flash('Please select a student.', 'danger')
                students = Student.query.filter_by(
                    school_id=current_user.school_id, status='active'
                ).order_by(Student.full_name).all()
                return render_template(
                    'record_payment.html', students=students,
                    classes=classes, default_amount=5.0,
                    today=date.today().strftime('%Y-%m-%d')
                )

            student = db.session.get(Student, student_pk)
            if not student or student.school_id != current_user.school_id:
                flash('Student not found.', 'danger')
                return redirect(url_for('payments.record_payment'))

            # Parse payment date
            if payment_date_str:
                try:
                    pay_date = datetime.strptime(
                        payment_date_str, '%Y-%m-%d'
                    ).date()
                except ValueError:
                    pay_date = date.today()
            else:
                pay_date = date.today()

            week_num = get_week_number(pay_date)
            year = pay_date.year
            month = pay_date.strftime('%B')

            # Check for duplicate payment
            existing = Payment.query.filter_by(
                school_id=current_user.school_id,
                student_id=student.id,
                week_number=week_num,
                year=year
            ).first()

            if existing:
                flash(
                    f'Payment already recorded for {student.full_name} '
                    f'in week {week_num} of {year}. '
                    f'Receipt: {existing.receipt_number}',
                    'warning'
                )
                return redirect(url_for('payments.record_payment'))

            receipt_number = generate_receipt_number()

            payment = Payment(
                school_id=current_user.school_id,
                student_id=student.id,
                amount=amount,
                payment_date=pay_date,
                week_number=week_num,
                month=month,
                year=year,
                receipt_number=receipt_number,
                recorded_by=current_user.id
            )

            db.session.add(payment)

            audit = AuditLog(
                user_id=current_user.id,
                action=(
                    f'Recorded payment for {student.full_name}: '
                    f'GH\u20b5{amount:.2f} '
                    f'(Receipt: {receipt_number})'
                )
            )
            db.session.add(audit)
            db.session.commit()

            # Generate PDF receipt (non-blocking)
            try:
                school = db.session.get(School, current_user.school_id)
                generate_pdf_receipt(payment, student, school)
            except Exception as e:
                logger.error('Failed to generate PDF receipt: %s', e)

            flash(
                f'Payment of GH\u20b5{amount:.2f} recorded for '
                f'{student.full_name}. Receipt: {receipt_number}',
                'success'
            )
            return redirect(url_for('payments.payment_receipt',
                                    payment_id=payment.id))

        except IntegrityError:
            db.session.rollback()
            logger.warning(
                'Duplicate payment attempt by user %s',
                current_user.username
            )
            flash(
                'Duplicate payment detected for this student this week.',
                'danger'
            )
            return redirect(url_for('payments.record_payment'))
        except Exception as e:
            db.session.rollback()
            logger.error('Payment recording failed: %s', e)
            flash(
                'Payment failed, please try again. '
                'If the problem persists, contact your administrator.',
                'danger'
            )
            return redirect(url_for('payments.record_payment'))

    # GET request - load students
    students = Student.query.filter_by(
        school_id=current_user.school_id, status='active'
    ).order_by(Student.full_name).all()

    return render_template('record_payment.html', students=students, classes=classes,
                           default_amount=5.0, today=date.today().strftime('%Y-%m-%d'))


@payments_bp.route('/bulk-record', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'school_admin', 'collector')
def bulk_record():
    """Record payments for multiple students at once (e.g., a whole class)."""
    classes = SchoolClass.query.filter_by(school_id=current_user.school_id).order_by(SchoolClass.class_name).all()

    if request.method == 'POST':
        try:
            student_ids = request.form.getlist('student_ids', type=int)
            amount = request.form.get('amount', 5.0, type=float)
            payment_date_str = request.form.get('payment_date', '')

            if not student_ids:
                flash('Please select at least one student.', 'warning')
                return render_template(
                    'bulk_payment.html', classes=classes,
                    default_amount=5.0,
                    today=date.today().strftime('%Y-%m-%d')
                )

            if payment_date_str:
                try:
                    pay_date = datetime.strptime(
                        payment_date_str, '%Y-%m-%d'
                    ).date()
                except ValueError:
                    pay_date = date.today()
            else:
                pay_date = date.today()

            week_num = get_week_number(pay_date)
            year = pay_date.year
            month = pay_date.strftime('%B')
            school = db.session.get(School, current_user.school_id)

            success_count = 0
            skip_count = 0

            for sid in student_ids:
                student = db.session.get(Student, sid)
                if (not student
                        or student.school_id != current_user.school_id):
                    continue

                # Check for duplicate
                existing = Payment.query.filter_by(
                    school_id=current_user.school_id,
                    student_id=student.id,
                    week_number=week_num,
                    year=year
                ).first()

                if existing:
                    skip_count += 1
                    continue

                receipt_number = generate_receipt_number()
                payment = Payment(
                    school_id=current_user.school_id,
                    student_id=student.id,
                    amount=amount,
                    payment_date=pay_date,
                    week_number=week_num,
                    month=month,
                    year=year,
                    receipt_number=receipt_number,
                    recorded_by=current_user.id
                )
                db.session.add(payment)
                success_count += 1

                # Generate PDF receipt
                try:
                    db.session.flush()
                    generate_pdf_receipt(payment, student, school)
                except Exception as e:
                    logger.error('Bulk receipt error: %s', e)

            if success_count > 0:
                audit = AuditLog(
                    user_id=current_user.id,
                    action=(
                        f'Bulk recorded {success_count} payments '
                        f'for week {week_num}'
                    )
                )
                db.session.add(audit)

            db.session.commit()

            flash(
                f'{success_count} payments recorded. '
                f'{skip_count} skipped (duplicates).',
                'success'
            )
            return redirect(url_for('payments.list_payments'))

        except Exception as e:
            db.session.rollback()
            logger.error('Bulk payment recording failed: %s', e)
            flash('Bulk payment failed, please try again.', 'danger')
            return redirect(url_for('payments.bulk_record'))

    return render_template(
        'bulk_payment.html', classes=classes,
        default_amount=5.0,
        today=date.today().strftime('%Y-%m-%d')
    )


@payments_bp.route('/search-students')
@login_required
@role_required('super_admin', 'school_admin', 'collector')
def search_students():
    """API endpoint to search students by name or ID (for AJAX)."""
    from flask import jsonify
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    students = Student.query.filter(
        Student.school_id == current_user.school_id,
        Student.status == 'active',
        db.or_(
            Student.full_name.ilike(f'%{query}%'),
            Student.student_id.ilike(f'%{query}%')
        )
    ).order_by(Student.full_name).limit(20).all()

    return jsonify([{
        'id': s.id,
        'student_id': s.student_id,
        'full_name': s.full_name,
        'class_name': s.school_class.class_name if s.school_class else 'N/A'
    } for s in students])


@payments_bp.route('/get-students/<int:class_id>')
@login_required
@role_required('super_admin', 'school_admin', 'collector')
def get_students_by_class(class_id):
    """API endpoint to get students by class (for AJAX)."""
    students = Student.query.filter_by(
        school_id=current_user.school_id,
        class_id=class_id,
        status='active'
    ).order_by(Student.full_name).all()

    return jsonify([{
        'id': s.id,
        'student_id': s.student_id,
        'full_name': s.full_name
    } for s in students])


@payments_bp.route('/<int:payment_id>/receipt')
@login_required
def payment_receipt(payment_id):
    """View a payment receipt."""
    payment = db.session.get(Payment, payment_id)
    if not payment:
        flash('Payment not found.', 'danger')
        return redirect(url_for('payments.list_payments'))

    # School isolation
    if (not current_user.is_super_admin
            and payment.school_id != current_user.school_id):
        flash('Access denied.', 'danger')
        return redirect(url_for('payments.list_payments'))

    student = db.session.get(Student, payment.student_id)
    school = db.session.get(School, payment.school_id)

    return render_template('receipt.html', payment=payment,
                           student=student, school=school)


@payments_bp.route('/<int:payment_id>/download-receipt')
@login_required
def download_receipt(payment_id):
    """Download the PDF receipt."""
    import os

    payment = db.session.get(Payment, payment_id)
    if not payment:
        flash('Payment not found.', 'danger')
        return redirect(url_for('payments.list_payments'))

    if (not current_user.is_super_admin
            and payment.school_id != current_user.school_id):
        flash('Access denied.', 'danger')
        return redirect(url_for('payments.list_payments'))

    filepath = os.path.join(
        current_app.config['RECEIPTS_FOLDER'],
        f'{payment.receipt_number}.pdf'
    )

    if not os.path.exists(filepath):
        # Regenerate receipt
        try:
            student = db.session.get(Student, payment.student_id)
            school = db.session.get(School, payment.school_id)
            filepath = generate_pdf_receipt(payment, student, school)
        except Exception as e:
            logger.error('Receipt regeneration failed: %s', e)
            flash('Could not generate receipt.', 'danger')
            return redirect(url_for('payments.list_payments'))

    return send_file(filepath, as_attachment=True,
                     download_name=f'receipt_{payment.receipt_number}.pdf')


@payments_bp.route('/<int:payment_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def delete_payment(payment_id):
    """Delete a payment record (admin only)."""
    payment = db.session.get(Payment, payment_id)
    if not payment:
        flash('Payment not found.', 'danger')
        return redirect(url_for('payments.list_payments'))

    # School isolation
    if (not current_user.is_super_admin
            and payment.school_id != current_user.school_id):
        flash('Access denied.', 'danger')
        return redirect(url_for('payments.list_payments'))

    try:
        receipt_num = payment.receipt_number
        student = db.session.get(Student, payment.student_id)
        student_name = student.full_name if student else 'Unknown'

        audit = AuditLog(
            user_id=current_user.id,
            action=(
                f'Deleted payment {receipt_num} '
                f'for {student_name}'
            )
        )
        db.session.add(audit)
        db.session.delete(payment)
        db.session.commit()

        flash(f'Payment {receipt_num} deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Payment deletion failed: %s', e)
        flash('Failed to delete payment. Please try again.', 'danger')

    return redirect(url_for('payments.list_payments'))


@payments_bp.route('/collector-summary')
@login_required
@role_required('super_admin', 'school_admin')
def collector_summary():
    """View payment totals per collector."""
    from sqlalchemy import func

    results = db.session.query(
        User.id,
        User.full_name,
        User.username,
        func.count(Payment.id).label('payment_count'),
        func.coalesce(func.sum(Payment.amount), 0).label('total_amount')
    ).join(
        Payment, Payment.recorded_by == User.id
    ).filter(
        Payment.school_id == current_user.school_id
    ).group_by(User.id, User.full_name, User.username).all()

    collectors = []
    for r in results:
        collectors.append({
            'id': r[0],
            'full_name': r[1],
            'username': r[2],
            'payment_count': r[3],
            'total_amount': float(r[4])
        })

    return render_template('collector_summary.html',
                           collectors=collectors)
