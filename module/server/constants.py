# This Python file uses the following encoding: utf-8
"""
OAS web service shared constants.
This module contains only pure constants to avoid circular imports.
"""
from pathlib import Path

# FastAPI application metadata
APP_TITLE = 'OAS'
APP_DESCRIPTION = 'OAS web service'
APP_VERSION = '0.0.0'

# CORS middleware configuration
CORS_ALLOW_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# Router prefixes and OpenAPI tags
HOME_ROUTER_PREFIX = "/home"
HOME_ROUTER_TAGS = ["home"]

# Common HTTP status codes
HTTP_400_BAD_REQUEST = 400
HTTP_404_NOT_FOUND = 404
HTTP_500_INTERNAL_SERVER_ERROR = 500

# API log configuration
API_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "log" / "api"
MAX_API_LOG_FILES = 30
MAX_API_LOG_SIZE = 5 * 1024 * 1024
