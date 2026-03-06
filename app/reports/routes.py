"""Reporting routes."""

import io
from datetime import date, datetime

import pandas as pd
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from app.extensions import db
from app.models import Payment, Student, School
from app.utils import role_required, get_week_number

reports_bp = Blueprint('reports', __name__, template_folder='../templates')


def _get_report_data(school_id, report_type, date_str=None, week=None, month=None, year=None):
    """Fetch report data based on filters.

    Returns:
        list[dict]: List of payment records with student info.
    """
    query = db.session.query(
        Payment, Student
    ).join(
        Student, Payment.student_id == Student.id
    ).filter(
        Payment.school_id == school_id
    )

    today = date.today()

    if report_type == 'daily':
        if date_str:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                report_date = today
        else:
            report_date = today
        query = query.filter(Payment.payment_date == report_date)

    elif report_type == 'weekly':
        target_week = week or get_week_number(today)
        target_year = year or today.year
        query = query.filter(
            Payment.week_number == target_week,
            Payment.year == target_year
        )

    elif report_type == 'monthly':
        target_month = month or today.strftime('%B')
        target_year = year or today.year
        query = query.filter(
            Payment.month == target_month,
            Payment.year == target_year
        )

    results = query.order_by(Payment.payment_date.desc()).all()

    data = []
    for payment, student in results:
        data.append({
            'receipt_number': payment.receipt_number,
            'student_id': student.student_id,
            'student_name': student.full_name,
            'amount': payment.amount,
            'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
            'week_number': payment.week_number,
            'month': payment.month,
            'year': payment.year
        })

    return data


@reports_bp.route('/')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def reports_home():
    """Reports home page with filter options."""
    today = date.today()
    current_week = get_week_number(today)
    current_month = today.strftime('%B')
    current_year = today.year

    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    return render_template('reports.html',
                           today=today.strftime('%Y-%m-%d'),
                           current_week=current_week,
                           current_month=current_month,
                           current_year=current_year,
                           months=months)


@reports_bp.route('/generate')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def generate_report():
    """Generate a report based on filters."""
    report_type = request.args.get('type', 'daily')
    date_str = request.args.get('date', '')
    week = request.args.get('week', type=int)
    month = request.args.get('month', '')
    year = request.args.get('year', type=int)

    data = _get_report_data(
        current_user.school_id, report_type,
        date_str=date_str, week=week, month=month, year=year
    )

    total_amount = sum(item['amount'] for item in data)
    school = db.session.get(School, current_user.school_id)

    # Build report title
    if report_type == 'daily':
        title = f"Daily Report - {date_str or date.today().strftime('%Y-%m-%d')}"
    elif report_type == 'weekly':
        title = f"Weekly Report - Week {week or get_week_number()}, {year or date.today().year}"
    else:
        title = f"Monthly Report - {month or date.today().strftime('%B')} {year or date.today().year}"

    return render_template('report_result.html', data=data, total_amount=total_amount,
                           school=school, title=title, report_type=report_type,
                           date_str=date_str, week=week, month=month, year=year)


@reports_bp.route('/export/csv')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def export_csv():
    """Export report data as CSV."""
    report_type = request.args.get('type', 'daily')
    date_str = request.args.get('date', '')
    week = request.args.get('week', type=int)
    month = request.args.get('month', '')
    year = request.args.get('year', type=int)

    data = _get_report_data(
        current_user.school_id, report_type,
        date_str=date_str, week=week, month=month, year=year
    )

    if not data:
        data = [{'receipt_number': '', 'student_id': '', 'student_name': '',
                 'amount': 0, 'payment_date': '', 'week_number': '', 'month': '', 'year': ''}]

    df = pd.DataFrame(data)
    df.columns = ['Receipt #', 'Student ID', 'Student Name', 'Amount (GH\u20b5)',
                  'Payment Date', 'Week', 'Month', 'Year']

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8')
    buffer.seek(0)

    filename = f"report_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=filename)


@reports_bp.route('/export/excel')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def export_excel():
    """Export report data as Excel."""
    report_type = request.args.get('type', 'daily')
    date_str = request.args.get('date', '')
    week = request.args.get('week', type=int)
    month = request.args.get('month', '')
    year = request.args.get('year', type=int)

    data = _get_report_data(
        current_user.school_id, report_type,
        date_str=date_str, week=week, month=month, year=year
    )

    if not data:
        data = [{'receipt_number': '', 'student_id': '', 'student_name': '',
                 'amount': 0, 'payment_date': '', 'week_number': '', 'month': '', 'year': ''}]

    df = pd.DataFrame(data)
    df.columns = ['Receipt #', 'Student ID', 'Student Name', 'Amount (GH\u20b5)',
                  'Payment Date', 'Week', 'Month', 'Year']

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    buffer.seek(0)

    filename = f"report_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@reports_bp.route('/export/pdf')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def export_pdf():
    """Export report data as PDF."""
    report_type = request.args.get('type', 'daily')
    date_str = request.args.get('date', '')
    week = request.args.get('week', type=int)
    month = request.args.get('month', '')
    year = request.args.get('year', type=int)

    data = _get_report_data(
        current_user.school_id, report_type,
        date_str=date_str, week=week, month=month, year=year
    )

    school = db.session.get(School, current_user.school_id)

    # Build title
    if report_type == 'daily':
        title = f"Daily Report - {date_str or date.today().strftime('%Y-%m-%d')}"
    elif report_type == 'weekly':
        title = f"Weekly Report - Week {week or get_week_number()}, {year or date.today().year}"
    else:
        title = f"Monthly Report - {month or date.today().strftime('%B')} {year or date.today().year}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []
    styles = getSampleStyleSheet()

    # Header
    elements.append(Paragraph(school.name if school else 'School Report', styles['Title']))
    elements.append(Paragraph(title, styles['Heading2']))
    elements.append(Spacer(1, 10 * mm))

    # Table data
    table_data = [['#', 'Receipt #', 'Student ID', 'Student Name', 'Amount (GH\u20b5)',
                   'Payment Date', 'Week', 'Month']]

    total = 0
    for idx, item in enumerate(data, 1):
        table_data.append([
            str(idx),
            item['receipt_number'],
            item['student_id'],
            item['student_name'],
            f"{item['amount']:.2f}",
            item['payment_date'],
            str(item['week_number']),
            item['month']
        ])
        total += item['amount']

    table_data.append(['', '', '', 'TOTAL', f"{total:.2f}", '', '', ''])

    # Create table
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5c2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f5e9')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | "
        f"Total Records: {len(data)} | Total Amount: GH\u20b5{total:.2f}",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)

    filename = f"report_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)


@reports_bp.route('/defaulters')
@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def defaulters_report():
    """Show students who haven't paid for the current week."""
    current_week = get_week_number()
    current_year = date.today().year
    week = request.args.get('week', current_week, type=int)
    year = request.args.get('year', current_year, type=int)

    # Get all active students
    all_students = Student.query.filter_by(
        school_id=current_user.school_id,
        status='active'
    ).all()

    # Get students who paid for the given week
    paid_student_ids = db.session.query(Payment.student_id).filter(
        Payment.school_id == current_user.school_id,
        Payment.week_number == week,
        Payment.year == year
    ).all()
    paid_ids = {sid for (sid,) in paid_student_ids}

    # Defaulters are active students who haven't paid
    defaulters = [s for s in all_students if s.id not in paid_ids]

    return render_template('defaulters.html', defaulters=defaulters,
                           week=week, year=year, total_active=len(all_students),
                           total_paid=len(paid_ids))
