# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import onepush.core
import yaml
from onepush import get_notifier
from onepush.core import Provider
from onepush.exceptions import OnePushException
from onepush.providers.custom import Custom
from requests import Response
from smtplib import SMTPResponseException

from module.logger import logger
onepush.core.log = logger


class Notifier:
    def __init__(self, _config: str = "", enable: bool = False) -> None:
        self.config_name: str = ""
        self.enable: bool = bool(enable)
        self.config: dict = {}
        self.provider_name: str | None = None
        self.notifier: Provider | None = None
        self.required: list[str] = []

        if not self.enable:
            return
        config: dict = {}
        try:
            for item in yaml.safe_load_all(_config or ""):
                if isinstance(item, dict):
                    config.update(item)
        except Exception:
            logger.error("Fail to load onepush config, skip sending")
            self.enable = False
            return
        if not config:
            logger.info("Empty onepush config, skip sending")
            self.enable = False
            return
        self.config = config
        try:
            # 获取provider
            self.provider_name = self.config.pop("provider", None)
            if not self.provider_name:
                logger.info("No provider specified, skip sending")
                self.enable = False
                return
            # 获取notifier
            self.notifier = get_notifier(self.provider_name)
            # 获取notifier的必填参数
            self.required = list(self.notifier.params.get("required", []))
        except OnePushException:
            logger.exception("Init notifier failed")
            self.enable = False
            return
        except Exception as e:
            logger.exception(e)
            self.enable = False
            return

    def push(self, **kwargs) -> bool:
        if not self.enable or self.notifier is None:
            return False
        payload = dict(self.config)
        # 更新本次推送标题与内容，不污染长期保存的 self.config
        req_kwargs = dict(kwargs)
        raw_title = str(req_kwargs.get("title", "") or "")
        req_kwargs["title"] = f"{self.config_name} {raw_title}".strip() if self.config_name else raw_title
        payload.update(req_kwargs)
        # pre check
        for key in self.required:
            if key not in payload:
                logger.warning(
                    f"Notifier {self.notifier} require param '{key}' but not provided"
                )

        if isinstance(self.notifier, Custom):
            if "method" not in payload or payload["method"] == "post":
                payload["datatype"] = "json"
            existing_data = payload.get("data")
            custom_data = dict(existing_data) if isinstance(existing_data, dict) else {}
            if "title" in req_kwargs:
                custom_data["title"] = req_kwargs["title"]
            if "content" in req_kwargs:
                custom_data["content"] = req_kwargs["content"]
            payload["data"] = custom_data

        if self.provider_name and self.provider_name.lower() == "gocqhttp":
            access_token = payload.get("access_token")
            if access_token:
                payload["token"] = access_token

        try:
            resp = self.notifier.notify(**payload)
            if isinstance(resp, Response):
                if resp.status_code != 200:
                    logger.warning("Push notify failed!")
                    logger.warning(f"HTTP Code:{resp.status_code}")
                    return False
                else:
                    if self.provider_name.lower() == "gocqhttp":
                        return_data: dict = resp.json()
                        if return_data["status"] == "failed":
                            logger.warning("Push notify failed!")
                            logger.warning(
                                f"Return message:{return_data['wording']}")
                            return False
        except SMTPResponseException:
            logger.warning("Appear SMTPResponseException")
            pass
        except OnePushException:
            logger.exception("Push notify failed")
            return False
        except Exception as e:
            logger.exception(e)
            return False

        logger.info("Push notify success")
        return True



