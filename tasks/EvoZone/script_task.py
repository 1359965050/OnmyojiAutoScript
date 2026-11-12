# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

from tasks.Component.GeneralBattle.general_battle import GeneralBattle, ExitMatcher, BattleContext, BattleAction
from tasks.Component.GeneralInvite.general_invite import GeneralInvite, RoomType
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.default_pages import page_reward
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page import page_main, page_awake_zones, page_shikigami_records
from tasks.EvoZone.assets import EvoZoneAssets
from tasks.EvoZone.config import EvoZone, UserStatus, KirinType
from module.base.timer import Timer
from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, EvoZoneAssets, SwitchSoul):
    default_room_type = RoomType.NORMAL_3

    def _register_custom_pages(self) -> None:
        reward_page = self.navigator.resolve_page(page_reward)
        if reward_page is None:
            return
        reward_page.recognizer = any_of(
            self.I_GI_SURE,
            self.I_GREED_GHOST,
            self.I_PET_PRESENT,
            reward_page.recognizer,
        )

    def _team_exit_matcher(self) -> ExitMatcher:
        return any_of(
            self.I_CHECK_TEAM,
            self.I_GI_IN_ROOM,
            self.I_GI_EMOJI_1,
            self.I_GI_EMOJI_2,
        )

    def _exit_matcher(self) -> ExitMatcher | None:
        return any_of(
            self.I_EVOZONE_FIRE,
            self._team_exit_matcher(),
            self.I_CHECK_AWAKE,
            self.I_CHECK_EXPLORATION,
        )

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        # 无论胜利与否, 都会出现是否邀请一次队友, 区别在于, 失败的话不会出现那个勾选默认邀请的框
        if self.config.evo_zone.evo_zone_config.user_status == UserStatus.LEADER and \
            self.check_and_invite(self.config.evo_zone.invite_config.default_invite):
            return BattleAction.CONTINUE
        if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
            return BattleAction.CONTINUE
        return super()._handle_reward(context, config)

    def run(self) -> bool:

        limit_count = self.config.evo_zone.evo_zone_config.limit_count
        limit_time = self.config.evo_zone.evo_zone_config.limit_time
        self.current_count = 0
        self.limit_count: int = limit_count
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        if not getattr(self, '_custom_pages_registered', False):
            self._register_custom_pages()
            self._custom_pages_registered = True
        con = self.config.evo_zone
        config: EvoZone = self.config.evo_zone

        # 队长/队员若启动时已处于组队房间或战斗中，严禁跳回庭院导致误触退出组队或拆散队伍
        self.screenshot()
        in_team_session = (
            con.evo_zone_config.user_status in (UserStatus.MEMBER, UserStatus.LEADER)
            and self.is_in_team_session()
        )
        if in_team_session:
            logger.info(
                f'EvoZone {con.evo_zone_config.user_status.value} already in team room or battle, skip goto page_main'
            )
        else:
            if con.switch_soul_config.enable:
                self.goto_page(page_shikigami_records)
                self.run_switch_soul(con.switch_soul_config.switch_group_team)
            if con.switch_soul_config.enable_switch_by_name:
                self.goto_page(page_shikigami_records)
                self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)

            self.goto_page(page_main)
            if config.evo_zone_config.soul_buff_enable:
                self.open_buff()
                self.awake(is_open=True)
                self.close_buff()

        success = True
        match config.evo_zone_config.user_status:
            case UserStatus.LEADER:
                success = self.run_leader()
            case UserStatus.MEMBER:
                success = self.run_member()
            case UserStatus.ALONE:
                self.run_alone()
            case UserStatus.WILD:
                self.run_wild()
            case _:
                logger.error('Unknown user status')

        self.goto_page(page_main)
        # 记得关掉
        if config.evo_zone_config.soul_buff_enable:
            self.open_buff()
            self.awake(is_open=False)
            self.close_buff()
        # 下一次运行时间
        if success:
            self.set_next_run('EvoZone', finish=True, success=True)
        else:
            self.set_next_run('EvoZone', finish=False, success=False)
        raise TaskEnd

    def evozone_enter(self) -> bool:
        logger.info('Enter evozone')
        kirintype = self.I_LIGHTNING_KIRIN
        match self.config.evo_zone.evo_zone_config.kirin_type:
            case KirinType.FIREKIRIN:
                kirintype = self.I_FIRE_KIRIN
            case KirinType.WINDKIRIN:
                kirintype = self.I_WIND_KIRIN
            case KirinType.WATERKIRIN:
                kirintype = self.I_WATER_KIRIN
            case KirinType.LIGHTNINGKIRIN:
                kirintype = self.I_LIGHTNING_KIRIN
        enter_timer = Timer(15).start()
        while True:
            if enter_timer.reached():
                logger.warning('EvoZone enter timeout')
                return False
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return True
            if self.appear_then_click(kirintype, interval=1):
                continue
        return False

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True
        return False

    def run_leader(self):
        logger.info('Start run leader')
        self.screenshot()
        if self.dismiss_team_exit_prompt():
            self.screenshot()
        if self.is_in_team_session():
            logger.info('EvoZone leader already in team room or battle, skip create room')
            if self.is_in_room(False):
                self.check_lock(
                    self.config.evo_zone.general_battle_config.lock_team_enable,
                    self.I_LOCK,
                    self.I_UNLOCK,
                )
        else:
            self.goto_page(page_awake_zones)
            self.evozone_enter()
            layer = self.config.evo_zone.evo_zone_config.layer
            logger.info("test0")
            self.check_layer(layer)
            logger.info("test1")
            self.check_lock(self.config.evo_zone.general_battle_config.lock_team_enable, self.I_EVOZONE_LOCK, self.I_EVOZONE_UNLOCK)
            logger.info("test2")
            # 创建队伍
            logger.info('Create team')
            create_timer = Timer(15).start()
            while 1:
                if create_timer.reached():
                    logger.warning('EvoZone create team timeout')
                    break
                self.screenshot()
                if self.appear(self.I_CHECK_TEAM):
                    break
                if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                    continue
            # 创建房间
            self.create_room()
            self.ensure_private()
            self.create_ensure()
        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()
            if self.dismiss_team_exit_prompt():
                continue
            if self.check_and_invite(self.config.evo_zone.invite_config.default_invite):
                continue
            if self.current_count >= self.limit_count:
                if self.is_in_room(False):
                    logger.info('EvoZone count limit out')
                    break
            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room(False):
                    logger.info('EvoZone time limit out')
                    break
            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room(False):
                if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                    continue
                if self.is_in_battle(False):
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self._team_exit_matcher(),
                    )
                    continue
                # 如果在探索界面或者是出现在组队界面， 那就是可能房间死了
                # 要结束任务
                sleep(0.5)
                if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                    sleep(0.5)
                    if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                        logger.warning('EvoZone task failed')
                        success = False
                        break
                continue
            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.config.evo_zone.invite_config):
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self._team_exit_matcher(),
                    )
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this EvoZone task')
                    success = False
                    break
            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self.config.evo_zone.invite_config, is_first=True):
                    logger.warning('Invite failed and exit this evozone task')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self._team_exit_matcher(),
                    )

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass
        if not success:
            return False
        return True

    def run_member(self):
        logger.info('Start run member')
        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                continue
            if self.current_count >= self.limit_count:
                logger.info('EvoZone count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('EvoZone time limit out')
                break
            if self.check_then_accept():
                continue
            if self.is_in_room(False):
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.config.evo_zone.invite_config.wait_time):
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self._team_exit_matcher(),
                    )
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            if self.is_in_battle(False):
                self.run_general_battle(
                    config=self.config.evo_zone.general_battle_config,
                    exit_matcher=self._team_exit_matcher(),
                )

        exit_timer = Timer(20).start()
        while 1:
            if exit_timer.reached():
                logger.warning('EvoZone run_member exit timeout')
                break
            self.screenshot()
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_CHECK_MAIN) or self.appear(self.I_CHECK_EXPLORATION):
                break
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=0.8):
                continue
            if self.appear(self.I_REWARD) or self.appear(self.I_REWARD_STATISTICS) or self.appear(self.I_WIN) or self.appear(self.I_FALSE):
                self.click(self.C_RANDOM_RIGHT, interval=0.8)
                continue
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass
        return True

    def run_alone(self):
        logger.info('Start run alone')
        self.goto_page(page_awake_zones)
        self.evozone_enter()
        layer = self.config.evo_zone.evo_zone_config.layer
        self.check_layer(layer)
        self.check_lock(self.config.evo_zone.general_battle_config.lock_team_enable, self.I_EVOZONE_LOCK, self.I_EVOZONE_UNLOCK)

        def is_in_evozone(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_EVOZONE_FIRE)

        wait_timer = Timer(15).start()
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                wait_timer.reset()
                continue
            if not is_in_evozone():
                if self.is_in_battle(False):
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self.I_EVOZONE_FIRE,
                    )
                    wait_timer.reset()
                elif wait_timer.reached():
                    logger.warning('EvoZone run_alone wait fire button timeout')
                    break
                continue
            wait_timer.reset()
            if self.current_count >= self.limit_count:
                logger.info('EvoZone count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('EvoZone time limit out')
                break
            # 点击挑战
            fire_timer = Timer(15).start()
            while 1:
                if fire_timer.reached():
                    logger.warning('EvoZone click fire timeout')
                    break
                self.screenshot()
                if self.appear_then_click(self.I_EVOZONE_FIRE, interval=1):
                    pass

                if not self.appear(self.I_EVOZONE_FIRE):
                    self.run_general_battle(
                        config=self.config.evo_zone.general_battle_config,
                        exit_matcher=self.I_EVOZONE_FIRE,
                    )
                    wait_timer.reset()
                    break

    def run_wild(self):
        logger.error('Wild mode is not implemented')
        pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()