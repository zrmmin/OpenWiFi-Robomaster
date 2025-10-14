# PC 控制 RoboMaster 方案

## 1. 概述

本文档旨在提供一个通过PC编写程序来控制大疆RoboMaster机甲大师的完整方案。我们将使用大疆官方提供的 `robomaster` Python SDK，通过局域网与机器人进行通信。

核心步骤包括：
-   **网络配置**：确保PC和RoboMaster在同一个局域网内且可以相互通信。
-   **环境搭建**：安装Python和RoboMaster SDK。
-   **编写控制程序**：使用SDK提供的API实现对机器人底盘、云台、发射器等模块的控制。

---

## 2. 网络配置

这是实现控制最关键的一步。您提供的PC IP (`192.11.100.x`) 和 RoboMaster IP (`192.168.13.11`) 处于不同的网段，理论上无法直接通信。您提到两者可以ping通，这说明可能存在一个路由器在中间进行了数据转发。

为了保证稳定控制，请确保PC和RoboMaster处于**同一个局域网**下。通常有两种连接方式：

#### 方式一：直连模式 (AP Mode)
1.  启动RoboMaster，它会创建一个名为 `ROBOMASTER_EP_XXXX` 的Wi-Fi热点。
2.  用您的PC连接到这个Wi-Fi。
3.  在这种模式下，RoboMaster的IP地址通常是固定的 `192.168.2.1`。您的PC会自动获取一个 `192.168.2.x` 的IP地址。

#### 方式二：组网模式 (STA Mode)
1.  通过官方App将RoboMaster连接到您指定的路由器Wi-Fi网络。
2.  将您的PC也连接到**同一个路由器**的Wi-Fi或有线网络。
3.  两者都会从路由器获取IP地址，例如 `192.168.13.x`。您需要通过App或路由器后台查看RoboMaster获取到的具体IP地址。

**建议**：在开始编程前，请再次确认您的PC在连接到机器人所在的网络后，获取到的IP地址与机器人的IP地址在同一个网段。例如，如果机器人是 `192.168.13.11`，您的PC也应该是 `192.168.13.x`。

---

## 3. 环境搭建

#### 3.1 安装 Python
确保您的PC上安装了 Python 3.6 或更高版本。您可以从 [Python官网](https://www.python.org/) 下载并安装。
安装时请勾选 "Add Python to PATH" 选项。

#### 3.2 安装 Robomaster SDK
打开您PC的终端（命令提示符或PowerShell），然后使用 pip 命令安装SDK库：
```bash
pip install robomaster
```
如果下载速度慢，可以考虑使用国内镜像源：
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple robomaster
```

安装完成后，您的开发环境就准备好了。

---

## 4. 核心API与示例代码

RoboMaster SDK 提供了面向对象的接口，可以方便地控制机器人的各个模块。

以下是一个简单的Python示例代码，它会连接到机器人，控制机器人前进1米，然后断开连接。

```python
# 导入robomaster库
import robomaster
from robomaster import robot

if __name__ == '__main__':
    # 初始化机器人对象
    # 在组网模式下，RoboMaster EP的默认IP是动态获取的，需要填入实际IP
    # 如果是直连模式，IP通常是 192.168.2.1
    ep_robot = robot.Robot()
    
    # 将 "192.168.13.11" 替换成你机器人的实际IP地址
    # conn_type='sta' 表示组网模式, 'ap' 表示直连模式
    ep_robot.initialize(conn_type="sta") 

    # 获取底盘控制对象
    ep_chassis = ep_robot.chassis

    # 控制底盘向前移动1米，速度为0.5米/秒
    # x, y, z 分别代表前/后、左/右、旋转三个方向的控制量
    # x > 0: 前进, x < 0: 后退
    # y > 0: 左移, y < 0: 右移
    # z > 0: 逆时针旋转, z < 0: 顺时针旋转
    print("控制底盘向前移动1米...")
    ep_chassis.move(x=1, y=0, z=0, xy_speed=0.5).wait_for_completed()
    print("移动完成。")

    # 释放机器人控制权
    ep_robot.close()
    print("程序结束，已断开连接。")

```

#### 如何运行代码：
1.  将以上代码保存为一个Python文件，例如 `control_test.py`。
2.  根据您的实际网络情况，修改代码中的IP地址。
3.  打开终端，进入文件所在目录，运行脚本：
    ```bash
    python control_test.py
    ```
4.  观察机器人的反应。

---

## 5. 后续步骤

基于以上框架，您可以探索更复杂的功能：
-   **云台控制**: `ep_robot.gimbal.move(...)`
-   **发射器控制**: `ep_robot.blaster.fire(...)`
-   **获取视频流**: `ep_robot.camera.start_video_stream(...)` 结合OpenCV进行显示和处理。
-   **读取传感器数据**: 订阅IMU、里程计等信息。
-   **事件响应**: 编写函数来响应机器人的事件，如掌声、姿态变化等。

您可以查阅 [官方SDK文档](https://robomaster-dev.readthedocs.io/zh_CN/latest/) 来获取所有API的详细信息。
