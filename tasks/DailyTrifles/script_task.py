# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from exceptiongroup import catch
from tasks.Component.config_base import Time
from tasks.DailyTrifles.page import page_store_gift_room, page_friends_luck
from winerror import NOERROR

from tasks.GameUi.page import page_main, page_summon, page_guild, page_mall, page_friends, page_courtyard_affairs, page_shikigami_records
from tasks.GameUi.default_pages import page_pet
from tasks.DailyTrifles.config import DailyTriflesConfig
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.Component.Summon.summon import Summon
from tasks.Orochi.script_task import ScriptTask as OrochiScriptTask
from tasks.Orochi.config import Layer
from tasks.Orochi.page import page_orochi
from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer
from tasks.DailyTrifles.config import SummonType
import re


class ScriptTask(OrochiScriptTask, Summon, DailyTriflesAssets):

    def run(self):
        con = self.config.daily_trifles.trifles_config
        pets_con = self.config.daily_trifles.pets_config
        simple_tidy_con = self.config.daily_trifles.simple_tidy
        # 每日召唤
        if con.one_summon:
            self.run_one_summon()
        if con.courtyard_affairs:
            self.run_courtyard_affairs()
        # 宠物喂养
        if pets_con.pets_feast:
            self.run_pets_feed()
        # 御魂十层（与宠物喂养解耦，不再经过宠物屋）
        if pets_con.enable_orochi_ten_once:
            self.run_orochi_ten_once()
        # 简易整理
        if simple_tidy_con.enable_greed or simple_tidy_con.enable_maneki:
            self.run_simple_tidy()
        if con.pickup_email:
            self.run_pickup_email()
        # 吉闻
        if con.luck_msg:
            self.run_luck_msg()
        # 商店签到
        if con.store_sign:
            self.run_store()
        self.config.save()
        self.plan_next_dt()
        raise TaskEnd('DailyTrifles')

    def run_simple_tidy(self):
        """简易整理：贪吃鬼 + 奉纳"""
        logger.hr('Simple tidy', 2)
        self.goto_page(page_shikigami_records)
        self.goto_souls()
        self.greed_maneki()
        self.back_records()
        self.goto_page(page_main)

    def goto_souls(self):
        """进入到御魂的主界面"""
        while 1:
            self.screenshot()
            if self.appear(self.I_ST_GREED) and self.appear(self.I_ST_TIDY):
                break
            if self.appear_then_click(self.I_ST_REPLACE, interval=1):
                continue
            if self.appear_then_click(self.I_ST_SOULS, interval=1):
                continue
            if self.appear_then_click(self.I_ST_SOULS_CLOSE, interval=1):
                continue
            if self.click(self.C_ST_DETAIL, interval=2):
                continue
        self.ocr_appear_click(self.O_ST_OVERFLOW)
        logger.info('Enter souls page')

    def back_records(self):
        """退回到式神录"""
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_RECORDS)

    def greed_maneki(self):
        """贪吃鬼和招财猫"""
        simple_tidy_con = self.config.daily_trifles.simple_tidy
        # 先是贪吃鬼
        if simple_tidy_con.enable_greed:
            logger.hr('Greed Ghost')
            self.ui_click(self.I_ST_GREED, self.I_ST_GREED_HABIT)
            self.ui_click(self.I_ST_GREED_HABIT, self.I_ST_FEED_NOW)
            logger.info('Feed greed ghost')
            feed_count = 0
            while 1:
                self.screenshot()
                if self.appear(self.I_ST_UNSELECTED):
                    self.ui_click_until_disappear(self.I_ST_UNSELECTED)
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                    continue
                if feed_count >= 3:
                    break
                if self.appear_then_click(self.I_ST_FEED_NOW, interval=3.5):
                    feed_count += 1
                    continue
            logger.info('Feed greed ghost done')
        # 关闭贪吃鬼, 进入奉纳
        while 1:
            self.screenshot()
            if self.appear(self.I_ST_CAT):
                break
            if self.appear(self.I_ST_UNSELECTED):
                self.ui_click_until_disappear(self.I_ST_UNSELECTED)
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                continue
            if self.appear_then_click(self.I_ST_GREED_CLOSE, interval=0.7):
                continue
            if self.appear_then_click(self.I_ST_BONGNA, interval=1, threshold=0.6):
                continue
        if simple_tidy_con.enable_maneki:
            logger.hr('Enter bongna')
            # 确保已弃置界面
            while 1:
                self.screenshot()
                if self.appear(self.I_ST_ABANDONED_SELECTED):
                    break
                if self.appear(self.I_UI_BACK_RED):
                    self.click(self.I_UI_BACK_RED, interval=0.8)
                    continue
                self.click(self.I_ST_ABANDONED_SELECTED, interval=1.5)
            # 确保是按照等级来排序的
            while 1:
                self.screenshot()
                if self.appear(self.I_UI_BACK_RED):
                    self.click(self.I_UI_BACK_RED, interval=0.8)
                    continue
                if self.ocr_appear(self.O_ST_SORT_LEVEL_1):
                    break
                if self.ocr_appear_click(self.O_ST_SORT_LEVEL_2, interval=0.6):
                    continue
                if self.ocr_appear_click(self.O_ST_SORT_TIME, interval=2):
                    continue
                if self.ocr_appear_click(self.O_ST_SORT_TYPE, interval=2):
                    continue
                if self.ocr_appear_click(self.O_ST_SORT_LOCATION, interval=2):
                    continue
            logger.info('Sort by level')
            # 开始奉纳
            while 1:
                if self.wait_until_appear(self.I_ST_SOUL_STACK, wait_time=2):
                    logger.info('Soul stack')
                else:
                    self.wait_until_appear(self.I_ST_LEVEL_0, wait_time=2)
                    self.screenshot()
                    if not self.appear(self.I_ST_LEVEL_0):
                        logger.info("First Orichi isn't Level 0, quit")
                        break
                    firvel = self.O_ST_FIRSET_LEVEL.ocr(self.device.image)
                    if firvel is None or firvel == '':
                        logger.info('ocr result is Null')
                        continue
                    if firvel != '古':
                        logger.info('No zero level, bongna done')
                        break

                # 长按
                self.click(self.L_ONE, interval=2.5)
                self.screenshot()
                gold_amount = self.O_ST_GOLD.ocr(self.device.image)
                if not isinstance(gold_amount, int):
                    logger.warning('Gold amount not int, skip')
                    continue
                if gold_amount == 0:
                    continue

                # 点击奉纳收取奖励
                if not self.appear(self.I_ST_DONATE):
                    logger.warning('Donate button not appear, skip')
                    continue
                # 点击奉纳 及收取奖励
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_UI_CONFIRM, interval=0.5):
                        continue
                    if self.ui_reward_appear_click():
                        continue
                    if self.appear(self.I_ST_GOD_PRESENT):
                        logger.info('God present appear')
                        self.click(self.C_ST_GOD_PRSENT, interval=2)
                        continue
                    if self.appear_then_click(self.I_ST_DONATE, interval=5.5):
                        self.wait_until_appear(self.I_ST_GOLD, True, wait_time=5)
                        continue
                    if not self.appear(self.I_ST_GOLD):
                        break
                logger.info('Donate one')

        logger.info('Bongna done')

    def run_pets_feed(self):
        """宠物喂养"""
        logger.hr('Pets feed', 2)
        self.goto_page(page_pet)
        self._feed()
        self.goto_page(page_main)

    def _feed(self):
        """快速喂养"""
        logger.hr('Feed', 3)
        self.ui_click(self.I_PET_FEAST, self.I_PET_FEED)
        number = self.O_PET_FEED_AP.ocr(self.device.image)
        if number == 0:
            # 已经投喂过了
            logger.warning('Already feed')
            self.appear_then_click(self.I_UI_BACK_CIRCLE)
            return
        self.ui_click(self.I_PET_FEED, self.I_PET_SKIP)
        self.ui_click_until_disappear(self.I_PET_SKIP)

    def run_orochi_ten_once(self):
        """运行一次御魂十层"""
        logger.hr('Run Orochi', 3)
        conf = self.config.daily_trifles.pets_config
        self.config.orochi.orochi_config.layer = Layer.TEN
        self.limit_count = 1
        self.limit_time = timedelta(hours=10)
        self.goto_page(page_orochi)
        if conf.switch_soul_enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(conf.switch_group_team)
        if conf.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(conf.group_name, conf.team_name)
        self.run_alone()

    def run_one_summon(self):
        logger.hr('daily summon', 2)
        if self.config.daily_trifles.today_is_done('summon'):
            logger.info('Today is done, skip')
            return
        self.goto_page(page_summon)
        config = self.config.daily_trifles.trifles_config
        if config.summon_type == SummonType.default:
            self.summon_one(draw_mystery_pattern=config.draw_mystery_pattern)
            self.check_time()
        elif config.summon_type == SummonType.recall:
            self.summon_recall()
        self.back_summon_main()
        self.config.daily_trifles.done_record.summon_dt = datetime.now()

    def check_time(self):
        config = self.config.daily_trifles.trifles_config
        now = datetime.now()
        next_run = now + self.config.daily_trifles.scheduler.success_interval
        # 检查是否跨月（next_run的月份与当前月份不同）
        if next_run.month != now.month:
            # 跨月重置神秘图案触发状态
            if not config.draw_mystery_pattern:
                config.draw_mystery_pattern = True
                logger.info(
                    f"reset draw_mystery_pattern to True, next_run: {next_run}")
        else:
            # 如果还是在同一月份，则没必要再绘制神秘图案
            config.draw_mystery_pattern = False
        self.config.save()

    def summon_recall(self):
        """
        确保在召唤界面,每日召唤一次
        召唤结束后回到 召唤主界面
        :return:
        """
        list = [self.O_SELECT_SM2, self.O_SELECT_SM3, self.O_SELECT_SM4]
        count = 0
        while True:
            count += 1

            for i in range(len(list)):
                sleep(1)
                self.goto_page(page_summon)
                self.appear_then_click(self.I_UI_BACK_RED, interval=1)
                x, y = list[i].coord()
                self.device.click(x, y)
                sleep(1)
                self.screenshot()
                if self.appear(self.I_RECALL_TICKET):
                    break
                logger.info("Select preset group RECALL")

            self.screenshot()
            if self.appear(self.I_RECALL_TICKET):
                break
            if count >= 3:
                self.config.notifier.push(title='今忆召唤抽卡失败', content='每日任务,今忆召唤抽卡失败!!!')
                return

        logger.info('Summon one RECALL')
        self.wait_until_appear(self.I_RECALL_TICKET)
        while True:
            ticket_info = self.O_RECALL_TICKET_AREA.ocr(self.device.image)
            # 处理 None 和空字符串
            if ticket_info is None or ticket_info == '':
                ticket_info = 0
            else:
                # 使用正则表达式提取字符串中的数字
                match = re.search(r'\d+', ticket_info)
                if match:
                    ticket_info = int(match.group())
                else:
                    logger.warning(f'Invalid ticket_info value: {ticket_info}, expected a numeric string')
                    ticket_info = 0  # 将无效值设置为默认值 0
            if ticket_info <= 0:
                logger.warning('There is no any one RECALL ticket')
                return
            # 某些情况下滑动异常
            self.S_RANDOM_SWIPE_1.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_2.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_3.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_4.name = 'S_RANDOM_SWIPE'
            while 1:
                self.screenshot()
                if self.appear(self.I_RECALL_ONE_TICKET):
                    break
                if self.appear_then_click(self.I_RECALL_TICKET, interval=1):
                    continue

            # 画一张票
            sleep(1)
            while 1:
                self.screenshot()
                if self.appear(self.I_RECALL_SM_CONFIRM, interval=0.6):
                    self.ui_click_until_disappear(self.I_RECALL_SM_CONFIRM)
                    break
                if self.appear(self.I_SM_CONFIRM_2, interval=0.6):
                    self.ui_click_until_disappear(self.I_SM_CONFIRM_2)
                    break
                if self.appear(self.I_RECALL_ONE_TICKET, interval=1):
                    # 某些时候会点击到 “语言召唤”
                    if self.appear_then_click(self.I_UI_CANCEL, interval=0.8):
                        continue
                    self.summon()
                    continue
            logger.info('Summon one success')

    def run_luck_msg(self):
        logger.hr('luck msg', 2)
        if self.config.daily_trifles.today_is_done('luck_msg'):
            logger.info('Today is done, skip')
            return
        self.goto_page(page_friends_luck)
        logger.info('Start luck msg')
        check_timer = Timer(2)
        check_timer.start()
        while 1:
            self.screenshot()

            if self.appear_then_click(self.I_CLICK_BLESS, interval=1):
                continue
            if self.appear_then_click(self.I_ONE_CLICK_BLESS, interval=1):
                continue
            if self.ui_reward_appear_click():
                logger.info('Get reward of luck msg')
                break
            if check_timer.reached():
                logger.warning('There is no any luck msg')
                break

        self.goto_page(page_main)
        self.config.daily_trifles.done_record.luck_msg_dt = datetime.now()

    def run_store(self):
        if self.check_store_all_done():
            logger.info('Store all done, skip')
            return
        self.goto_page(page_mall, confirm_wait=3)
        if self.config.daily_trifles.trifles_config.store_sign:
            self.run_store_sign()
        self.goto_page(page_main)

    def run_store_sign(self):
        logger.hr('store sign', 2)
        if self.config.daily_trifles.today_is_done('store_sign'):
            logger.info('Today is done, skip')
            return
        self.config.daily_trifles.done_record.store_sign_dt = datetime.now()
        self.goto_page(page_store_gift_room)
        self.screenshot()
        self.appear_then_click(self.I_GIFT_RECOMMEND, interval=1)
        logger.info('Enter store sign')
        sleep(1)  # 等个动画
        self.screenshot()
        if not self.appear(self.I_GIFT_SIGN):
            logger.warning('There is no gift sign')
            return

        if self.ui_get_reward(self.I_GIFT_SIGN, click_interval=2.5):
            logger.info('Get reward of gift sign')

    def run_courtyard_affairs(self):
        """庭院事务"""
        logger.hr('courtyard affairs', 2)
        self.goto_page(page_main)
        timeout_timer = Timer(3).start()
        while not timeout_timer.reached():
            self.screenshot()
            if self.appear(self.I_ENTER_COURTYARD_AFFAIRS, interval=1.2):
                self.goto_page(page_courtyard_affairs)
                timeout_timer.reset()
                break
        if timeout_timer.reached():
            logger.info('Not have courtyard affairs, exit')
            return
        while True:
            self.screenshot()
            if self.appear(self.I_CHECK_IN_DAILY, interval=0.5):
                break
            if self.appear_then_click(self.I_ENTER_DAILY, interval=1):
                continue
        self.appear_then_click(self.I_ONE_COMPLETE, interval=1)
        self.goto_page(page_main)
        self.config.daily_trifles.done_record.courtyard_affairs_dt = datetime.now()

    def run_pickup_email(self):
        """领取邮件"""
        logger.hr('pick up email', 2)
        self.goto_page(page_main)
        self.screenshot()
        if self.appear(self.I_DT_HARVEST_MAIL_COPY):
            self.appear_then_click(self.I_DT_HARVEST_MAIL_COPY, interval=1.2)
            logger.info('Clicked mail icon by template, entering mail page')
        else:
            self.device.click(x=1165, y=35, control_name='MAIL_ICON')
            logger.info('Clicked fixed mail icon position')
        self.device.sleep(1)
        self.screenshot()
        if self.appear(self.O_MAIL_EMPTY):
            logger.info('No system emails, exit mail page')
            self.appear_then_click(GlobalGameAssets.I_UI_BACK_RED, interval=1.2)
            self.device.sleep(1)
            self.goto_page(page_main)
            self.config.daily_trifles.done_record.pickup_email_dt = datetime.now()
            return
        timeout_timer = Timer(20).start()
        while not timeout_timer.reached():
            self.screenshot()
            if self.appear(self.O_MAIL_EMPTY):
                logger.info('No system emails, exit mail page')
                self.appear_then_click(GlobalGameAssets.I_UI_BACK_RED, interval=1.2)
                break
            if self.appear_then_click(self.I_HARVEST_MAIL_ALL, interval=2):
                timeout_timer.reset()
                continue
            if self.appear_then_click(self.I_READ_ALL_MAIL, interval=3):
                continue
            if self.appear_then_click(self.I_HARVEST_MAIL_CONFIRM, interval=1):
                continue
            from tasks.Restart.assets import RestartAssets
            if self.appear_then_click(RestartAssets.I_HARVEST_MAIL_OPEN, interval=1):
                continue
            if self.appear(self.I_DT_HARVEST_MAIL_COPY):
                self.device.click(x=1165, y=35, control_name='MAIL_ICON')
                continue
        self.appear_then_click(GlobalGameAssets.I_UI_BACK_RED, interval=1.2)
        self.device.sleep(1)
        self.goto_page(page_main)
        self.config.daily_trifles.done_record.pickup_email_dt = datetime.now()

    def plan_next_dt(self):
        # 定时领体力（每天 12-14、20-22 时内各有 20 体力）
        now = datetime.now()
        # 如果时间在00:00-12:00之间则设定时间为当日 12 时
        if now.time() < time(12, 0):
            self.custom_next_run(task='DailyTrifles', custom_time=Time(12, 0), time_delta=0)
        # 如果时间在12:00-20:00之间则设定时间为当日 20 时
        elif time(12, 0) <= now.time() < time(20, 0):
            self.custom_next_run(task='DailyTrifles', custom_time=Time(20, 0), time_delta=0)
        # 如果时间在20:00-23:59之间则设定时间为次日 12 时
        else:
            self.custom_next_run(task='DailyTrifles', custom_time=Time(12, 0), time_delta=1)

    def check_store_all_done(self) -> bool:
        """判断商店任务是否都做完了, 做完了则不再进入商店"""
        if self.config.daily_trifles.trifles_config.store_sign and not self.config.daily_trifles.today_is_done('store_sign'):
            return False
        return True


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run_courtyard_affairs()

