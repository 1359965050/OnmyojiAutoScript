# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import random
import re

from module.logger import logger
from module.atom.image import RuleImage
from tasks.GameUi.default_pages import page_shirin

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import GuildStore
from tasks.RichMan.page import page_guild_store


class Guild(Buy, GameUi, RichManAssets):

    def _default_detect_categories(self) -> set[str]:
        categories = super()._default_detect_categories()
        categories.add("guild")
        return categories

    def execute_guild(self, con: GuildStore = None):
        if not con.enable:
            return
        logger.hr('Start guild', 1)
        self.goto_page(page_guild_store)
        logger.info('Enter guild store success')
        time.sleep(0.5)

        items = [
            *([(self.I_GUILD_HONOR_GIFT, self._guild_honor_gift)] if con.honor_gift else []),
            *([(self.I_GUILD_BLUE, self._guild_mystery_amulet)] if con.mystery_amulet else []),
            *([(self.I_GUILD_SCRAP, self._guild_black_daruma_scrap)] if con.black_daruma_scrap else []),
            *([(self.I_GUILD_SKIN, lambda: self._guild_skin_ticket(con.skin_ticket))] if con.skin_ticket else []),
        ]

        swipe_no_progress = 0
        while items:
            self.screenshot()
            bought_this_round = False
            for item in list(items):
                button, func = item
                if not self.appear(button):
                    continue
                try:
                    res = func()
                    items.remove(item)
                    if res:
                        bought_this_round = True
                        swipe_no_progress = 0
                except Exception as e:
                    logger.warning(f'Button {button.name} click failed: {e}')
                break

            if not items:
                logger.info('All target items have been processed')
                break

            # 刚购买成功: 先等待界面稳定并重新识别, 视野内还有商品就继续买, 不要急着滑动
            if bought_this_round:
                time.sleep(1)
                continue

            # 连续多次滑动都没有买到东西, 防止无限滑动触发点击保护
            swipe_no_progress += 1
            if swipe_no_progress >= 8:
                logger.warning(f'Swipe {swipe_no_progress} times without buying, stop guild store')
                break

            if self.swipe(self.S_GUILD_STORE, interval=1.5):
                time.sleep(2)
                continue

        # 回去
        self.goto_page(page_shirin)

    def _guild_honor_gift(self):
        # 功勋礼包
        logger.hr('Guild honor gift', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 210):
            return False
        number = self.check_remain(self.I_GUILD_HONOR_GIFT)
        if number == 0:
            logger.warning('No honor gift can buy')
            return False
        self.buy_more(self.I_GUILD_HONOR_GIFT)
        time.sleep(0.5)
        return True

    def _guild_mystery_amulet(self):
        # 蓝票
        logger.hr('Guild mystery amulet', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 240):
            return False
        number = self.check_remain(self.I_GUILD_BLUE)
        if number == 0:
            logger.warning('No mystery amulet can buy')
            return False
        self.buy_more(self.I_GUILD_BLUE, number)
        time.sleep(0.5)
        return True

    def _guild_black_daruma_scrap(self):
        # 黑碎
        logger.hr('Guild black daruma scrap', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 200):
            return False
        number = self.check_remain(self.I_GUILD_SCRAP)
        if number == 0:
            logger.warning('No black daruma can buy')
            return False
        self.buy_one(self.I_GUILD_SCRAP, self.I_GUILD_CHECK_SCRAP)
        time.sleep(0.5)
        return True

    def _guild_skin_ticket(self, num: int = 0):
        # 皮肤券
        logger.hr('Guild skin ticket', 2)
        if num == 0:
            logger.warning('No buy skin ticket')
            return False
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 50):
            return False
        # 检查功勋商店皮肤券 本周剩余数量
        number = self.check_remain(self.I_GUILD_SKIN)
        if number == 0:
            logger.warning('No skin ticket can buy')
            return False
        # 购买功勋商店皮肤券
        buy_num = min(num, number) if num > 0 else number
        self.buy_more(self.I_GUILD_SKIN, buy_num)
        time.sleep(0.5)
        return True

    def check_remain(self, image: RuleImage) -> int:
        self.O_GUILD_REMAIN.roi[0] = image.roi_front[0] - 38
        self.O_GUILD_REMAIN.roi[1] = image.roi_front[1] + 83
        logger.info(f'Image roi {image.roi_front}')
        logger.info(f'GUILD REMAIN roi {self.O_GUILD_REMAIN.roi}')
        self.screenshot()
        result = self.O_GUILD_REMAIN.ocr(self.device.image)
        logger.warning(result)
        result = result.replace('？', '2').replace('?', '2').replace(':', '；')
        try:
            result = re.findall(r'本周[剩刺][余条]数量(\d+)', result)[0]
            result = int(result)
        except:
            result = 0
        logger.info('Remain: %s' % result)
        return int(result)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('日常1')
    d = Device(c)
    t = Guild(c, d)

    # t._guild_skin_ticket(5)
    t._guild_honor_gift()

