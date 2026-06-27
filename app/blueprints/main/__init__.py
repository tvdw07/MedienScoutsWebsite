from flask import Blueprint

bp_main = Blueprint('main', __name__)

from . import account, pages, tickets  # noqa: E402,F401

