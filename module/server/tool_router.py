# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from fastapi import APIRouter

from module.server.api_logger import ApiLoggingRoute

tool_app = APIRouter(
    prefix="/tool",
    tags=["tool"],
    route_class=ApiLoggingRoute,
)
