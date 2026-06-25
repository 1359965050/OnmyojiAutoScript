# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json
from fastapi import APIRouter, Body
from pathlib import Path

from module.config.utils import write_file
from module.logger import logger
from module.ocr.rpc import shutdown_ocr_server
from module.server.main_manager import MainManager
from module.server.updater import Updater
from module.server.i18n import I18n

home_app = APIRouter(
    prefix="/home",
    tags=["home"],
)


@home_app.get('/test')
async def home_test():
    return {'message': 'test'}


#  gcc -Wall -pedantic -shared -fPIC -o group_work.so group_work.c -lwiringPi
@home_app.get('/home_menu')
async def home_menu():
    return {'Home': [], 'Updater': []}


@home_app.get('/kill_server')
async def kill_server():
    shutdown_ocr_server()
    MainManager.signal_kill_server = True
    return 'success'


@home_app.get('/update_info')
async def update_info():
    try:
        updater = Updater()
        result = updater.get_update_info()
        result['branch'] = updater.current_branch()
        return result
    except Exception as e:
        logger.error(e)
        return None


@home_app.get('/execute_update')
async def execute_update():
    # 下拉仓库 -> 关闭所有脚本进程 -> 最后重启oasx
    try:
        updater = Updater()
        success = updater.execute_pull()
        if success:
            return '更新成功，请重启 OASX。'
        return '更新失败，请检查网络或 git 配置。'
    except Exception as e:
        logger.error(e)
        return f'更新异常: {e}'


@home_app.put('/chinese_translate')
async def chinese_translate(data: dict = Body(...)):
    try:
        I18n.save_zh_cn(data)
    except Exception as e:
        logger.error(e)
    return True


@home_app.get('/additional_translate')
async def additional_translate() -> dict:
    try:
        data = I18n.load_additions()
        return data
    except Exception as e:
        logger.error(e)
    return {}
