# Ford Edge MK2 适配 spbig 代码修改说明

> 供 sunnypilot 开发者参考：如何在 spbig 中增加 Ford Edge 车型支持。

---

## 一、车型信息

| 项 | 值 |
|----|-----|
| 内部代号 | `FORD_EDGE_MK2` |
| 车型名 | Ford Edge 2022（也兼容 Fusion Retrofited 2013-2019） |
| 整备质量 | 1691 kg |
| 转向比 | 15.3 |
| 轴距 | 2.824 m |
| 线束 | Ford Q3 |
| 雷达 | Delphi MRR |
| CAN 总线 | **非 CANFD**（标准 CAN） |
| 特殊标志 | `ALT_STEER_ANGLE = 2` |

---

## 二、核心差异说明

Ford Edge 使用 `ALT_STEER_ANGLE` 模式，与普通 Ford 车型的 CAN 消息不同：

| 功能 | Edge (ALT_STEER_ANGLE) | 普通 Ford |
|------|----------------------|-----------|
| 转向角度传感器 | `SteeringPinion_Data_Alt` + `ParkAid_Data` | `SteeringPinion_Data` |
| 传感器有效性 | ParkAid_Data 信号组合判断 | `StePinCompAnEst_D_Qf != 3` |
| 档位信号 | `TransGearData.GearLvrPos_D_Actl` | `PowertrainData_10.TrnRng_D_Rq` |

**关键注意事项**：spbig 使用 `vehicleSensorsInvalid`（负逻辑：True=传感器无效），而 FrogPilot 使用 `vehicle_sensors_valid`（正逻辑：True=传感器有效）。从 FrogPilot 参考代码时，必须加 `not` 取反。详见下文"修改 B"和"坑 4"。

---

## 三、需要修改的 6 个文件

所有文件位于 `opendbc_repo/opendbc/` 下。

### 文件 1：`car/ford/values.py`

**修改 A** — 在 `FordFlags` 类中添加 `ALT_STEER_ANGLE`：

```python
class FordFlags(IntFlag):
  CANFD = 1
  ALT_STEER_ANGLE = 2
```

**修改 B** — 在 `CAR` 类中 `FORD_BRONCO_SPORT_MK1` 之后添加：

```python
FORD_EDGE_MK2 = FordPlatformConfig(
    [
      FordCarDocs("Ford Edge 2022"),
      FordCarDocs("Ford Fusion Retrofited 2013-2019"),
    ],
    CarSpecs(mass=1691, steerRatio=15.3, wheelbase=2.824),
    flags=FordFlags.ALT_STEER_ANGLE,
)
```

### 文件 2：`car/ford/fingerprints.py`

添加 Edge 的 4 个 ECU 固件版本：

```python
CAR.FORD_EDGE_MK2: {
    (Ecu.eps, 0x730, None): [
      b'K2GC-14D003-AJ\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
    ],
    (Ecu.abs, 0x760, None): [
      b'HG9C-2D053-AH\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
      b'HG9C-2D053-MG\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
    ],
    (Ecu.fwdRadar, 0x764, None): [
      b'LB5T-14D049-AB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x706, None): [
      b'KT4T-14F397-AE\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
    ],
},
```

> `\x00` 填充长度必须精确。

### 文件 3：`car/ford/carstate.py`（最关键）

⚠️ spbig 的 carstate.py 使用 **2 空格缩进**，所有修改必须保持一致的缩进风格。

共 5 处修改：

**修改 A** — `__init__` 中档位值映射：

```python
    if CP.transmissionType == TransmissionType.automatic:
      if self.CP.flags & FordFlags.ALT_STEER_ANGLE:
        self.shifter_values = can_define.dv["TransGearData"]["GearLvrPos_D_Actl"]
      else:
        self.shifter_values = can_define.dv["PowertrainData_10"]["TrnRng_D_Rq"]
```

**修改 A2** — `self.lc_button = 0` 之后添加：

```python
    self.lc_button = 0
    self.steering_angle_offset_deg = 0.0
```

**修改 B** — `update()` 中传感器有效性验证（⚠️ 最容易出错）：

```python
    if self.CP.flags & FordFlags.ALT_STEER_ANGLE:
      ret.vehicleSensorsInvalid = not (
          int((cp.vl["ParkAid_Data"]["ExtSteeringAngleReq2"] + 1000) * 10) not in (32766, 32767)
          and cp.vl["ParkAid_Data"]["EPASExtAngleStatReq"] == 0
          and cp.vl["ParkAid_Data"]["ApaSys_D_Stat"] in (0, 1)
      )
    else:
      ret.vehicleSensorsInvalid = cp.vl["SteeringPinion_Data"]["StePinCompAnEst_D_Qf"] != 3
```

**修改 C** — `update()` 中转向角度读取：

```python
    if self.CP.flags & FordFlags.ALT_STEER_ANGLE:
      steering_angle_init = cp.vl["SteeringPinion_Data_Alt"]["StePinRelInit_An_Sns"]
      if not ret.vehicleSensorsInvalid:
        steering_angle_est = cp.vl["ParkAid_Data"]["ExtSteeringAngleReq2"]
        self.steering_angle_offset_deg = steering_angle_est - steering_angle_init
      ret.steeringAngleDeg = steering_angle_init + self.steering_angle_offset_deg
    else:
      ret.steeringAngleDeg = cp.vl["SteeringPinion_Data"]["StePinComp_An_Est"]
```

**修改 D** — `update()` 中档位读取：

```python
      if self.CP.flags & FordFlags.ALT_STEER_ANGLE:
        gear = self.shifter_values.get(cp.vl["TransGearData"]["GearLvrPos_D_Actl"])
      else:
        gear = self.shifter_values.get(cp.vl["PowertrainData_10"]["TrnRng_D_Rq"])
```

### 文件 4：`car/torque_data/override.toml`

在 `"FORD_BRONCO_SPORT_MK1"` 所在行之后插入：

```toml
"FORD_EDGE_MK2" = [nan, 1.5, nan]
```

> 三个值分别是 `LAT_ACCEL_FACTOR`、`MAX_LAT_ACCEL_MEASURED`、`FRICTION`。`nan` 使用默认值，`1.5` 为估计值。**只添加一行，不要重复**（TOML 不允许重复键）。

### 文件 5：`car/fingerprints.py`（顶层 MIGRATION 字典）

在 `"FORD BRONCO SPORT 1ST GEN"` 之后插入：

```python
"FORD EDGE 2022": FORD.FORD_EDGE_MK2,
```

### 文件 6：`sunnypilot/car/car_list.json`

添加 UI 车系列表条目：

```json
"Ford Edge 2022": {
    "platform": "FORD_EDGE_MK2",
    "make": "Ford",
    "brand": "ford",
    "model": "Edge",
    "year": ["2022"],
    "package": "Co-Pilot360 Assist+"
},
"Ford Fusion Retrofited 2013-2019": {
    "platform": "FORD_EDGE_MK2",
    "make": "Ford",
    "brand": "ford",
    "model": "Fusion Retrofited",
    "year": ["2013", "2014", "2015", "2016", "2017", "2018", "2019"],
    "package": "Co-Pilot360 Assist+"
}
```

---

## 四、文件修改速查总表

| # | 文件路径（相对于 opendbc_repo/opendbc） | 修改内容 | 易错点 |
|---|----------------------------------------|---------|--------|
| 1 | `car/ford/values.py` | 新增 `ALT_STEER_ANGLE` + `FORD_EDGE_MK2` | CarSpecs 参数正确性 |
| 2 | `car/ford/fingerprints.py` | 4 个 ECU 固件版本 | `\x00` 填充长度 |
| 3 | `car/ford/carstate.py` | 5 处 ALT_STEER_ANGLE 分支 | **2 空格缩进 + MOD B 必须 `not (`** |
| 4 | `car/torque_data/override.toml` | Edge 扭矩参数 | **只添加一行** |
| 5 | `car/fingerprints.py` | MIGRATION 映射 | 格式一致 |
| 6 | `sunnypilot/car/car_list.json` | UI 车系条目 | JSON 逗号 |

---

## 五、易踩的坑

### 坑 1：缩进风格

原始 carstate.py 使用 **2 空格缩进**，不是 4 空格。修改前用 `sed -n 1,60p` 确认风格，全部修改保持一致。

### 坑 2：TOML 不允许重复键

`override.toml` 中同一键出现两次会导致 `tomllib.TOMLDecodeError`。修改前先 `grep` 检查目标键是否已存在。

### 坑 3：缩进错误的代码被 commit

如果之前的修改已经把损坏代码提交到 git，`git checkout` 无法恢复干净版本。需要用 `git checkout <clean_parent_commit> -- 文件路径` 从干净父提交恢复。

### 坑 4：vehicleSensorsInvalid 逻辑极性（最关键）

spbig 使用 `vehicleSensorsInvalid`（**负逻辑**：True = 传感器无效），而 FrogPilot 使用 `vehicle_sensors_valid`（**正逻辑**：True = 传感器有效）。

从 FrogPilot 复制代码时只改变量名会导致逻辑完全反转——正常行驶时传感器被误判为无效，校准永远无法完成。

**FrogPilot 原版（正逻辑）：**
```python
self.vehicle_sensors_valid = (
    int((cp.vl["ParkAid_Data"]["ExtSteeringAngleReq2"] + 1000) * 10) not in (32766, 32767)
    and cp.vl["ParkAid_Data"]["EPASExtAngleStatReq"] == 0
    and cp.vl["ParkAid_Data"]["ApaSys_D_Stat"] in (0, 1)
)
```

**spbig 正确版本（负逻辑，必须加 `not`）：**
```python
ret.vehicleSensorsInvalid = not (
    int((cp.vl["ParkAid_Data"]["ExtSteeringAngleReq2"] + 1000) * 10) not in (32766, 32767)
    and cp.vl["ParkAid_Data"]["EPASExtAngleStatReq"] == 0
    and cp.vl["ParkAid_Data"]["ApaSys_D_Stat"] in (0, 1)
)
```

**验证方法**：修改完成后执行：
```bash
grep 'ret.vehicleSensorsInvalid =' car/ford/carstate.py
# 必须输出：ret.vehicleSensorsInvalid = not (
```

---

## 六、PSCM 配置说明

部分 Ford Edge 车型出厂时 PSCM（动力转向控制模块）设置为 Lane Keeping Assist 模式，不支持外部转向指令。需要用 FORScan + OBD 线将 PSCM 改为 **Lane Centering Assist** 或 **Traffic Jam Assist** 模式。

---

## 七、验证清单

```bash
# 1. override.toml 无重复键
grep -n 'FORD_EDGE_MK2' opendbc_repo/opendbc/car/torque_data/override.toml
# 应只有 1 行

# 2. ALT_STEER_ANGLE 出现次数
grep -c 'ALT_STEER_ANGLE' opendbc_repo/opendbc/car/ford/carstate.py
# 应为 5

# 3. 【关键】vehicleSensorsInvalid 有 not
grep 'ret.vehicleSensorsInvalid =' opendbc_repo/opendbc/car/ford/carstate.py
# 必须输出：ret.vehicleSensorsInvalid = not (

# 4. 语法验证
python3 -c 'compile(open("opendbc_repo/opendbc/car/ford/carstate.py").read(), "cs.py", "exec"); print("OK")'

# 5. 导入验证
python3 -c 'from opendbc.car.ford.carstate import CarState; print("OK")'

# 6. 编译
scons -j$(nproc)
```





边框颜色：
mads.enabled 且 selfdrive.enabled → 绿色 ENGAGED
仅 mads.enabled → 青色 LAT_ONLY
仅 selfdrive.enabled → 紫色 LONG_ONLY
都未开 → 蓝色 DISENGAGED
preEnabled、纵向 override、MADS paused/overriding → 灰色 OVERRIDE


