# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from module.config.utils import convert_to_underscore

from module.logger import logger
from module.server.api_logger import ApiLoggingRoute, log_ws_event
from module.server.config_manager import (
    ConfigAlreadyExistsError,
    ConfigJsonError,
    ConfigManager,
    ConfigNameError,
    ConfigNotFoundError,
    ConfigTaskError,
    ConfigValidationError,
)
from module.exception import RequestHumanTakeover
from module.server.main_manager import mm
from module.server.script_process import ScriptProcess, ScriptState

from tasks.Component.config_base import TimeDelta


script_app = APIRouter(route_class=ApiLoggingRoute)


@script_app.get('/test')
async def script_test():
    return 'success'

@script_app.get('/script_menu')
def script_menu():
    return mm.config_cache('template').gui_menu_list
# ----------------------------------   配置文件管理   ----------------------------------
@script_app.get('/config_list')
def config_list():
    return mm.all_script_files()

@script_app.post('/config_copy')
def config_copy(file: str, template: str = 'template'):
    try:
        file = ConfigManager.validate_config_name(file, allow_template=False)
        template = ConfigManager.validate_config_name(template, allow_template=True)
        mm.copy(file, template)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    mm.add_script_file(file)
    return mm.all_script_files()

@script_app.get('/config_new_name')
def config_new_name():
    return mm.generate_script_name()

@script_app.get('/config_all')
def config_all():
    return mm.all_json_file()


@script_app.post('/config/import')
async def config_import(name: str = Form(...), file: UploadFile = File(...)):
    """
    导入脚本配置文件，上传文件名不会作为落盘名称。
    """
    try:
        raw = await file.read()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as e:
            raise ConfigJsonError(f'Config file must be UTF-8 JSON: {e}') from e
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigJsonError(f'Config JSON parse failed: {e}') from e

        config_name = await asyncio.to_thread(mm.import_config, name, data)
        mm.add_script_file(config_name)
        return {"name": config_name, "file": f"{config_name}.json"}
    except ConfigAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "fields": e.fields},
        )
    except (ConfigNameError, ConfigJsonError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.get('/config/export')
def config_export(name: str):
    """
    导出脱敏后的脚本配置文件。
    """
    try:
        config_name, data = mm.load_config_for_export(name)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConfigJsonError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redacted = ConfigManager.redact_config(data)
    content = json.dumps(redacted, indent=2, ensure_ascii=False, sort_keys=False, default=str)
    filename = f"{config_name}.json"
    quoted_filename = quote(filename, safe='')
    fallback_filename = "config.json"
    return Response(
        content=content,
        media_type='application/json; charset=utf-8',
        headers={
            'Content-Disposition': f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{quoted_filename}",
            'Cache-Control': 'no-store',
        },
    )


@script_app.post('/config/task/import')
async def config_task_import(
    config_name: str = Form(...),
    task_name: str = Form(...),
    json_text: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    """
    导入单个任务配置 JSON，内容必须是 {"task_key": {...}}。
    """
    try:
        file_content = await file.read() if file is not None else None
        data = await asyncio.to_thread(
            mm.parse_task_json_source, json_text=json_text, file_content=file_content
        )
        config_name, task_key = await asyncio.to_thread(
            mm.import_task_config, config_name, task_name, data
        )
        mm.invalidate_config_cache(config_name)
        return {
            "config_name": config_name,
            "task_name": task_key,
            "file": f"{config_name}.json",
            "updated": True,
        }
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "fields": e.fields},
        )
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.get('/config/task/export')
def config_task_export(config_name: str, task_name: str):
    """
    导出脱敏后的单个任务配置 JSON 文件。
    """
    try:
        config_name, task_key, data = mm.load_task_for_export(config_name, task_name)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
    filename = f"{config_name}-{task_key}.json"
    quoted_filename = quote(filename, safe='')
    fallback_filename = "task.json"
    return Response(
        content=content,
        media_type='application/json; charset=utf-8',
        headers={
            'Content-Disposition': f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{quoted_filename}",
            'Cache-Control': 'no-store',
        },
    )


@script_app.get('/config/task/copy-json')
def config_task_copy_json(config_name: str, task_name: str):
    """
    复制单个任务配置 JSON，返回未脱敏普通 JSON。
    """
    try:
        _, _, data = mm.load_task_for_transfer(config_name, task_name)
        return data
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConfigNameError, ConfigJsonError, ConfigTaskError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@script_app.put('/config')
async def config_rename(old_name: str = '', new_name: str = ''):
    """
    update config name
    :param old_name: old config name
    :param new_name: new config name
    :return: True or False
    """
    if old_name == '' or new_name == '':
        return False
    try:
        old_name = ConfigManager.validate_config_name(old_name, allow_template=False)
        new_name = ConfigManager.validate_config_name(new_name, allow_template=False)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if old_name == new_name:
        return False
    old_path = ConfigManager.config_path(old_name)
    new_path = ConfigManager.config_path(new_name)
    if not old_path.exists() or new_path.exists():
        raise HTTPException(status_code=400, detail='Rename failed')
    await mm.remove_script_process(old_name)
    mm.invalidate_config_cache(old_name)
    if not await asyncio.to_thread(mm.rename, old_name, new_name):
        raise HTTPException(status_code=400, detail='Rename failed')
    mm.invalidate_config_cache(new_name)
    mm.add_script_file(new_name)
    return True


@script_app.delete('/config')
async def config_delete(name: str = ''):
    """
    delete config file
    :param name: config name
    :return: True or False
    """
    try:
        name = ConfigManager.validate_config_name(name, allow_template=False)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ConfigManager.config_path(name).exists():
        raise HTTPException(status_code=400, detail='Delete failed')
    await mm.remove_script_process(name)
    mm.invalidate_config_cache(name)
    if not await asyncio.to_thread(mm.delete, name):
        raise HTTPException(status_code=400, detail='Delete failed')
    return True


@script_app.put('/config/task/copy')
def task_copy(task_name: str, dest_config_name: str, source_config_name: str):
    if dest_config_name not in mm.script_process or source_config_name not in mm.script_process:
        return False
    source_task = getattr(mm.config_cache(source_config_name).model, convert_to_underscore(task_name), None)
    if source_task is None:
        return False
    return mm.config_cache(dest_config_name).model.copy_script_task(task_name, source_task)


@script_app.put('/config/task/group/copy')
def task_group_copy(task_name: str, group_name: str, dest_config_name: str, source_config_name: str):
    if dest_config_name not in mm.script_process or source_config_name not in mm.script_process:
        return False
    source_task = getattr(mm.config_cache(source_config_name).model, convert_to_underscore(task_name), None)
    if source_task is None:
        return False
    return mm.config_cache(dest_config_name).model.copy_task_group(task_name, group_name, source_task)


# ---------------------------------   脚本实例管理   ----------------------------------
@script_app.get('/{script_name}/start')
async def script_start(script_name: str):
    try:
        script_name = ConfigManager.validate_config_name(script_name, allow_template=False)
    except ConfigNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if script_name not in mm.script_process:
        try:
            mm.script_process[script_name] = await asyncio.to_thread(ScriptProcess, script_name)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    await mm.script_process[script_name].start()
    mm.ensure_script_tasks(script_name)
    return

@script_app.get('/{script_name}/stop')
async def script_stop(script_name: str):
    if script_name not in mm.script_process:
        logger.warning(f'[{script_name}] script process does not exist')
        return
    await mm.script_process[script_name].stop()
    return

@script_app.get('/{script_name}/{task}/args')
def get_script_task(script_name: str, task: str):
    return mm.config_cache(script_name).model.script_task(task)

@script_app.put('/{script_name}/{task}/{group}/{argument}/value')
def set_script_task(script_name: str, task: str, group: str, argument: str, types: str, value):
    try:
        match types:
            case 'integer':
                value = int(value)
            case 'number':
                value = float(value)
            case 'boolean':
                if isinstance(value, bool):
                    pass
                elif isinstance(value, str):
                    logger.debug(f'[{script_name}] script argument {argument} value is string, try to convert to bool')
                    lower = value.strip().lower()
                    if lower in ('true', '1'):
                        value = True
                    elif lower in ('false', '0'):
                        value = False
                    else:
                        raise ValueError(f'Invalid boolean value: {value}')
                elif isinstance(value, (int, float)) and value in (0, 1):
                    value = bool(value)
                else:
                    raise ValueError(f'Invalid boolean value: {value}')
            case 'string':
                pass
            case 'date_time':
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            case 'time_delta':
                parts = str(value).strip().split()
                if len(parts) == 2:
                    day = int(parts[0])
                    date_time = datetime.strptime(parts[1], '%H:%M:%S')
                elif len(parts) == 1:
                    day = 0
                    date_time = datetime.strptime(parts[0], '%H:%M:%S')
                else:
                    raise ValueError(f'Invalid time_delta format: {value}')
                value = TimeDelta(days=day, hours=date_time.hour, minutes=date_time.minute, seconds=date_time.second)
            case 'time':
                value = datetime.strptime(value, '%H:%M:%S').time()
            case _:
                pass
    except Exception as e:
        # 类型不正确
        raise HTTPException(status_code=400, detail=f'Argument type error: {e}')
    return mm.config_cache(script_name).model.script_set_arg(task, group, argument, value)


def _safe_get_schedule_data(config) -> dict[str, dict]:
    try:
        config.update_scheduler()
        if config.pending_task or config.waiting_task:
            config.get_next()
    except RequestHumanTakeover:
        pass
    except Exception as e:
        logger.warning(f"Failed to update schedule data: {e}")
    return config.get_schedule_data()


@script_app.put('/{script_name}/{task}/sync_next_run')
async def sync_next_run(script_name: str, task: str, target_dt: str):
    if script_name not in mm.script_process:
        return False

    def _sync_and_build_schedule() -> dict[str, dict]:
        config = mm.config_cache(script_name)
        target = datetime.strptime(target_dt, '%Y-%m-%d %H:%M:%S') if target_dt else None
        config.task_delay(task=task, success=True, target=target)
        return _safe_get_schedule_data(config)

    schedule_data = await asyncio.to_thread(_sync_and_build_schedule)
    script_process = mm.script_process[script_name]
    await script_process.broadcast_state({"schedule": schedule_data})
    return True


# -------------------------------------- websocket --------------------------------------

@script_app.websocket("/ws/{script_name}")
async def websocket_endpoint(websocket: WebSocket, script_name: str):
    try:
        script_name = ConfigManager.validate_config_name(script_name)
        if script_name not in mm.script_process:
            mm.script_process[script_name] = await asyncio.to_thread(ScriptProcess, script_name)
    except (ConfigNameError, FileNotFoundError) as e:
        await websocket.close(code=1008, reason=str(e))
        return
    script_process = mm.script_process[script_name]
    await script_process.connect(websocket)
    log_ws_event(f"ws[{script_name}] connected")

    def _load_schedule(name: str) -> dict[str, dict]:
        config = mm.config_cache(name)
        return _safe_get_schedule_data(config)

    try:
        await script_process.send_json(websocket, {"state": script_process.state})
        log_ws_event(f"ws[{script_name}] connect state: {script_process.state}")
        schedule_data = await asyncio.to_thread(_load_schedule, script_name)
        await script_process.send_json(websocket, {"schedule": schedule_data})
        log_ws_event(f"ws[{script_name}] connect response: {schedule_data}")
        while True:
            # 初次进入，广播state schedule
            data = await websocket.receive_text()
            log_ws_event(f"ws[{script_name}] msg: {data}")
            if data == 'get_state':
                await script_process.send_json(websocket, {"state": script_process.state})
                log_ws_event(f"ws[{script_name}] response: {script_process.state}")
            elif data == 'get_schedule':
                schedule_data = await asyncio.to_thread(_load_schedule, script_name)
                await script_process.send_json(websocket, {"schedule": schedule_data})
                log_ws_event(f"ws[{script_name}] response: {schedule_data}")
            elif data == 'start':
                await script_process.start()
                mm.ensure_script_tasks(script_name)
            elif data == 'stop':
                await script_process.stop()

    except WebSocketDisconnect:
        log_ws_event(f"ws[{script_name}] disconnect", level="warning")
        await script_process.disconnect(websocket)
    except Exception as e:
        log_ws_event(f"ws[{script_name}] error: {type(e).__name__}: {e}", level="error")
        logger.exception(f'[{script_name}] websocket error: {e}')
        await script_process.disconnect(websocket)
