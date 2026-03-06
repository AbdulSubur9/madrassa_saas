"""Student management forms."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class StudentForm(FlaskForm):
    """Form for creating/editing a student."""

    student_id = StringField('Student ID', validators=[
        DataRequired(),
        Length(min=1, max=50)
    ])
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    gender = SelectField('Gender', choices=[
        ('Male', 'Male'),
        ('Female', 'Female')
    ], validators=[DataRequired()])
    class_id = SelectField('Class', coerce=int, validators=[Optional()])
    guardian_name = StringField('Guardian Name', validators=[
        Optional(),
        Length(max=200)
    ])
    guardian_phone = StringField('Guardian Phone', validators=[
        Optional(),
        Length(max=20)
    ])
    submit = SubmitField('Save Student')


class ClassForm(FlaskForm):
    """Form for creating a class."""

    class_name = StringField('Class Name', validators=[
        DataRequired(),
        Length(min=1, max=100)
    ])
    submit = SubmitField('Create Class')
