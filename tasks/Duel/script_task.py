# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep

import random
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchOnmyoji.switch_onmyoji import SwitchOnmyoji
from tasks.GameUi.page import page_duel, page_onmyodo, random_click
from tasks.Duel.config import Duel
from tasks.Duel.assets import DuelAssets
from tasks.GameUi.page import page_main, page_shikigami_records

""" 斗技 """


class ScriptTask(GeneralBattle, DuelAssets, SwitchOnmyoji):
    # TODO: 斗技适配页面模块

    battle_win_count = 0
    battle_lose_count = 0
    current_score = 0
    pre_battle_win_cnt = battle_win_count
    pre_battle_lose_cnt = battle_lose_count
    conf: Duel = None

    def run(self):
        current_time = datetime.now().time()
        if not (time(12, 00) <= current_time < time(23, 00)):
            self.set_next_run(task='Duel', success=True, finish=False)
            raise TaskEnd('Duel')
        self.conf = self.config.duel
        limit_time = self.conf.duel_config.limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        self.prepare_duel()
        while True:
            self.screenshot()
            self.check_and_get_reward()
            if not self.duel_main():
                self.goto_page(page_duel)
                continue
            if not self.can_start_duel():
                break
            self.start_duel()
        logger.info('Duel battle end')
        self.goto_page(page_main)
        self.set_next_run(task='Duel', success=True, finish=True)
        raise TaskEnd('Duel')

    def prepare_duel(self):
        """斗技准备工作(切换阴阳师...), 最后回到斗技主界面"""
        self.goto_page(page_main)
        if self.conf.duel_config.switch_enabled:
            self.goto_page(page_onmyodo)
            self.switch_onmyoji(self.conf.duel_config.switch_onmyoji)
        self.goto_page(page_duel)
        self.switch_all_soul()

    def can_start_duel(self) -> bool:
        """是否可以运行斗技"""
        # 任务执行时间超过限制时间，退出
        if datetime.now() - self.start_time >= self.limit_time:
            logger.info('Duel task is over time')
            return False
        # 当前分数跟目标分数比较, 判断分数是否已经满足条件
        if self.get_and_update_cur_score() >= self.conf.duel_config.target_score:
            logger.info('Duel task is over score')
            return False
        # 练习
        if self.appear(self.I_BATTLE_WITH_TRAIN) or self.appear(self.I_BATTLE_WITH_TRAIN2):
            return False
        # 荣誉满了，退出
        if self.conf.duel_config.honor_full_exit and self.check_honor():
            logger.info('Duel task is over honor')
            return False
        return True

    def start_duel(self):
        """进行一次斗技"""
        logger.hr('Duel battle', 2)
        self.current_count += 1
        self.enter_battle()
        self.battle_prepare()
        battle_ret = self.wait_battle()
        if battle_ret:
            self.pre_battle_win_cnt = self.battle_win_count
            self.battle_win_count += 1
        else:
            self.pre_battle_lose_cnt = self.battle_lose_count
            self.battle_lose_count += 1
        task_run_time_seconds = timedelta(seconds=int((datetime.now() - self.start_time).total_seconds()))
        logger.info(f'battle result: {battle_ret}')
        logger.info(f'battle count:{self.current_count} | win:{self.battle_win_count} failure:{self.battle_lose_count}')
        logger.info(f'battle time: {task_run_time_seconds} / {self.limit_time}')
        self.goto_page(page_duel)

    def enter_battle(self):
        """点击开始战斗(一直到出现战斗准备界面)"""
        logger.hr('duel battle matching')
        while not self.is_in_battle_prepare():
            self.screenshot()
            # 战斗按钮
            self.ui_click_until_disappear(self.I_D_BATTLE, interval=1.2)
            self.ui_click_until_disappear(self.I_D_BATTLE2, interval=1.2)
            # 战斗带保护的按钮
            self.ui_click_until_disappear(self.I_D_BATTLE_PROTECT, interval=1.2)

    def battle_prepare(self):
        """选式神准备斗技阶段"""
        logger.hr('duel battle preparing')
        not_in_prepare_cnt, max_retry = 0, 3
        while True:
            if not_in_prepare_cnt >= max_retry:  # max_retry次识别不到任何阶段元素(准备,战斗,结算), 退出
                break
            self.screenshot()
            if self.is_battle_end() or self.is_in_real_battle():  # 战斗已经结束或已经开始战斗
                break
            if not self.is_in_battle_prepare():  # 一般不会出现这种情况(不在准备,战斗,结束界面), 但是处理一下
                not_in_prepare_cnt += 1
                sleep(random.uniform(1.2, 2.4))
                continue
            not_in_prepare_cnt = 0
            # 点击自动上阵或准备
            if self.appear_then_click(self.I_D_AUTO_ENTRY, interval=1.2) or \
                    self.appear_then_click(self.I_D_PREPARE, interval=1.2):
                self.reset_device('PREPARE_BEFORE_BATTLE')

    def wait_battle(self) -> bool:
        """等待战斗结束, 返回战斗结果, 最后会退出到斗技主界面"""
        logger.hr('duel battle waiting')
        battle_operated = False
        battle_timeout_timer = Timer(270).start()
        ret_timer = Timer(5)
        battle_timeout_cnt, max_timeout_cnt = 0, 3
        ret = None
        while True:
            self.screenshot()
            self.check_and_get_reward()
            if self.appear(self.I_CHECK_DUEL) and self.appear(self.I_D_HELP):  # 斗技主界面
                break
            if self.appear(self.I_D_WIN_SHARE,interval= 1.2): #拔得头筹
                self.click(random_click(ltrb=(True, True, False, True)), interval=1.2)
                continue
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.2):  # 关闭段位上升页面
                ret_timer.reset()
                continue
            if ret_timer.started() and ret_timer.reached():  # 兜底逻辑, 已经结算了但是还没有到斗技主界面
                self.goto_page(page_duel)
                break
            if self.is_battle_win():
                ret = True
                ret_timer.start()
                self.click(random_click(ltrb=(True, True, False, True)), interval=1.2)
                continue
            if self.is_battle_lose():
                ret = False
                ret_timer.start()
                self.click(random_click(ltrb=(True, True, False, True)), interval=1.2)
                continue
            if not ret_timer.started() and battle_timeout_cnt >= max_timeout_cnt:
                logger.warning('Duel battle timeout[>15 minutes], exit')
                self.duel_exit_battle()
                continue
            if ret is None and not battle_operated:  # 进行战斗前的操作
                self.ui_click(self.O_BATTLE_HAND, self.O_BATTLE_AUTO, interval=2.0)
                self.green_mark(self.conf.duel_config.green_enable, self.conf.duel_config.green_mark)
                battle_operated = True
                self.reset_device('BATTLE_STATUS_S')
                continue
            if not ret_timer.started() and battle_timeout_timer.reached_and_reset():
                battle_timeout_cnt += 1
                self.reset_device('BATTLE_STATUS_S')
                logger.warning("battle' time is too long, increase wait time")
        return ret

    def duel_exit_battle(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_D_FAIL) or self.appear(self.I_FALSE):
                return
            if self.appear_then_click(self.I_EXIT_ENSURE):
                continue
            # 选式神界面退出或战斗内退出
            if self.appear_then_click(self.I_DUEL_EXIT, interval=1) or self.appear_then_click(self.I_EXIT, interval=1):
                continue

    def check_honor(self) -> bool:
        """检查荣誉是否满了"""
        if not self.appear(self.I_DUEL_HONOR):
            return False
        roi_x = self.I_DUEL_HONOR.roi_front[0] + self.I_DUEL_HONOR.roi_front[2]
        roi_y = self.I_DUEL_HONOR.roi_front[1]
        roi_w = 110
        roi_h = self.I_DUEL_HONOR.roi_front[3]
        self.O_D_HONOR.roi = [roi_x, roi_y, roi_w, roi_h]
        current, remain, total = self.O_D_HONOR.ocr(self.device.image)
        return current == total and remain == 0

    def get_and_update_cur_score(self, skip_screenshot: bool = True) -> int:
        """
        获取并更新当前斗技分数, 要求处于斗技主界面
        :param skip_screenshot: 是否跳过截图
        :return: 当前斗技分数
        """
        self.maybe_screenshot(skip_screenshot)
        score, remain, total = self.O_D_SCORE.ocr(self.device.image)
        if score > 10000:
            # 识别错误分数超过一万, 去掉最高位
            logger.warning('Recognition error, score is too high')
            score = int(str(score)[1:])

        # 检查名士段位（3000分及以上）
        if self.appear(self.I_D_CELEB_STAR) or self.appear(self.I_D_CELEB_HONOR):
            celeb_stars = self.O_D_CELEB_STAR_COUNT.ocr(self.device.image)
            if isinstance(celeb_stars, int) and celeb_stars > 0:
                score = 3000 + celeb_stars * 100
                logger.info(f'Detected Celeb (名士) rank with {celeb_stars} stars, calculated score: {score}')
            else:
                score = max(score, 3000)
                logger.info(f'Detected Celeb (名士) rank, score set to: {score}')

        logger.info(f'battle score: {score}')
        self.current_score = score
        return self.current_score


    def duel_main(self, screenshot=False) -> bool:
        """判断是否在斗技主界面"""
        if screenshot:
            self.screenshot()
        return self.appear(self.I_D_HELP) or self.appear(self.I_CHECK_DUEL)

    def switch_all_soul(self):
        """在斗技式神备选界面一键切换所有御魂"""
        if not self.conf.duel_config.switch_all_soul:
            return
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 3:
                break
            if self.appear_then_click(self.I_D_TEAM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.6):
                continue
            if self.appear_then_click(self.I_D_TEAM_SWTICH, interval=1):
                click_count += 1
                continue
        logger.info('Souls Switch is complete')
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_D_TEAM)

    def check_and_get_reward(self):
        """检查并收获奖励"""
        if self.appear(self.I_REWARD) or self.appear(self.I_UI_REWARD):
            if self.click(random_click(ltrb=(True, True, False, True)), interval=0.6):
                logger.info('get reward')

    def is_in_battle_prepare(self, skip_screenshot=True) -> bool:
        """是否在战斗准备界面"""
        self.maybe_screenshot(skip_screenshot)
        return self.appear(self.I_D_PREPARE) or \
            self.appear(self.I_D_AUTO_ENTRY) or \
            self.appear(self.I_D_WORD_BATTLE)

    def is_battle_win(self) -> bool:
        return self.appear(self.I_WIN) or self.appear(self.I_D_VICTORY)

    def is_battle_lose(self) -> bool:
        return self.appear(self.I_FALSE) or self.appear(self.I_D_FAIL)

    def is_battle_end(self) -> bool:
        return self.is_battle_win() or self.is_battle_lose() or \
            self.appear(self.I_REWARD) or self.appear(self.I_UI_REWARD)

    def reset_device(self, status: str):
        self.device.click_record_clear()
        self.device.stuck_record_clear()
        self.device.stuck_record_add(status)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas3')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

