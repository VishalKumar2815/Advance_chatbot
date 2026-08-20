import email_validator
from flask_wtf import FlaskForm
from wtforms import StringField,EmailField,PasswordField,SubmitField
from wtforms.validators import  DataRequired,Email,Length




class RegistrationForm(FlaskForm):
    name=StringField("Full Name",validators=[DataRequired(message="Enter your full name!")])
    email=StringField("Email Id",validators=[DataRequired(message="Enter valid email id!"),Email()])
    password=PasswordField("Create Password",validators=[DataRequired(message="Create strong password"),Length(min=6)])
    submit=SubmitField("Register")


class LoginForm(FlaskForm):
    Email=StringField("Email Id",validators=[DataRequired(),Email()])
    Password=PasswordField("Enter your password",validators=[DataRequired(),Length(min=6)])
    submit = SubmitField("Login")


class ChangePass(FlaskForm):
    old_pass=PasswordField("Old password",validators=[DataRequired(message="Enter your old password")])
    new_pass=PasswordField("New password",validators=[DataRequired(message="Enter a new password"),Length(min=6,message="length should be more than 6 characters")])
    submit=SubmitField("Save changes")


