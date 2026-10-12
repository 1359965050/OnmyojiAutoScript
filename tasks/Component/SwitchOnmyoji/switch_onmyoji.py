from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.base.timer import Timer
from module.logger import logger
from tasks.Component.SwitchOnmyoji.assets import SwitchOnmyojiAssets
from tasks.Component.SwitchOnmyoji.config import Onmyoji
from tasks.base_task import BaseTask


class SwitchOnmyoji(BaseTask, SwitchOnmyojiAssets):

    def is_in_onmyodo_main(self) -> bool:
        """是否在阴阳术主界面"""
        return (
            self.appear(self.I_ONMYOJI_SWITCH)
            or self.appear(self.I_HERO_CHECK)
            or self.appear(self.I_ONMYOJI_CHECK)
        )

    def is_in_exchange_page(self) -> bool:
        """是否在角色交换界面（阴阳师交换 / 英杰交换）"""
        return self.appear(self.I_UI_BACK_BLUE)

    def is_hero_tab_active(self) -> bool:
        """当前交换页面是否在英杰标签"""
        if self.ocr_appear(self.O_EXCHANGE_HERO_TITLE):
            return True
        if self.ocr_appear(self.O_EXCHANGE_ONMYOJI_TITLE):
            return False
        # 亮度兜底判定（激活标签为亮色纸张约188，未激活为深色木质约100）
        img = self.device.image
        hero_mean = img[450:520, 25:70].mean()
        onm_mean = img[220:300, 25:70].mean()
        return hero_mean > onm_mean

    def enter_exchange_page(self, timeout: float = 10) -> bool:
        """从阴阳术主界面点击交替按钮进入交换界面"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.is_in_exchange_page():
                logger.info("Entered exchange page")
                return True
            if self.appear_then_click(self.I_ONMYOJI_SWITCH, interval=1.0):
                continue
        logger.warning("enter_exchange_page timeout")
        return False

    def switch_exchange_tab(self, target_hero: bool, timeout: float = 10) -> bool:
        """在交换界面切换到目标标签（英杰或阴阳师）"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.is_hero_tab_active() == target_hero:
                tab_name = "英杰" if target_hero else "阴阳师"
                logger.info(f"Exchange tab switched to: {tab_name}")
                return True
            if target_hero:
                self.click(self.C_SWITCH_TAB_HERO, interval=1.0)
            else:
                self.click(self.C_SWITCH_TAB_ONMYOJI, interval=1.0)
        logger.warning(f"switch_exchange_tab to hero={target_hero} timeout")
        return False

    def _get_role_battle_rule(self, role: Onmyoji) -> RuleImage | None:
        mapping = {
            Onmyoji.SEIMI: self.I_SEIMI_BATTLE,
            Onmyoji.KAGURA: self.I_KAGURA_BATTLE,
            Onmyoji.HIROMASA: self.I_HIROMASA_BATTLE,
            Onmyoji.YAO_BIKUNI: self.I_YAO_BIKUNI_BATTLE,
            Onmyoji.YORIMITSU: self.I_YORIMITSU_BATTLE,
            Onmyoji.MICHINAGA: self.I_MICHINAGA_BATTLE,
        }
        return mapping.get(role)

    def _get_role_click_rule(self, role: Onmyoji) -> RuleClick | None:
        """获取角色卡位的点击规则（若卡片未出战时，点击对应卡位出战）"""
        mapping = {
            Onmyoji.SEIMI: self.C_SELECT_SEIMI,
            Onmyoji.KAGURA: self.C_SELECT_KAGURA,
            Onmyoji.HIROMASA: self.C_SELECT_HIROMASA,
            Onmyoji.YAO_BIKUNI: self.C_SELECT_YAO_BIKUNI,
            Onmyoji.YORIMITSU: self.C_SELECT_YORIMITSU,
            Onmyoji.MICHINAGA: self.C_SELECT_MICHINAGA,
        }
        return mapping.get(role)

    def select_role_in_exchange(self, role: Onmyoji, timeout: float = 12) -> bool:
        """在交换界面中确认或点击目标角色出战。

        注意：实机点击卡片后，游戏会**直接完成切换并自动返回阴阳术主界面**
        （交换界面随之消失），因此除了"战"标志外，还必须以"已离开交换界面"
        作为切换成功的判定，否则会在主界面上持续盲点卡位坐标。
        """
        battle_rule = self._get_role_battle_rule(role)
        click_rule = self._get_role_click_rule(role)
        if not battle_rule or not click_rule:
            logger.warning(f"Unknown role type: {role}")
            return False

        role_name = role.value if hasattr(role, 'value') else role.name
        mx_click = 5
        timer = Timer(timeout).start()
        clicked = 0
        while not timer.reached():
            self.screenshot()
            # 1) 目标角色"战"标志已亮起，说明其已在出战状态
            if self.appear(battle_rule):
                logger.info(f"Role {role_name} is in battle")
                return True
            # 2) 点击后游戏自动完成切换并返回阴阳术主界面（已离开交换界面即视为成功）
            if clicked and not self.is_in_exchange_page() and self.is_in_onmyodo_main():
                logger.info(f"Role {role_name} switched, auto returned to onmyodo main")
                return True
            # 3) 未出战时拟人化点击对应卡位（设上限熔断，杜绝盲点死循环）
            if clicked >= mx_click:
                logger.warning(f"select_role_in_exchange {role_name} reach click limit {mx_click}")
                break
            if self.click(click_rule, interval=1.2):
                clicked += 1
        logger.warning(f"select_role_in_exchange {role_name} timeout")
        return False

    def exit_exchange_page(self, timeout: float = 10) -> bool:
        """从交换界面点击蓝色返回箭头退回阴阳术主界面"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.is_in_onmyodo_main():
                logger.info("Returned to onmyodo main page")
                return True
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1.0):
                continue
        logger.warning("exit_exchange_page timeout")
        return False

    def switch_onmyoji(self, onmyoji: Onmyoji):
        """
        切换阴阳师 / 英杰。
        不论阴阳师之间切换还是英杰之间切换，统一通过阴阳术主界面的“交替”按钮进入交换界面进行操作。
        :param onmyoji: 目标阴阳师/英杰
        """
        logger.hr('切换阴阳师/英杰', 2)
        is_hero = onmyoji in [Onmyoji.YORIMITSU, Onmyoji.MICHINAGA]
        target_name = onmyoji.value if hasattr(onmyoji, 'value') else onmyoji.name
        logger.info(f'Switch onmyoji target: {target_name} (is_hero={is_hero})')

        # 1. 在阴阳术主界面点击交替按钮进入交换界面
        if not self.enter_exchange_page():
            logger.warning(f'Switch onmyoji aborted: enter exchange page failed ({target_name})')
            return False

        # 2. 切换至对应标签（英杰 / 阴阳师）
        if not self.switch_exchange_tab(is_hero):
            logger.warning(f'Switch onmyoji aborted: switch exchange tab failed ({target_name})')
            return False

        # 3. 选中目标角色出战
        if not self.select_role_in_exchange(onmyoji):
            logger.warning(f'Switch onmyoji failed: select role in exchange timeout ({target_name})')

        # 4. 返回阴阳术主界面
        if not self.exit_exchange_page():
            logger.warning(f'Switch onmyoji failed: exit exchange page timeout ({target_name})')

        logger.info(f'Switch onmyoji complete: {target_name}')
        return True

    def _get_onmyoji_battle_dict(self):
        """获取阴阳师出战图标映射（兼容老调用）"""
        return {
            Onmyoji.SEIMI: self.I_SEIMI_BATTLE,
            Onmyoji.KAGURA: self.I_KAGURA_BATTLE,
            Onmyoji.HIROMASA: self.I_HIROMASA_BATTLE,
            Onmyoji.YAO_BIKUNI: self.I_YAO_BIKUNI_BATTLE,
        }

    def _get_hero_battle_dict(self):
        """获取英杰出战图标映射（兼容老调用）"""
        return {
            Onmyoji.YORIMITSU: self.I_YORIMITSU_BATTLE,
            Onmyoji.MICHINAGA: self.I_MICHINAGA_BATTLE,
        }


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = SwitchOnmyoji(c, d)

    t.switch_onmyoji(Onmyoji.MICHINAGA)
