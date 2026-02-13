"""
Robot message types for BIC laboratory automation.

Message definitions for communication between agent service and robot
via message queue. Includes task commands and result messages for:
- Cartridge and tube rack setup
- Column chromatography (CC) operations
- Rotary evaporation (RE) operations
- Photo capture
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# region Enums


# -- Infrastructure & Identity


class DeviceType(StrEnum):
    """设备类型, 根据目前我们支持的设备类型不断添加

    1. 我们目前的过柱机: 客户现场是300+, 我们的是300
    2. 我们自研的过柱机通用外置机构: 暂且称为第一代
    3. 我们目前用的旋蒸机: https://www.buchi.com/ja/products/instruments/rotavapor-r-180
    4. 我们目前用的真空泵: https://shop.vacuubrand.com/en/vario-chemistry-pumping-unit-pc-3001-vario-select-vp-6319.html
    """

    CC_ISCO_300P = "cc-isco-300p"
    CC_AUX_C12_GEN1 = "cc-aux-c12-gen1"
    RE_BUCHI_R180 = "re-buchi-r180"
    PP_VACUUBRAND_PC3001 = "pp-vacuubrand-pc3001"


class DeviceID(StrEnum):
    """目前实验室投入给机器人使用的设备ID"""

    CC_ISCO_300P_001 = "cc-isco-300p_001"
    CC_AUX_C12_GEN1_001 = "cc-aux-c12-gen1_001"
    RE_BUCHI_R180_001 = "re-buchi-r180_001"
    PP_VACUUBRAND_PC3001_001 = "pp-vacuubrand-pc3001_001"


class DeviceComponent(StrEnum):
    """设备内可拍摄/可操作的部位"""

    SCREEN = "screen"


class WorkStation(StrEnum):
    """机器人工作站点定义"""

    # 备料区, staging area
    # L型备料区: 硅胶住, 样品柱, 废液桶
    WS_BIC_09_SA_001 = "ws_bic_09_sa_001"
    # 试管架备料区
    WS_BIC_09_SA_002 = "ws_bic_09_sa_002"
    # 试管废弃桶备料区
    WS_BIC_09_SA_003 = "ws_bic_09_sa_003"

    # 通风橱, fume hood
    # 过柱通风橱
    WS_BIC_09_FH_001 = "ws_bic_09_fh_001"
    # 旋蒸通风橱
    WS_BIC_09_FH_002 = "ws_bic_09_fh_002"


# -- Task & Robot States


class TaskType(StrEnum):
    """Robot task command types."""

    # 任务类型：架设柱子
    # 1. 去备料区（不需要指定站点，机器人自己知道现场存有所需物料的备料区的具体位置）：
    #   - 取指定规格的硅胶柱：无特殊性，只需要指定规格，机器人自己看着随便拿一个
    #   - 取指定位置的样品柱：有特殊性，需要指定位置，机器人需要根据位置去取
    # 2. 去过柱通风橱（需要指定站点，不过目前bic这边只有这一个通风橱）：
    #   - 架设柱子：目前bic这边只有这一个通风橱，机器人会到这里去把柱子架设到过柱机外置机构上
    SETUP_CARTRIDGES = "setup_tubes_to_column_machine"

    # 任务类型：架设试管架
    # 1. 去备料区（不需要指定站点，机器人自己知道现场存有所需试管架的具体位置）：
    #   - 取装满空试管的试管架：无特殊性，目前我们只有这一种试管架，机器人自己看着随便拿一个
    # 2. 去过柱通风橱（需要指定站点，不过目前bic这边只有这一个通风橱）：
    #   - 架设试管架
    SETUP_TUBE_RACK = "setup_tube_rack"

    # 任务类型：开始过柱
    # 1. 在过柱通风橱：
    #   - 机器人触屏操作，设定一系列过柱参数，开始过柱
    START_CC = "start_column_chromatography"

    # 任务类型：终止过柱
    # 1. 在过柱通风橱：
    #   - 机器人触屏操作，终止过柱
    TERMINATE_CC = "terminate_column_chromatography"

    # 任务类型：拍照
    # 1. 在指定站点：
    #   - 机器人对指定的对象拍摄指定局部的照片，比如在过柱通风橱，拍摄过柱机屏幕，用于AI分析
    TAKE_PHOTO = "take_photo"

    # 任务类型：收集过柱产物
    # 1. 在过柱通风橱：
    #   - 拉出试管架
    #   - 拉出右侧抽屉到预期位置
    #   - 根据指定的要收集的试管map，把一些试管的溶液，转移到茄形瓶，另一些转移到废液桶，丢弃试管
    #   - 取下茄形瓶上的漏斗，丢弃
    #   - 关上废液桶盖子
    #   - 关上右侧抽屉
    #   - 取走茄形瓶，到移动位姿
    COLLECT_CC_FRACTIONS = "collect_column_chromatography_fractions"

    # 任务类型：开始旋蒸
    # 1. 前往旋蒸通风橱：
    #   - 把茄形瓶插到旋蒸机上，开启真空泵降压到预期压力，松开手
    #   - 机器人降低茄形瓶到指定高度，使其与水浴锅里的水适当接触
    #   - 机器人触屏操作，设定转速、温度参数，并开始旋蒸
    #   - 机器人回到idle姿态，并根据入参，在开始旋蒸后一定时间，进一步调整真空泵到指定压力
    START_EVAPORATION = "start_evaporation"


class RobotState(StrEnum):
    """Robot operational states."""

    IDLE = "idle"
    WORKING = "working"
    CHARGING = "charging"


# -- Entity State Categories


class EntityState(StrEnum):
    """设备、柱子等对象的状态
    TODO：这块感觉也需要yilun来提供产品层面的最终设计。我下面写的也还不完整，有的可能也不一定合适
    """

    # 样品柱一开始未被使用应该也可以用idle来描述，过柱机、旋蒸机等设备在非工作状态也处于idle状态
    IDLE = "idle"
    # 比如过柱任务的柱子，被架设到外置机构上了，状态就变成mounted
    MOUNTED = "mounted"
    # 过柱进行中，外置机构上的硅胶柱和样品柱就处于using状态。应该我们主要关心样品柱，硅胶柱的状态可能无所谓。
    # 以及，过柱机外置机构被架设了柱子，也进入到using状态
    USING = "using"
    # 过柱终止后，样品柱就是used状态
    USED = "used"
    # 过柱机或旋蒸机在运作过程中会切换到running状态
    RUNNING = "running"


class DeviceState(StrEnum):
    """设备状态"""

    IDLE = "idle"  # 空闲
    INUSE = "using"  # 正在使用
    UNAVAILABLE = "unavailable"  # 不可用


class ConsumableState(StrEnum):
    """耗材状态"""

    UNUSED = "unused"  # 未使用
    INUSE = "inuse"  # 正在使用
    USED = "used"  # 已使用


class ToolState(StrEnum):
    """工具状态"""

    AVAILABLE = "available"  # 可用
    INUSE = "inuse"  # 正在使用
    CONTAMINATED = "contaminated"  # 已污染


class ContainerContentState(StrEnum):
    """容器内容的使用状态"""

    EMPTY = "empty"  # 完全没用过
    FILL = "fill"  # 里面有东西
    USED = "used"  # 里面有过东西, 但已经被倒出去了


class ContainerLidState(StrEnum):
    """容器盖子状态"""

    CLOSED = "closed"  # 盖子关闭
    OPENED = "opened"  # 盖子打开


class SubstanceUnit(StrEnum):
    """溶剂、样品等的单位"""

    ML = "ml"  # 毫升
    L = "l"  # 升
    G = "g"  # 克
    KG = "kg"  # 千克
    MG = "mg"  # 毫克


class TubeRackState(StrEnum):
    """试管架状态"""

    IDLE = "idle"
    MOUNTED = "mounted"
    USED = "used"
    PULLED_OUT = "pulled_out"
    READY_FOR_RECOVERY = "ready_for_recovery"


# -- CC-specific


class PeakGatheringMode(StrEnum):
    """Peak collection modes for column chromatography.
    过柱机峰收集的模式，就这三种
    """

    ALL = "all"
    PEAK = "peak"
    NONE = "none"


class CCSolvent(StrEnum):
    """Column chromatography solvents."""

    PET_ETHER = "pet_ether"
    ETHYL_ACETATE = "ethyl_acetate"
    DICHLOROMETHANE = "dichloromethane"
    METHANOL = "methanol"


class CCSiliconCartridgeType(StrEnum):
    """硅胶柱规格
    其中:
    1. 以下是目前isco nextgen 300/300+支持的硅胶柱类型
    2. 但我们目前现场暂时只支持12g, 24g, 40g这三种, 可预见未来里暂时不会增加其他类型
    """

    S4G = "silica_4g"
    S12G = "silica_12g"
    S24G = "silica_24g"
    S40G = "silica_40g"
    S80G = "silica_80g"
    S120G = "silica_120g"
    S125G = "silica_125g"
    S220G = "silica_220g"
    S330G = "silica_330g"
    S750G = "silica_750g"
    S1500G = "silica_1500g"


class CCSampleCartridgeType(StrEnum):
    """样品柱规格
    其中:
    1. 我们目前只支持这一种样品柱, 可预见未来里暂时不会增加其他类型
    """

    S40G = "sample_40g"


class CCSampleCartridgeLocation(StrEnum):
    """样品柱位置
    注意:
    1. 现场目前只支持一个位置, 这里暂时严格按现场情况来, 但未来会支持多个值
    2. 现在现场的布局还不是以后全部摆满的最终布局, 因此这里几层几号以后会有变化
    """

    BIC_09B_L3_002 = "bic_09B_l3_002"


class CCRackType(StrEnum):
    """试管架类型
    1. 以下是目前isco nextgen 300/300+支持的试管架类型
    2. 但我们目前现场暂时只支持16x150这一种。
    """

    R13X100 = "13x100"
    R16X100 = "16x100"
    R16X125 = "16x125"
    R16X150 = "16x150"
    R18X150 = "18x150"
    R18X180 = "18x180"
    R25X150 = "25x150"
    R25X95 = "25x95"


# endregion


# region Shared Types


class Substance(BaseModel):
    """溶剂、样品等的定义"""

    name: str = Field(title="名称", description="常用英文名")
    zh_name: str = Field(title="中文名称", default="")
    unit: SubstanceUnit = Field(title="单位", description="比如毫升")
    amount: float = Field(title="量", description="比如500毫升")


class ContainerState(BaseModel):
    """容器状态"""

    content_state: ContainerContentState = Field(
        title="内容物状态",
        description="表示容器里面东西的状态, 比如空的, 有东西, 有过东西",
    )
    has_lid: bool = Field(title="是否有盖", description="True表示有, False表示没有")
    lid_state: ContainerLidState | None = Field(title="盖子状态", description="如果有盖子，就表示盖子的状态")
    substance: Substance | None = Field(title="", description="如果容器有子项，就表示子项的状态")


class CapturedImage(BaseModel):
    """Captured image metadata."""

    work_station: WorkStation = Field(title="要前往拍摄的站点id", description="机器人前往该站点进行拍摄")
    device_id: DeviceID = Field(title="被拍摄设备id", description="labrun提供，用于后续log/result追踪")
    device_type: DeviceType = Field(
        title="设备类型",
        description="不同设备类型包含不同components，以及对应的机器人动作都会不同，因此需要指定",
    )
    component: DeviceComponent = Field(
        title="设备内的可拍摄部位",
        description="每个设备可能包含不同的若干个可拍摄部位, 比如过柱机有screen",
    )
    url: str = Field(title="图片url", description="我们图片存在边缘计算机上的对象存储服务上，比如minio，这里提供路径")
    create_time: str = Field(title="拍摄时间", description="格式如: 2026-02-04_16:18:39.234")


# endregion


# region Messages


class RobotCommand[P: BaseModel](BaseModel):
    """Command message sent to robot via MQ.
    向机器人下发task请求的基本参数结构
    """

    task_id: str = Field(title="任务ID", description="由labrun分配指定, 后续robot回传的消息里也会带上对应的task_id")
    task_type: TaskType = Field(title="任务类型", description="是一个enum的有限集")
    params: P = Field(title="任务参数", description="字典，因任务而异")


class RobotHeartbeat(BaseModel):
    """Heartbeat message received from robot via MQ heartbeat queue."""

    timestamp: str
    state: RobotState
    Work_station: WorkStation | None = None


class RobotResult(BaseModel):
    """Result message received from robot via MQ.
    机器人返回result或log的通用结构。如果是一般的text日志，则code就200，主要log内容
    在msg里，task_id有的话就用对应的正在进行的task_id，否则可能也为空。updates和images如果没有也可能为空。
    """

    code: int = Field(title="结果状态码", description="200表示成功，其它的我们回头再整理")
    msg: str = Field(title="消息", description="文本信息")
    task_id: str = Field(
        title="任务ID",
        description="由前面labrun调用时提供，机器人回传log和result使用这个结构体时，附上",
    )
    updates: list["EntityUpdate"] = Field(
        default=[],
        title="状态更新list",
        description="包含物料、设备等对象的状态更新",
    )
    images: list[CapturedImage] | None = Field(
        default=None,
        title="照片",
        description="机器人回传的消息里有时可能带有一些拍摄的照片，具体参见下面CapturedImage的定义",
    )


# endregion


# region Experiment Parameters


class CCGradientConfig(BaseModel):
    """Column chromatography gradient configuration."""

    duration_minutes: float = Field(title="梯度持续时间", description="单位分钟")
    solvent_b_ratio: float = Field(title="溶剂B流量占比", description="0-100, 表示百分之多少")


class CCExperimentParams(BaseModel):
    """Column chromatography experiment parameters."""

    silicone_cartridge: CCSiliconCartridgeType = Field(
        title="硅胶柱规格",
        default=CCSiliconCartridgeType.S40G,
        description="Silica column spec, e.g. '40g'",
    )
    peak_gathering_mode: PeakGatheringMode = Field(
        title="峰收集模式",
        default=PeakGatheringMode.PEAK,
        description="Peak gathering mode: all, peak, none, 一般都是峰收集",
    )
    air_purge_minutes: float = Field(
        title="空气吹扫时长",
        default=1.2,
        description="300+我们当前默认采用结束后手动控制吹扫, 实测1分10秒差不多就可以了",
    )
    run_minutes: int = Field(
        title="运行时长",
        default=30,
        description=(
            "过柱环节的总运行时长, 这个根据样品而定的, 目前我们测试用的样品师兄给的默认是30分钟, 但往往会提前结束"
        ),
    )
    solvent_a: CCSolvent = Field(title="溶剂A", default=CCSolvent.PET_ETHER, description="过柱时使用的溶剂A")
    solvent_b: CCSolvent = Field(title="溶剂B", default=CCSolvent.ETHYL_ACETATE, description="过柱时使用的溶剂B")
    gradients: list[CCGradientConfig] = Field(
        title="梯度参数",
        default=[],
        description="默认参数其实是(0, 0), (1.1, 0), (22.6, 100), (6.3, 100)。实际格式不是元组，我这里只是为了方便",
    )
    need_equilibration: bool = Field(title="是否需要润柱", default=True, description="通常都是需要的")
    left_rack: CCRackType | None = Field(
        title="左试管架规格",
        default=CCRackType.R16X150,
        description=(
            "BIC这边300+其实自动识别的，但我们家的300型号需要手动设置，为了兼容，保留这个参数，"
            "但默认就是我们目前使用的这个规格，因此你传的时候，暂时可以省略没关系"
        ),
    )
    right_rack: CCRackType | None = Field(
        title="右试管架规格",
        default=None,
        description="我们暂时只用了一个左试管架, 右边留空",
    )


class EvaporationTrigger(BaseModel):
    """Trigger condition for evaporation profile changes."""

    type: Literal["time_from_start", "event"]
    time_in_sec: int | None = Field(default=None, description="Delay in seconds")
    event_name: str | None = Field(default=None, description="Event name for event trigger")


class EvaporationProfile(BaseModel):
    """Evaporation parameter profile."""

    lower_height: float = Field(description="Flask lowering height in mm, 可以为空，表示保持不变")
    rpm: int = Field(description="Rotation speed in rpm, 可以为空，表示保持不变")
    target_temperature: float = Field(description="Water bath temp in Celsius, 可以为空，表示保持不变")
    target_pressure: float = Field(description="Vacuum pressure in mbar")
    trigger: EvaporationTrigger | None = Field(default=None)


class EvaporationProfiles(BaseModel):
    """Collection of evaporation profiles for different stages."""

    start: EvaporationProfile = Field(description="Initial profile (required)")
    updates: list[EvaporationProfile] = Field(default=[])


# endregion


# region Command Parameters


class SetupCartridgesParams(BaseModel):
    """架设柱子的参数"""

    silica_cartridge_type: CCSiliconCartridgeType = Field(
        title="硅胶柱类型",
        description="硅胶柱无特殊性，目前在实验室某型号硅胶柱在哪个备料区的哪几个位置，机器人自己记忆，并看着拿",
        default=CCSiliconCartridgeType.S12G,
    )
    sample_cartridge_location: CCSampleCartridgeLocation = Field(
        title="样品柱位置ID",
        description="样品柱具有特殊性，需要明确指定拿的位置，精确到个体",
        default=CCSampleCartridgeLocation.BIC_09B_L3_002,
    )
    sample_cartridge_type: CCSampleCartridgeType = Field(
        title="样品柱类型",
        description="样品柱的规格。其实理论上，同一种规格的样品柱只能放在某些location上，因此有了location_id，我应该能知道type是什么。但还是先提供吧。",
        default=CCSampleCartridgeType.S40G,
    )
    sample_cartridge_id: str = Field(
        title="样品柱ID",
        description="用于该次实验的样品柱唯一身份ID，用来后续追踪，labrun提供",
    )
    work_station: WorkStation = Field(
        title="工作站点ID",
        description="要去哪里架设柱子",
        default=WorkStation.WS_BIC_09_FH_001,
    )


class SetupTubeRackParams(BaseModel):
    """架设试管架的参数"""

    work_station: WorkStation = Field(
        title="要架设的目标站点ID",
        description="详见enum",
        default=WorkStation.WS_BIC_09_FH_001,
    )


class TakePhotoParams(BaseModel):
    """拍照参数"""

    work_station: WorkStation = Field(title="要拍照的目标站点ID", description="支持通风橱里两个ws")
    device_id: DeviceID = Field(title="要拍照的设备ID")
    device_type: DeviceType = Field(title="要架设的设备类型", description="详见enum")
    components: list[DeviceComponent] | DeviceComponent = Field(
        title="要拍摄的设备内的部位",
        description="详见DeviceComponent enum",
    )


class StartCCParams(BaseModel):
    """开始过柱的参数"""

    work_station: WorkStation = Field(
        title="要开始过柱的工作站点ID",
        description="详见enum",
        default=WorkStation.WS_BIC_09_FH_001,
    )
    device_id: DeviceID = Field(title="过柱机设备ID", default=DeviceID.CC_ISCO_300P_001)
    device_type: DeviceType = Field(title="过柱机型号", default=DeviceType.CC_ISCO_300P)
    experiment_params: CCExperimentParams = Field(title="实验参数")


class TerminateCCParams(BaseModel):
    """终止过柱的参数"""

    work_station: WorkStation = Field(
        title="要终止过柱的工作站点ID",
        description="详见enum",
        default=WorkStation.WS_BIC_09_FH_001,
    )
    device_id: DeviceID = Field(title="过柱机设备ID", default=DeviceID.CC_ISCO_300P_001)
    device_type: DeviceType = Field(title="过柱机型号", default=DeviceType.CC_ISCO_300P)
    experiment_params: CCExperimentParams = Field(
        title="实验参数",
        description="目前300+在结束时需要额外手动做一下空气吹扫，这里提供相关参数",
    )


class CollectCCFractionsParams(BaseModel):
    """收集过柱产物的参数"""

    work_station: WorkStation = Field(title="工作站点ID", description="详见enum", default=WorkStation.WS_BIC_09_FH_001)
    device_id: DeviceID = Field(title="过柱机设备ID", default=DeviceID.CC_ISCO_300P_001)
    device_type: DeviceType = Field(title="过柱机型号", description="详见enum", default=DeviceType.CC_ISCO_300P)
    collect_config: list[int] = Field(description="1=collect, 0=discard per tube")


class StartEvaporationParams(BaseModel):
    """开始旋蒸的参数"""

    work_station: WorkStation = Field(title="工作站点ID", description="详见enum", default=WorkStation.WS_BIC_09_FH_002)
    device_id: DeviceID = Field(title="旋蒸机设备ID", default=DeviceID.RE_BUCHI_R180_001)
    device_type: DeviceType = Field(title="旋蒸机型号", description="详见enum", default=DeviceType.RE_BUCHI_R180)
    profiles: EvaporationProfiles = Field(title="旋蒸参数")


# Concrete command types
SetupCartridgesCommand = RobotCommand[SetupCartridgesParams]
SetupTubeRackCommand = RobotCommand[SetupTubeRackParams]
TakePhotoCommand = RobotCommand[TakePhotoParams]
StartCCCommand = RobotCommand[StartCCParams]
TerminateCCCommand = RobotCommand[TerminateCCParams]
CollectCCFractionsCommand = RobotCommand[CollectCCFractionsParams]
StartEvaporationCommand = RobotCommand[StartEvaporationParams]


# endregion


# region Entity Properties


class RobotProperties(BaseModel):
    """Robot entity properties."""

    location: str = Field(title="机器人当前位置", description="用work_station_id表示")
    state: RobotState = Field(title="机器人状态", description="机器人属于设备")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class CartridgeProperties(BaseModel):
    """Cartridge (silica/sample) properties."""

    location: str = Field(title="柱子当前位置", description="这里倾向于保持用str, 由Robot描述")
    state: ConsumableState = Field(title="柱子状态", description="柱子属于耗材")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class TubeRackProperties(BaseModel):
    """Tube rack properties."""

    location: str = Field(title="试管架当前位置", description="这里倾向于保持用str, 由Robot描述")
    state: ToolState = Field(title="试管架状态", description="试管架属于工具")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class RoundBottomFlaskProperties(BaseModel):
    """Round bottom flask properties."""

    location: str = Field(title="茄形瓶当前位置", description="这里倾向于保持用str, 由Robot描述")
    state: ContainerState = Field(title="茄形瓶状态", description="茄形瓶属于容器")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class CCSExtModuleProperties(BaseModel):
    """CC external module properties."""

    state: DeviceState = Field(title="过柱机外置机构状态", description="过柱机外置机构属于设备")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class CCMachineProperties(BaseModel):
    """Column chromatography machine properties."""

    state: DeviceState = Field(title="过柱机状态", description="过柱机属于设备")
    experiment_params: CCExperimentParams | None = None
    start_timestamp: str | None = None
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )


class EvaporatorProperties(BaseModel):
    """Evaporator properties."""

    state: DeviceState = Field(title="旋蒸机状态", description="旋蒸机属于设备")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )
    lower_height: float = Field(title="下盖高度", description="旋蒸机下盖高度")
    rpm: int = Field(title="转速", description="旋蒸机转速")
    target_temperature: float = Field(title="目标温度", description="旋蒸机目标温度")
    current_temperature: float = Field(title="当前温度", description="旋蒸机当前温度")
    target_pressure: float = Field(title="目标压力", description="旋蒸机目标压力")
    current_pressure: float = Field(title="当前压力", description="旋蒸机当前压力")


class PCCChuteProperties(BaseModel):
    """Post-column-chromatography chute properties."""

    state: DeviceState = Field(title="过柱机外置机构状态", description="过柱机外置机构属于设备")
    description: str = Field(
        title="补充描述",
        description="预留一个str的补充描述字段, 允许未来Robot也许能自主添加一些补充信息",
    )
    pulled_out_mm: float = Field(title="已抽离距离", description="过柱机外置机构已抽离距离")
    pulled_out_rate: float = Field(title="抽离比例", description="过柱机外置机构抽离比例")
    closed: bool = Field(title="是否关闭", description="过柱机外置机构是否关闭")
    front_waste_bin: ContainerState | None = Field(
        title="前垃圾桶状态",
        description="过柱机外置机构前垃圾桶状态, 属于容器",
    )
    back_waste_bin: ContainerState | None = Field(
        title="后垃圾桶状态",
        description="过柱机外置机构后垃圾桶状态, 属于容器",
    )


# endregion


# region Entity Updates


class EntityUpdateBase[P: BaseModel](BaseModel):
    """Base class for entity update messages.
    通过泛型基类实现DRY，避免重复定义id和properties字段
    """

    id: str
    properties: P


class RobotUpdate(EntityUpdateBase[RobotProperties]):
    type: Literal["robot"] = "robot"


class SilicaCartridgeUpdate(EntityUpdateBase[CartridgeProperties]):
    type: Literal["silica_cartridge"] = "silica_cartridge"


class SampleCartridgeUpdate(EntityUpdateBase[CartridgeProperties]):
    type: Literal["sample_cartridge"] = "sample_cartridge"


class TubeRackUpdate(EntityUpdateBase[TubeRackProperties]):
    type: Literal["tube_rack"] = "tube_rack"


class RoundBottomFlaskUpdate(EntityUpdateBase[RoundBottomFlaskProperties]):
    type: Literal["round_bottom_flask"] = "round_bottom_flask"


class CCSExtModuleUpdate(EntityUpdateBase[CCSExtModuleProperties]):
    type: Literal["ccs_ext_module"] = "ccs_ext_module"


class CCSystemUpdate(EntityUpdateBase[CCMachineProperties]):
    type: Literal["column_chromatography_machine", "isco_combiflash_nextgen_300"]


class EvaporatorUpdate(EntityUpdateBase[EvaporatorProperties]):
    type: Literal["evaporator"] = "evaporator"


class PCCLeftChuteUpdate(EntityUpdateBase[PCCChuteProperties]):
    type: Literal["pcc_left_chute"] = "pcc_left_chute"


class PCCRightChuteUpdate(EntityUpdateBase[PCCChuteProperties]):
    type: Literal["pcc_right_chute"] = "pcc_right_chute"


EntityUpdate = Annotated[
    RobotUpdate
    | SilicaCartridgeUpdate
    | SampleCartridgeUpdate
    | TubeRackUpdate
    | RoundBottomFlaskUpdate
    | CCSExtModuleUpdate
    | CCSystemUpdate
    | EvaporatorUpdate
    | PCCLeftChuteUpdate
    | PCCRightChuteUpdate,
    Field(discriminator="type"),
]


# endregion


# region Reserved
# Kept as real code (linted & type-checked) for future reference.
# These types are NOT actively used — do not import them elsewhere.


class _BinState(StrEnum):
    """废液桶的状态，其中：open和close二选一，同时可能处于full状态，表示满了
    TODO：这块感觉也需要yilun来提供产品层面的最终设计
    """

    OPEN = "open"
    CLOSE = "close"
    FULL = "full"


class _CCSiliconCartridgeS40GLocation(StrEnum):
    """40g硅胶柱位置
    注意:
    1. 现场目前只支持一个位置, 这里暂时严格按现场情况来, 但未来会支持多个值
    2. 现在现场的布局还不是以后全部摆满的最终布局, 因此这里几层几号以后会有变化
    """

    BIC_09A_L3_001 = "bic_09A_l3_001"


class _CCSiliconCartridgeS24GLocation(StrEnum):
    """24g硅胶柱位置
    注意:
    1. 现场目前只支持一个位置, 这里暂时严格按现场情况来, 但未来会支持多个值
    2. 现在现场的布局还不是以后全部摆满的最终布局, 因此这里几层几号以后会有变化
    """

    BIC_09A_L3_002 = "bic_09A_l3_002"


class _CCSiliconCartridgeS12GLocation(StrEnum):
    """12g硅胶柱位置
    注意:
    1. 现场目前只支持一个位置, 这里暂时严格按现场情况来, 但未来会支持多个值
    2. 现在现场的布局还不是以后全部摆满的最终布局, 因此这里几层几号以后会有变化
    """

    BIC_09B_L3_001 = "bic_09B_l3_001"


# endregion
