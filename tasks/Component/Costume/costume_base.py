# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage
from module.logger import logger
from module.server.i18n import I18n

from tasks.Component.Costume.config import (MainType, CostumeConfig, ShikigamiType, BattleType, CourtyardAffairType)
from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.CostumeBattle.assets import CostumeBattleAssets
from tasks.Component.CostumeShikigami.assets import CostumeShikigamiAssets
from tasks.Component.CustomCourtyardAffair.assets import CustomCourtyardAffairAssets

# 庭院皮肤
# 主界面皮肤（使用字典推导式动态生成）
main_costume_model = {
    getattr(MainType, f"COSTUME_MAIN_{i}"): {
        'I_CHECK_MAIN': f'I_CHECK_MAIN_{i}',
        'I_MAIN_GOTO_EXPLORATION': f'I_MAIN_GOTO_EXPLORATION_{i}',
        'I_MAIN_GOTO_SUMMON': f'I_MAIN_GOTO_SUMMON_{i}',
        'I_MAIN_GOTO_TOWN': f'I_MAIN_GOTO_TOWN_{i}',
        'I_PET_HOUSE': f'I_PET_HOUSE_{i}',
        'I_WQ_DONE': f'I_WQ_DONE_{i}',  # 该条及以下非强制更改, 若对应庭院内容识别不到可以添加
        'I_HARVEST_SIGN': f'I_HARVEST_SIGN_{i}',
        'I_HARVEST_JADE': f'I_HARVEST_JADE_{i}',
        'I_HARVEST_MAIL': f'I_HARVEST_MAIL_{i}',
        'I_HARVEST_SOUL': f'I_HARVEST_SOUL_{i}',
        'I_HARVEST_GUILD_REWARD': f'I_HARVEST_GUILD_REWARD_{i}'
    } for i in range(1, 18)
}

# 战斗主题（使用循环处理常规情况 + 特例处理）
battle_theme_model = {}
for i in range(1, 16):
    entry = {
        'I_LOCAL': f'I_LOCAL_{i}',
        'I_EXIT': f'I_EXIT_{i}',
        'I_FRIENDS': f'I_FRIENDS_{i}',
        'I_BATTLE_INFO': f'I_BATTLE_INFO_{i}',
    }
    if i in [8, 12, 13, 14, 15]:  # 特殊处理
        entry.update({
            'I_WIN': f'I_WIN_{i}',
            'I_DE_WIN': f'I_DE_WIN_{i}',
            'I_FALSE': f'I_FALSE_{i}'
        })
    battle_theme_model[getattr(BattleType, f"COSTUME_BATTLE_{i}")] = entry

# 幕间主题
shikigami_costume_model = {
    getattr(ShikigamiType, f"COSTUME_SHIKIGAMI_{i}"): {
        # GameUi 进出式神录
        'I_CHECK_RECORDS': f'I_CHECK_RECORDS_{i}',
        'I_RECORD_SOUL_BACK': f'I_RECORD_SOUL_BACK_{i}',
        # SwitchSoul 相关
        'I_SOUL_PRESET': f'I_SOUL_PRESET_{i}',
        'I_SOU_CHECK_IN': f'I_SOU_CHECK_IN_{i}',
        'I_SOU_TEAM_PRESENT': f'I_SOU_TEAM_PRESENT_{i}',
        'I_SOU_CLICK_PRESENT': f'I_SOU_CLICK_PRESENT_{i}',
        'I_SOU_SWITCH_SURE': f'I_SOU_SWITCH_SURE_{i}',
        # SwitchSoul 分组相关 (1-7组)
        **{f'I_SOU_CHECK_GROUP_{g}': f'I_SOU_CHECK_GROUP_{g}_{i}' for g in range(1, 8)},
        # SwitchSoul 队伍相关 (1-4队)
        **{f'I_SOU_SWITCH_{t}': f'I_SOU_SWITCH_{t}_{i}' for t in range(1, 5)},
        # SoulsTidy 相关
        'I_ST_SOULS': f'I_ST_SOULS_{i}',
        'I_ST_REPLACE': f'I_ST_REPLACE_{i}',
    }
    for i in range(1, 14)  # 目前支持 COSTUME_SHIKIGAMI_1 到 COSTUME_SHIKIGAMI_13
}

# 庭院事务皮肤
courtyard_affair_model = {
    getattr(CourtyardAffairType, f"CUSTOM_COURTYARD_AFFAIR_{i}"): {
        'I_CHECK_COURTYARD_AFFAIRS': f'I_CHECK_COURTYARD_AFFAIRS_{i}',
        'I_ONE_COMPLETE': f'I_ONE_COMPLETE_{i}',
        'I_ENTER_DAILY': f'I_ENTER_DAILY_{i}',
        'I_CHECK_IN_DAILY': f'I_CHECK_IN_DAILY_{i}',
    } for i in range(1, 2)
}


# 各皮肤模块涉及替换的资源键集合（用于切换回默认主题或更换皮肤前清理旧皮肤残留）
_MAIN_ASSET_KEYS = tuple({k for m in main_costume_model.values() for k in m})
_BATTLE_ASSET_KEYS = tuple({k for m in battle_theme_model.values() for k in m})
_SHIKIGAMI_ASSET_KEYS = tuple({k for m in shikigami_costume_model.values() for k in m})
_COURTYARD_AFFAIR_ASSET_KEYS = tuple({k for m in courtyard_affair_model.values() for k in m})


class CostumeBase:
    # 全局按 RuleImage 对象 id 记录首次替换前的默认属性快照，便于切回默认皮肤时完整还原
    _original_snapshots: dict[int, tuple] = {}

    def check_costume(self, config: CostumeConfig=None):
        if config is None:
            config: CostumeConfig = self.config.model.global_game.costume_config
        self.check_costume_main(config.costume_main_type)
        self.check_costume_battle(config.costume_battle_type)
        self.check_costume_shikigami(config.costume_shikigami_type)
        self.check_custom_courtyard_affair(config.custom_courtyard_affair)

    @classmethod
    def _snapshot_original(cls, asset_object: RuleImage) -> None:
        obj_id = id(asset_object)
        if obj_id not in cls._original_snapshots:
            cls._original_snapshots[obj_id] = (
                list(asset_object.roi_front),
                asset_object.roi_back,
                asset_object.threshold,
                asset_object.method,
                asset_object.scale_range,
                asset_object.scale_step,
                asset_object.file,
            )

    @staticmethod
    def _reset_image_cache(asset_object: RuleImage) -> None:
        asset_object._image = None
        asset_object._mask_loaded = False
        asset_object._mask = None
        asset_object._kp = None
        asset_object._des = None

    def restore_img(self, asset_before: str) -> None:
        if not hasattr(self, asset_before):
            return
        asset_before_object: RuleImage = getattr(self, asset_before)
        snapshot = self._original_snapshots.get(id(asset_before_object))
        if snapshot is None:
            return
        roi_front, roi_back, threshold, method, scale_range, scale_step, file_path = snapshot
        asset_before_object.roi_front = list(roi_front)
        asset_before_object.roi_back = roi_back
        asset_before_object.threshold = threshold
        asset_before_object.method = method
        asset_before_object.scale_range = scale_range
        asset_before_object.scale_step = scale_step
        asset_before_object.file = file_path
        self._reset_image_cache(asset_before_object)

    def _restore_assets(self, asset_keys: tuple[str, ...]) -> None:
        for key in asset_keys:
            self.restore_img(key)

    def replace_img(self,
                    asset_before: str,
                    asset_after: RuleImage,
                    rp_roi_back: bool = True):
        if not hasattr(self, asset_before):
            return
        # setattr(self, asset_before, asset_after)
        asset_before_object: RuleImage = getattr(self, asset_before)
        self._snapshot_original(asset_before_object)
        asset_before_object.roi_front = asset_after.roi_front
        if rp_roi_back:
            asset_before_object.roi_back = asset_after.roi_back
        asset_before_object.threshold = asset_after.threshold
        asset_before_object.method = asset_after.method
        asset_before_object.scale_range = asset_after.scale_range
        asset_before_object.scale_step = asset_after.scale_step
        asset_before_object.file = asset_after.file
        asset_before_object._image = None
        asset_before_object._mask_loaded = False
        asset_before_object._mask = None
        asset_before_object._kp = None
        asset_before_object._des = None

    def check_costume_main(self, main_type: MainType):
        self._restore_assets(_MAIN_ASSET_KEYS)
        if main_type == MainType.COSTUME_MAIN:
            return
        logger.info(f'Switch main costume to {main_type} ({I18n.trans_zh_cn(main_type)})')
        costume_assets = CostumeAssets()
        for key, value in main_costume_model[main_type].items():
            assert_value: RuleImage = getattr(costume_assets, value, None)
            if assert_value is None:
                continue
            self.replace_img(key, assert_value)

    def check_costume_battle(self, battle_type: BattleType):
        self._restore_assets(_BATTLE_ASSET_KEYS)
        if battle_type == BattleType.COSTUME_BATTLE_DEFAULT:
            return
        logger.info(f'Switch battle theme {battle_type} ({I18n.trans_zh_cn(battle_type)})')
        costume_battle_assets = CostumeBattleAssets()
        for key, value in battle_theme_model[battle_type].items():
            assert_value: RuleImage = getattr(costume_battle_assets, value)
            # 绿标的坐标点范围不变
            if key == 'I_LOCAL':
                self.replace_img(key, assert_value, rp_roi_back=False)
            else:
                self.replace_img(key, assert_value)

    def check_costume_shikigami(self, shikigami_type: ShikigamiType):
        self._restore_assets(_SHIKIGAMI_ASSET_KEYS)
        if shikigami_type == ShikigamiType.COSTUME_SHIKIGAMI_DEFAULT:
            return
        logger.info(f'Switch shikigami theme {shikigami_type} ({I18n.trans_zh_cn(shikigami_type)})')
        shikigami_assets = CostumeShikigamiAssets()
        model = shikigami_costume_model.get(shikigami_type, {})
        for key, value in model.items():
            if not hasattr(shikigami_assets, value):
                # 尚未采集完成的资产，跳过
                continue
            assert_value: RuleImage = getattr(shikigami_assets, value)
            # 一般不需要固定 back ROI，如确有需要可在此为特例设置 rp_roi_back=False
            self.replace_img(key, assert_value)

    def check_custom_courtyard_affair(self, courtyard_affair_type: CourtyardAffairType):
        self._restore_assets(_COURTYARD_AFFAIR_ASSET_KEYS)
        if courtyard_affair_type == CourtyardAffairType.CUSTOM_COURTYARD_AFFAIR_DEFAULT:
            return
        logger.info(f'Switch courtyard affair {courtyard_affair_type} ({I18n.trans_zh_cn(courtyard_affair_type)})')
        courtyard_affair_assets = CustomCourtyardAffairAssets()
        for key, value in courtyard_affair_model[courtyard_affair_type].items():
            assert_value: RuleImage = getattr(courtyard_affair_assets, value)
            self.replace_img(key, assert_value)


if __name__ == '__main__':
    c = CostumeBase()
    c.check_costume_main(MainType.COSTUME_MAIN_2)
