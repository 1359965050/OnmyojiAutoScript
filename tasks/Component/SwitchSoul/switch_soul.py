# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from typing import Union

from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.ocr import RuleOcr
from module.base.timer import Timer
from tasks.base_task import BaseTask
from tasks.Component.SwitchSoul.assets import SwitchSoulAssets
from tasks.GameUi.assets import GameUiAssets
from module.logger import logger


def switch_parser(switch_str: str) -> tuple:
    switch_list = switch_str.split(',')
    if len(switch_list) != 2:
        raise ValueError('Switch_str must be 2 length')
    return int(switch_list[0]), int(switch_list[1])


class SwitchSoul(BaseTask, SwitchSoulAssets):

    def goto_shikigami_records(self, button):
        """
        进入式神录
        """
        wait_timer = Timer(15).start()
        while 1:
            if wait_timer.reached():
                logger.warning('Goto shikigami records timeout')
                return
            self.screenshot()
            if self.appear(GameUiAssets.I_CHECK_RECORDS):
                break
            if self.appear_then_click(button, interval=1.5):
                continue
        logger.info('Entry shikigami records')

    def run_switch_soul(self, target: tuple | list[tuple] | str):
        """
        保证在式神录的界面
        :return:
        """
        if isinstance(target, str):
            try:
                target = switch_parser(target)
            except ValueError:
                logger.error('Switch soul config error')
                return
        self.click_preset()
        self.switch_souls(target)

    def click_preset(self) -> None:
        """
        点击预设
        :return:
        """
        wait_timer = Timer(15).start()
        while 1:
            if wait_timer.reached():
                logger.warning('Click preset timeout')
                return
            self.screenshot()
            if self.appear(self.I_SOU_SWITCH_1):
                break
            if self.appear(self.I_SOU_SWITCH_2):
                break
            if self.appear(self.I_SOU_SWITCH_3):
                break
            if self.appear(self.I_SOU_SWITCH_4):
                break
            if self.appear(self.I_SOU_TEAM_PRESENT):
                break
            if self.appear_then_click(self.I_SOUL_PRESET, interval=2):
                continue
        logger.info('Click preset in switch soul')

    def switch_soul_one(self, group: int, team: int) -> None:
        """
        设置一个队伍的预设御魂
        :param group: 只能是[1-7]
        :param team: 只能是[1-4]
        :return:
        """

        def get_group_assets(group: int) -> tuple:
            match = {
                1: tuple([self.C_SOU_GROUP_1, self.I_SOU_CHECK_GROUP_1]),
                2: tuple([self.C_SOU_GROUP_2, self.I_SOU_CHECK_GROUP_2]),
                3: tuple([self.C_SOU_GROUP_3, self.I_SOU_CHECK_GROUP_3]),
                4: tuple([self.C_SOU_GROUP_4, self.I_SOU_CHECK_GROUP_4]),
                5: tuple([self.C_SOU_GROUP_5, self.I_SOU_CHECK_GROUP_5]),
                6: tuple([self.C_SOU_GROUP_6, self.I_SOU_CHECK_GROUP_6]),
                7: tuple([self.C_SOU_GROUP_7, self.I_SOU_CHECK_GROUP_7]),
            }
            return match[group]

        def get_team_asset(team: int):
            match = {
                1: self.I_SOU_SWITCH_1,
                2: self.I_SOU_SWITCH_2,
                3: self.I_SOU_SWITCH_3,
                4: self.I_SOU_SWITCH_4,
            }
            return match[team]

        # 滑动至分组最上层(分組過多, 导致第一个分组显示不全)
        cur_text = ""
        swipe_timer = Timer(15).start()
        while 1:
            if swipe_timer.reached():
                logger.warning('Switch soul swipe to top timeout')
                break
            self.screenshot()
            compare1 = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            ocr_text = str([result.ocr_text for result in compare1])
            # 相等时 滑动到最上层
            if cur_text == ocr_text:
                break
            cur_text = ocr_text
            # 向上滑动
            self.swipe(self.S_SS_GROUP_SWIPE_UP, 1.5)
            # 等待滑动动画
            sleep(0.5)

        if group < 1 or group > 7:
            raise ValueError('Switch soul_one group must be in [1-7]')
        if team < 1 or team > 4:
            raise ValueError('Switch soul_one team must be in [1-4]')
        # 这一步是选择组
        target_click, target_check = get_group_assets(group)
        # while 1:
        #     self.screenshot()
        #     if self.click(target_click, interval=1):
        #         continue
        #     if self.appear(target_check):
        #         break
        # 2023.8.5 修改为无反馈的点击切换
        for i in range(2):
            self.click(target_click)
            sleep(0.5)
        # 点击队伍
        target_team = get_team_asset(team)
        for i in range(3):
            sleep(0.8)
            self.screenshot()
            if self.appear(self.I_SOU_SWITCH_SURE):
                confirm_timer = Timer(15).start()
                while 1:
                    if confirm_timer.reached():
                        logger.warning('Switch soul confirm timeout')
                        break
                    self.click(self.I_SOU_SWITCH_SURE, 3)
                    self.screenshot()
                    if self.appear_then_click(self.I_CHECK_BLOCK, 3):
                        continue
                    if not self.appear(self.I_SOU_SWITCH_SURE):
                        break
                continue
            if not self.appear_then_click(target_team, interval=3):
                logger.warning(f'Click team {team} failed in group {group}')
        # 兜底若还出现确认按钮则点击
        self.ui_click_until_disappear(self.I_SOU_SWITCH_SURE)
        logger.info(f'Switch soul_one group {group} team {team}')

    def switch_souls(self, target: tuple or list[tuple]) -> None:
        """
        切换御魂
        :param target: [(1, 1), (2, 2), (3, 3), (4, 4)]  或者是单独的一个元组(4, 4) 第一个是组, 第二个是队伍
        :return:
        """
        if isinstance(target, tuple):
            target = [target]
        for group, team in target:
            group = int(group)
            team = int(team)
            self.switch_soul_one(group, team)

    def exit_shikigami_records(self) -> None:
        """
        退出式神录的界面
        :return:
        """
        exit_timer = Timer(15).start()
        while 1:
            if exit_timer.reached():
                logger.warning('Exit shikigami records timeout')
                break
            self.screenshot()
            if not self.appear(self.I_SOU_CHECK_IN):
                break
            if self.appear_then_click(self.I_RECORD_SOUL_BACK, interval=3.5):
                continue
        logger.info('Exit shikigami records')

    def run_switch_soul_by_name(self, groupName, teamName):
        """
        保证在式神录的界面
        :return:
        """
        if isinstance(groupName, str) and isinstance(teamName, str):
            self.click_preset()
            self.switch_soul_by_name(groupName, teamName)

    def switch_soul_by_name(self, groupName, teamName):
        """
        保证在式神录的界面
        :return:
        """
        logger.hr('按名称切换御魂', 2)
        # 滑动至分组最上层
        last_group_text = ''
        swipe_top_timer = Timer(20).start()
        while 1:
            if swipe_top_timer.reached():
                logger.warning('Swipe to top of group timeout')
                break
            self.screenshot()
            compare1 = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            now_group_text = str([result.ocr_text for result in compare1])
            if now_group_text == last_group_text:
                break
            self.swipe(self.S_SS_GROUP_SWIPE_UP, 2)
            sleep(2.5)
            last_group_text = now_group_text
        logger.info('Swipe to top of group')

        # 判断有无目标分组
        find_group_timer = Timer(25).start()
        last_seen_groups = None
        same_group_count = 0
        group_found = False
        while 1:
            if find_group_timer.reached():
                logger.warning(f'Swipe down to find group [{groupName}] timeout')
                break
            self.screenshot()
            # 获取当前分组名
            results = self.O_SS_GROUP_NAME.detect_and_ocr(self.device.image)
            text1 = [result.ocr_text for result in results]
            # 判断当前分组有无目标分组
            result = set(text1).intersection({groupName})
            # 有则跳出检测
            if result and len(result) > 0:
                group_found = True
                break
            if text1 == last_seen_groups:
                same_group_count += 1
                if same_group_count >= 2:
                    logger.warning(f'Group [{groupName}] not found after reaching bottom of list')
                    break
            else:
                same_group_count = 0
                last_seen_groups = text1
            self.swipe(self.S_SS_GROUP_SWIPE_DOWN)
            sleep(1.5)
        if not group_found:
            return False
        logger.info('Swipe down to find target group')

        # 选中分组
        select_group_timer = Timer(10).start()
        while 1:
            if select_group_timer.reached():
                logger.warning(f'Select group [{groupName}] timeout')
                return False
            self.screenshot()
            self.O_SS_GROUP_NAME.keyword = groupName
            if self.ocr_appear_click(self.O_SS_GROUP_NAME):
                break
        logger.info(f'Select group {groupName}')

        # 滑动至阵容最上层
        last_team_text = ''
        swipe_team_top_timer = Timer(20).start()
        while 1:
            if swipe_team_top_timer.reached():
                logger.warning('Swipe to top of team timeout')
                break
            self.screenshot()
            compare1 = self.O_SS_TEAM_NAME.detect_and_ocr(self.device.image)
            now_team_text = str([result.ocr_text for result in compare1])
            # 向上滑动
            if now_team_text == last_team_text:
                break
            self.swipe(self.S_SS_TEAM_SWIPE_DOWN, 1.5)
            sleep(2)
            last_team_text = now_team_text
        logger.info('Swipe to top of team')

        # 判断当前分组有无目标阵容
        find_team_timer = Timer(25).start()
        last_seen_teams = None
        same_team_count = 0
        team_found = False
        while 1:
            if find_team_timer.reached():
                logger.warning(f'Swipe up to find team [{teamName}] timeout')
                break
            self.screenshot()
            # 获取当前阵容名
            results = self.O_SS_TEAM_NAME.detect_and_ocr(self.device.image)
            text1 = [result.ocr_text for result in results]
            # 判断当前分组有无目标阵容
            result = set(text1).intersection({teamName})
            # 有则跳出检测
            if result and len(result) > 0:
                team_found = True
                break
            if text1 == last_seen_teams:
                same_team_count += 1
                if same_team_count >= 2:
                    logger.warning(f'Team [{teamName}] not found in group [{groupName}]')
                    break
            else:
                same_team_count = 0
                last_seen_teams = text1
            self.swipe(self.S_SS_TEAM_SWIPE_UP, 0.3)
        if not team_found:
            return False
        logger.info('Swipe up to find target team')

        # 选中分组
        logger.info(f'Select team {teamName}')
        # 切换御魂
        cnt_click: int = 0
        apply_timer = Timer(15).start()
        self.O_SS_TEAM_NAME.keyword = teamName
        while 1:
            if apply_timer.reached():
                logger.warning(f'Apply team [{teamName}] soul preset timeout')
                break
            self.screenshot()
            if cnt_click >= 4:
                break
            if self.appear_then_click(self.I_SOU_SWITCH_SURE, interval=0.8):
                continue
            if self.ocr_appear_click_by_rule(self.O_SS_TEAM_NAME, self.I_SOU_CLICK_PRESENT, interval=1.5):
                cnt_click += 1
                continue
        logger.info(f'Switch soul_one group {groupName} team {teamName}')

    def ocr_appear_click_by_rule(self,
                                 target: RuleOcr,
                                 action: Union[RuleClick, RuleLongClick] = None,
                                 interval: float = None,
                                 duration: float = None) -> bool:
        """
        ocr识别目标，如果目标存在，则触发动作
        :param target:
        :param action:
        :param interval:
        :param duration:
        :return:
        """
        appear = self.ocr_appear(target, interval)

        if not appear:
            return False

        x1, y1 = target.coord()
        x, y = action.coord()

        self.device.click(x=x, y=y1, control_name=target.name)
        return True


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    s = SwitchSoul(c, d)

    s.click_preset()
    # s.switch_soul_one(4, 1)
    # s.switch_soul_by_name('契灵', '茨球')
    s.switch_soul_by_name('默认分组', '队伍5')
