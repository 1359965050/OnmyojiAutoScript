import re


def build_error_log_dir_name(config_name: str, timestamp_ms: int) -> str:
    """
    用统一规则生成错误日志目录名。

    目录格式为 ``<script_name>_<timestamp_ms>``，脚本名会先被净化，
    替换掉文件系统非法字符，避免路径注入。
    """
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', config_name)
    safe_name = safe_name.strip('. ')
    return f'{safe_name}_{timestamp_ms}'
