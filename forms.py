from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    native_language = SelectField('Native Language', choices=[
        ('English', 'English'), ('Spanish', 'Spanish'),
        ('French', 'French'), ('German', 'German'),
        ('Chinese', 'Chinese'), ('Japanese', 'Japanese')
    ])
    target_language = SelectField('Target Language', choices=[
        ('Spanish', 'Spanish'), ('French', 'French'),
        ('German', 'German'), ('Italian', 'Italian'),
        ('Japanese', 'Japanese'), ('Korean', 'Korean')
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class VocabularyForm(FlaskForm):
    word = StringField('Word', validators=[DataRequired()])
    translation = StringField('Translation', validators=[DataRequired()])
    context = StringField('Context/Sentence')
    proficiency = IntegerField('Proficiency (0-5)', default=0)
    submit = SubmitField('Add Word')

    def validate_proficiency(self, proficiency):
        if proficiency.data < 0 or proficiency.data > 5:
            raise ValidationError('Proficiency must be between 0 and 5.')