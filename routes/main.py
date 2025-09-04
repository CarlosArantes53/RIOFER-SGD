from flask import Blueprint, render_template, redirect, url_for, request, flash
from decorators import login_required, roles_required
from datetime import date

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
@login_required
def home():
    return render_template('home.html')
