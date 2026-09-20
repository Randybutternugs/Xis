"""The one rule for a request's client address.

App Engine's front end sets ``remote_addr`` to the real client. The
``X-Forwarded-For`` header can be supplied by the client itself, so
trusting its first value lets a caller pick the address we record,
rate-limit on, or compare against.
"""

from flask import request


def client_ip():
    return request.remote_addr or '0.0.0.0'
