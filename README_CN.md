# Matrix

**Matrix** 是一个基于 **Unreal Engine 5 (UE5)** 和 **MuJoCo** 的联合仿真工具包。  
它为**机器人研究、强化学习和虚实交互**提供了统一的环境，将 UE5 的高保真渲染与物理效果和 MuJoCo 的轻量级、可微分物理引擎相结合。

---

## 📂 目录结构

```text
├── deps/                        # 第三方依赖
│   ├── ecal_5.13.3-1ppa1~jammy_amd64.deb
│   ├── mujoco_3.3.0_x86_64_Linux.deb
│   ├── onnx_1.51.0_x86_64_jammy_Linux.deb
│   └── zsibot_common*.deb
├── scripts/                     # 构建与配置脚本
│   ├── build_mc.sh
│   ├── build_mujoco_sdk.sh
│   ├── download_uesim.sh
│   ├── install_deps.sh
│   └── modify_config.sh
├── src/
│   ├── robot_mc/
│   ├── robot_mujoco/
│   ├── navigo/
│   └── UeSim/
├── build.sh                     # 一键构建脚本
├── run_sim.sh                   # 仿真启动脚本
└── README.md                    # 项目文档
```

---

## ⚙️ 环境依赖

- **操作系统：** Ubuntu 22.04  
- **推荐显卡：** NVIDIA RTX 4080 或更高  
- **Unreal Engine：** 已集成（无需单独安装）  
- **构建环境：**  
  - GCC/G++ ≥ C++11  
  - CMake ≥ 3.16  
- **MuJoCo：** 3.3.2 开源版（已集成）  
- **遥控手柄：** 必需（推荐：*Logitech Wireless Gamepad F710*）  
- **Python 依赖：** `gdown`  

---

## 🚀 安装与构建

1. **下载 UE 仿真器**

    - **方式一：Google Drive**

      [Google Drive 下载链接](https://drive.google.com/file/d/1zvpvW1np9IfS-2DA6Uca7Ufar9JY1nwu/view?usp=sharing)

      **使用 gdown 下载：**
      ```bash
      pip install gdown
      gdown https://drive.google.com/uc?id=1zvpvW1np9IfS-2DA6Uca7Ufar9JY1nwu
      ```

    - **方式二：百度网盘**  

      [百度网盘链接](https://pan.baidu.com/s/1lvhGLcZOR6CMIcnpBxt53g?pwd=d2xu)  

    - **方式三：JFrog**  

      ```bash
      curl -H "Authorization: Bearer cmVmdGtuOjAxOjE3ODQ2MDY4OTQ6eFJvZVA5akpiMmRzTFVwWXQ3YWRIbTI3TEla"  -o "matrix.zip" -# "http://192.168.50.40:8082/artifactory/jszrsim/UeSim/matrix.zip"  
      ```

2. **解压**
   ```bash
   unzip <下载文件名>
   ```

3. **安装依赖并构建**
   ```bash
   cd matrix
   ./build.sh
   ```
   *(包含依赖安装)*

---

## 🏞️ 演示环境

- **Start Map**  
  <img src="demo_gif/start_map.png" alt="Matrix Demo Screenshot" width="500"/>

- **Warehouse**  
  <img src="demo_gif/whmap.gif" alt="Matrix Warehouse Demo" width="500"/>

- **Town10**  
  <img src="demo_gif/Town10.gif" alt="Matrix Town Demo" width="500"/>

- **Yard**  
  <img src="demo_gif/Yardmap.gif" alt="Matrix Yardmap Demo" width="500"/>

> **注：** 上述截图展示了用于机器人与强化学习实验的 UE5 高保真渲染效果。

---

## ▶️ 仿真运行方式

### 无渲染模式（Headless Mode）
```bash
./run_sim.sh MapId offrender # 示例：./run_sim.sh 1 offrender
```
- MuJoCo 物理仿真窗口弹出  
- Unreal Engine 在后台运行  
- 使用 ROS 工具查看图像：
  ```bash
  sudo apt install ros-humble-image-transport*
  rqt
  ```

### 渲染模式
```bash
./run_sim.sh MapId  # 示例：./run_sim.sh 1 
```
- UE 可视化窗口弹出  
- MuJoCo 物理仿真窗口弹出  

| MapId | 地图名称      |
|-------|--------------|
| 1     | **仓库** |
| 2     | **城镇**    |
| 3     | **庭院**      |
| 4     | **crown**     |

---

## 🎮 手柄操作说明

| 动作                                 | 手柄操作                                 |
|--------------------------------------|-----------------------------------------|
| 站立 / 坐下                          | 长按 **LB** + **Y**                     |
| 前进 / 后退 / 左移 / 右移            | **左摇杆**（上 / 下 / 左 / 右）           |
| 左转 / 右转                          | **右摇杆**（左 / 右）                    |
| 前跳                                 | 长按 **RB** + **Y**                     |
| 原地跳                               | 长按 **RB** + **X**                     |
| 翻滚                                 | 长按 **RB** + **B**                     |

---

## 🔧 配置指南

### 1. 更新 MuJoCo 场景
编辑配置文件：
```bash
vim matrix/src/jszr_mujoco/simulate/config.yaml
```
### 调整传感器配置
编辑：
```bash
vim matrix/src/UeSim/jszr_mujoco_ue/Content/model/config/config.json
```

示例片段：
```json
"sensors": {
  "camera": {
    "position": { "x": 29.0, "y": 0.0, "z": 1.0 },
    "rotation": { "roll": 0.0, "pitch": 15.0, "yaw": 0.0 },
    "sensor_type": "rgb",
    "topic": "/image_raw/compressed"
  },
  "depth_sensor": {
    "position": { "x": 29.0, "y": 0.0, "z": 1.0 },
    "rotation": { "roll": 0.0, "pitch": 15.0, "yaw": 0.0 },
    "sensor_type": "depth",
    "topic": "/image_raw/compressed/depth"
  },
  "lidar": {
    "position": { "x": 13.011, "y": 2.329, "z": 17.598 },
    "rotation": { "roll": 0.0, "pitch": 0.0, "yaw": 0.0 },
    "sensor_type": "mid360",
    "topic": "/livox/lidar"
  }
}
```

- 可根据需要调整**位姿**和**传感器数量**  
- 删除未使用的传感器以提升 **UE FPS 性能**

---

## 📡 传感器数据后处理

- 深度相机以 `sensor_msgs::msg::CompressedImage` 格式发布，编码为 **MONO8**  
- 转换为单通道灰度（`int8`）图像  
- 深度值计算方式如下：  

```math
depth = pixel_value / 20
```

### 示例转换代码
```cpp
void callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
{
    cv_bridge::CvImagePtr cv_ptr;
    try {
        cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::MONO8);
    } catch (cv_bridge::Exception & e) {
        RCLCPP_ERROR(this->get_logger(), "Image conversion failed: %s", e.what());
        return;
    }
    cv_ptr->image = cv_ptr->image / 20.0;
}
```