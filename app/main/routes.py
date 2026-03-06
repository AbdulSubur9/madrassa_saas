"""Main application routes (dashboard, landing page)."""

from datetime import date
from flask import render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import Student, Payment, School
from app.main import main_bp
from app.utils import get_week_number


@main_bp.route('/')
def index():
    """Landing page - redirect to dashboard if logged in."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with analytics."""
    if current_user.is_super_admin:
        return _super_admin_dashboard()
    return _school_dashboard()


def _super_admin_dashboard():
    """Dashboard for super admin - overview of all schools."""
    total_schools = School.query.count()
    total_students = Student.query.count()
    total_payments_today = Payment.query.filter_by(payment_date=date.today()).count()

    today_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter_by(payment_date=date.today()).scalar()

    schools = School.query.all()
    school_data = []
    for school in schools:
        student_count = Student.query.filter_by(school_id=school.id, status='active').count()
        payment_count = Payment.query.filter_by(school_id=school.id).count()
        school_data.append({
            'id': school.id,
            'name': school.name,
            'students': student_count,
            'payments': payment_count
        })

    return render_template('dashboard_super.html',
                           total_schools=total_schools,
                           total_students=total_students,
                           total_payments_today=total_payments_today,
                           today_revenue=today_revenue,
                           school_data=school_data)


def _school_dashboard():
    """Dashboard for school-level users."""
    school_id = current_user.school_id
    today = date.today()
    current_week = get_week_number(today)
    current_year = today.year
    current_month = today.strftime('%B')

    # Total active students
    total_students = Student.query.filter_by(school_id=school_id, status='active').count()

    # Today's payments
    total_payments_today = Payment.query.filter_by(
        school_id=school_id, payment_date=today
    ).count()

    today_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.school_id == school_id,
        Payment.payment_date == today
    ).scalar()

    # Weekly revenue
    weekly_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.school_id == school_id,
        Payment.week_number == current_week,
        Payment.year == current_year
    ).scalar()

    # Monthly revenue
    monthly_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.school_id == school_id,
        Payment.month == current_month,
        Payment.year == current_year
    ).scalar()

    # Yearly revenue
    yearly_revenue = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.school_id == school_id,
        Payment.year == current_year
    ).scalar()

    # Defaulters count (students who haven't paid this week)
    paid_this_week = db.session.query(Payment.student_id).filter(
        Payment.school_id == school_id,
        Payment.week_number == current_week,
        Payment.year == current_year
    ).distinct().count()

    defaulters_count = max(0, total_students - paid_this_week)

    # Recent payments
    recent_payments = db.session.query(Payment, Student).join(
        Student, Payment.student_id == Student.id
    ).filter(
        Payment.school_id == school_id
    ).order_by(Payment.created_at.desc()).limit(10).all()

    school = db.session.get(School, school_id)

    return render_template('dashboard.html',
                           school=school,
                           total_students=total_students,
                           total_payments_today=total_payments_today,
                           today_revenue=today_revenue,
                           weekly_revenue=weekly_revenue,
                           monthly_revenue=monthly_revenue,
                           yearly_revenue=yearly_revenue,
                           defaulters_count=defaulters_count,
                           recent_payments=recent_payments,
                           current_week=current_week)


@main_bp.route('/api/chart/weekly')
@login_required
def chart_weekly():
    """API endpoint for weekly payment trend chart data."""
    school_id = current_user.school_id
    current_year = date.today().year

    # Get weekly totals for the current year
    results = db.session.query(
        Payment.week_number,
        func.sum(Payment.amount),
        func.count(Payment.id)
    ).filter(
        Payment.school_id == school_id,
        Payment.year == current_year
    ).group_by(Payment.week_number).order_by(Payment.week_number).all()

    labels = [f"Week {r[0]}" for r in results]
    amounts = [float(r[1]) for r in results]
    counts = [int(r[2]) for r in results]

    return jsonify({
        'labels': labels,
        'amounts': amounts,
        'counts': counts
    })


@main_bp.route('/api/chart/monthly')
@login_required
def chart_monthly():
    """API endpoint for monthly revenue chart data."""
    school_id = current_user.school_id
    current_year = date.today().year

    months_order = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    results = db.session.query(
        Payment.month,
        func.sum(Payment.amount),
        func.count(Payment.id)
    ).filter(
        Payment.school_id == school_id,
        Payment.year == current_year
    ).group_by(Payment.month).all()

    # Build ordered data
    month_data = {r[0]: {'amount': float(r[1]), 'count': int(r[2])} for r in results}

    labels = []
    amounts = []
    counts = []
    for m in months_order:
        if m in month_data:
            labels.append(m[:3])
            amounts.append(month_data[m]['amount'])
            counts.append(month_data[m]['count'])
        else:
            labels.append(m[:3])
            amounts.append(0)
            counts.append(0)

    return jsonify({
        'labels': labels,
        'amounts': amounts,
        'counts': counts
    })
