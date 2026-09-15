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

    def _get_role_click_target(self, role: Onmyoji) -> tuple[int, int] | None:
        """获取角色的点击目标（若卡片未出战时，点击对应卡片中心位置）"""
        mapping = {
            Onmyoji.SEIMI: (310, 410),
            Onmyoji.KAGURA: (540, 410),
            Onmyoji.HIROMASA: (760, 410),
            Onmyoji.YAO_BIKUNI: (990, 410),
            Onmyoji.YORIMITSU: (540, 410),
            Onmyoji.MICHINAGA: (760, 410),
        }
        return mapping.get(role)

    def select_role_in_exchange(self, role: Onmyoji, timeout: float = 12) -> bool:
        """在交换界面中确认或点击目标角色出战"""
        battle_rule = self._get_role_battle_rule(role)
        click_coord = self._get_role_click_target(role)
        if not battle_rule or not click_coord:
            logger.warning(f"Unknown role type: {role}")
            return False

        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(battle_rule):
                role_name = role.value if hasattr(role, 'value') else role.name
                logger.info(f"Role {role_name} is in battle")
                return True
            self.click(click_coord, interval=1.2)
        logger.warning(f"select_role_in_exchange {role} timeout")
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
        self.enter_exchange_page()

        # 2. 切换至对应标签（英杰 / 阴阳师）
        self.switch_exchange_tab(is_hero)

        # 3. 选中目标角色出战
        self.select_role_in_exchange(onmyoji)

        # 4. 返回阴阳术主界面
        self.exit_exchange_page()

        logger.info(f'Switch onmyoji complete: {target_name}')

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
