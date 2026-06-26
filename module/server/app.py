# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pathlib import Path
from contextlib import asynccontextmanager

import argparse
from starlette import status
from starlette.responses import JSONResponse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from module.logger import logger
from module.server.home_router import home_app
from module.server.script_router import script_app
from module.server.tool_router import tool_app
from module.server.api_logger import ApiLoggingMiddleware, api_logger
from module.server.setting import State
from module.server.main_manager import mm
from module.server.constants import (
    APP_TITLE, APP_DESCRIPTION, APP_VERSION,
    CORS_ALLOW_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS,
    ANNOTATOR_STATIC_PATH, HTTP_500_INTERNAL_SERVER_ERROR,
)
from starlette.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

app.add_middleware(ApiLoggingMiddleware)

app.include_router(home_app)
app.include_router(script_app)
app.include_router(tool_app)

annotator_static_dir = Path(__file__).resolve().parent / "web" / "annotator" / "static"
if annotator_static_dir.exists():
    app.mount(ANNOTATOR_STATIC_PATH, StaticFiles(directory=str(annotator_static_dir)), name="annotator_static")


async def on_startup():
    """
    app.state 的生命周期在定义app的时候就有了
    :return:
    """
    logger.info('OAS web service startup done')
    if app.state.script_instances:
        await mm.restart_processes(app.state.script_instances)


async def on_shutdown():
    logger.info('OAS web service shutdown done')


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: ", exc_info=True)

    message = ', '.join(str(arg) for arg in exc.args) if exc.args else str(exc)

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'message': message
        },
    )


def fastapi_app():
    parser = argparse.ArgumentParser(description="OAS web service")
    parser.add_argument(
        "-k", "--key", type=str, help="Password of OAS. No password by default"
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use jsdelivr cdn for pywebio static files (css, js). Self host cdn by default.",
    )
    parser.add_argument(
        "--run",
        nargs="+",
        type=str,
        help="Run OAS by config names on startup",
    )
    args, _ = parser.parse_known_args()
    # ------------------------------------------------------------------------------------------------------------------

    runs = None
    if args.run:
        runs = args.run
    elif State.deploy_config.Run:
        # TODO: refactor poor_yaml_read() to support list
        tmp = State.deploy_config.Run.split(",")
        runs = [l.strip(" ['\"]") for l in tmp if len(l)]
    # ------------------------------------------------------------------------------------------------------------------
    app.state.script_instances = runs

    return app
