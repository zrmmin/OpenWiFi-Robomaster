import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import logging

# ===================================================
# --- 开启 Robomaster SDK 详细调试日志 ---
# 以下代码会将 robomaster 库内部的详细运行日志打印到启动脚本的终端窗口。
# 这对于诊断棘手的连接问题至关重要。
# ===================================================
# 1. 获取 robomaster 库的日志记录器
robomaster_logger = logging.getLogger("robomaster")
# 2. 设置日志级别为 DEBUG，这是最详细的级别
robomaster_logger.setLevel(logging.DEBUG)
# 3. 创建一个处理器，用于将日志输出到控制台（终端）
sdk_log_handler = logging.StreamHandler()
# 4. 创建一个格式化器，定义日志的输出格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sdk_log_handler.setFormatter(formatter)
# 5. 将处理器添加到日志记录器中
robomaster_logger.addHandler(sdk_log_handler)
# ===================================================


# 尝试导入 robomaster 库，如果失败则给出提示
try:
    import robomaster
    from robomaster import robot
except ImportError:
    print("错误：robomaster SDK 未安装。")
    print("请使用 'pip install robomaster' 命令进行安装。")
    exit()

# 视频流需要 opencv-python 和 Pillow
try:
    import cv2
    from PIL import Image, ImageTk
except ImportError:
    print("错误：缺少必要的库用于显示视频流。")
    print("请使用 'pip install opencv-python Pillow' 命令进行安装。")
    exit()


class RoboMasterController(tk.Tk):
    """
    RoboMaster 图形化控制主窗口
    """
    def __init__(self):
        super().__init__()
        self.title("RoboMaster GUI 控制器")
        self.geometry("600x900") # 增加了窗口高度以容纳视频

        self.ep_robot = None
        self.is_connected = False
        self.video_thread = None
        
        # --- 创建界面组件 ---
        self.create_widgets()

        # --- 绑定窗口关闭事件 ---
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # --- 主框架 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 连接控制框架 ---
        conn_frame = ttk.LabelFrame(main_frame, text="连接控制", padding="10")
        conn_frame.pack(fill=tk.X, pady=5)

        ttk.Label(conn_frame, text="机器人SN:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.sn_entry = ttk.Entry(conn_frame, width=20)
        self.sn_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.sn_entry.insert(0, "") # 留空可连接局域网内第一台机器人
        
        ttk.Label(conn_frame, text="机器人IP:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.ip_entry.insert(0, "192.168.13.11") # 默认IP

        self.connect_btn = ttk.Button(conn_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.grid(row=1, column=2, rowspan=1, padx=5, pady=5, sticky="ns")

        conn_frame.columnconfigure(1, weight=1)

        # --- 2. 日志输出框架 ---
        log_frame = ttk.LabelFrame(main_frame, text="状态日志", padding="10")
        log_frame.pack(fill=tk.X, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=5)
        self.log_text.pack(fill=tk.X, expand=True)

        # --- 3. 视频显示框架 ---
        video_frame = ttk.LabelFrame(main_frame, text="摄像头画面", padding="10")
        video_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建一个标签用于显示视频帧
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(expand=True)

        # --- 4. 底盘控制框架 ---
        chassis_frame = ttk.LabelFrame(main_frame, text="底盘控制", padding="10")
        chassis_frame.pack(fill=tk.X, pady=5)

        # 前进
        self.fwd_btn = ttk.Button(chassis_frame, text="↑\n前进", command=lambda: self.move_robot(x=0.5, y=0, z=0))
        self.fwd_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # 后退
        self.back_btn = ttk.Button(chassis_frame, text="↓\n后退", command=lambda: self.move_robot(x=-0.5, y=0, z=0))
        self.back_btn.grid(row=2, column=1, padx=5, pady=5)

        # 左移
        self.left_btn = ttk.Button(chassis_frame, text="←\n左移", command=lambda: self.move_robot(x=0, y=-0.5, z=0))
        self.left_btn.grid(row=1, column=0, padx=5, pady=5)

        # 右移
        self.right_btn = ttk.Button(chassis_frame, text="→\n右移", command=lambda: self.move_robot(x=0, y=0.5, z=0))
        self.right_btn.grid(row=1, column=2, padx=5, pady=5)

        # 左旋
        self.turn_left_btn = ttk.Button(chassis_frame, text="↺\n左旋", command=lambda: self.move_robot(x=0, y=0, z=-30))
        self.turn_left_btn.grid(row=0, column=0, padx=5, pady=5)

        # 右旋
        self.turn_right_btn = ttk.Button(chassis_frame, text="↻\n右旋", command=lambda: self.move_robot(x=0, y=0, z=30))
        self.turn_right_btn.grid(row=0, column=2, padx=5, pady=5)
        
        for i in range(3):
            chassis_frame.columnconfigure(i, weight=1)

        # --- 4. 云台控制框架 ---
        gimbal_frame = ttk.LabelFrame(main_frame, text="云台控制", padding="10")
        gimbal_frame.pack(fill=tk.X, pady=5)
        
        # 云台向上
        self.gimbal_up_btn = ttk.Button(gimbal_frame, text="↑\n向上", command=lambda: self.move_gimbal(pitch=20, yaw=0))
        self.gimbal_up_btn.grid(row=0, column=1, padx=5, pady=5)

        # 云台向下
        self.gimbal_down_btn = ttk.Button(gimbal_frame, text="↓\n向下", command=lambda: self.move_gimbal(pitch=-20, yaw=0))
        self.gimbal_down_btn.grid(row=1, column=1, padx=5, pady=5)
        
        # 云台向左
        self.gimbal_left_btn = ttk.Button(gimbal_frame, text="←\n向左", command=lambda: self.move_gimbal(pitch=0, yaw=-30))
        self.gimbal_left_btn.grid(row=1, column=0, padx=5, pady=5)

        # 云台向右
        self.gimbal_right_btn = ttk.Button(gimbal_frame, text="→\n向右", command=lambda: self.move_gimbal(pitch=0, yaw=30))
        self.gimbal_right_btn.grid(row=1, column=2, padx=5, pady=5)

        # 云台回中
        self.gimbal_recenter_btn = ttk.Button(gimbal_frame, text="回中", command=self.recenter_gimbal)
        self.gimbal_recenter_btn.grid(row=0, column=2, padx=5, pady=5)

        for i in range(3):
            gimbal_frame.columnconfigure(i, weight=1)

        self.set_controls_state('disabled')


    def log(self, message):
        """ 在日志窗口中记录信息 """
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def set_controls_state(self, state):
        """ 启用或禁用所有控制按钮 """
        for child in self.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, ttk.Button):
                        if widget != self.connect_btn: # 连接按钮除外
                             widget.config(state=state)

    def toggle_connection(self):
        """ 根据当前连接状态，执行连接或断开操作 """
        if self.is_connected:
            self.disconnect_robot()
        else:
            # 在新线程中执行连接，避免GUI卡死
            threading.Thread(target=self.connect_robot, daemon=True).start()

    def connect_robot(self):
        """ 连接到RoboMaster """
        self.connect_btn.config(state='disabled')
        self.log("正在初始化SDK...")

        # --- 获取用户输入的IP和SN ---
        robot_sn = self.sn_entry.get()
        robot_ip = self.ip_entry.get()

        if not robot_ip:
            self.log("错误：请输入机器人的IP地址！")
            self.connect_btn.config(state='normal')
            return

        # 如果SN为空, SDK将自动查找
        if not robot_sn:
            robot_sn = None
            self.log(f"SN为空, 将尝试连接IP为 {robot_ip} 的机器人...")
        else:
            self.log(f"正在尝试连接SN为 {robot_sn}, IP为 {robot_ip} 的机器人...")

        try:
            # --- 关键改动：在创建机器人对象之前，就设置好全局IP ---
            # 这会强制后续的所有SDK操作都使用这个指定的IP地址
            robomaster.config.ep_ip = robot_ip

            # 现在再创建机器人实例
            self.ep_robot = robot.Robot()

            # 初始化连接
            self.ep_robot.initialize(conn_type="sta", sn=robot_sn)

            self.is_connected = True
            self.log("机器人连接成功！")

            # --- 开启视频流 ---
            self.log("正在开启视频流...")
            self.ep_robot.camera.start_video_stream(display=False, resolution=robot.camera.STREAM_720P)
            self.video_thread = threading.Thread(target=self.update_video_feed, daemon=True)
            self.video_thread.start()
            
            self.connect_btn.config(text="断开")
            self.set_controls_state('normal')

        except TypeError as e:
            # 针对旧版本SDK(0.1.1.68)的特定BUG进行处理
            # 这个版本在连接失败时会抛出TypeError，而不是一个标准的异常
            # 此时机器人对象处于损坏状态，不能调用 close() 方法
            self.log(f"连接失败 (SDK Bug): {e}")
            self.log(f"这很可能意味着无法找到机器人。请仔细检查以下几点：")
            self.log(f"1. 机器人IP地址 ({robot_ip}) 是否正确。")
            self.log("2. PC和机器人之间的网络是否畅通（可以 ping 通）。")
            self.log("3. 机器人是否已开机并处于组网模式。")
            self.is_connected = False
            # 将损坏的对象丢弃
            self.ep_robot = None

        except Exception as e:
            # 捕获其他可能的异常
            self.log(f"连接时发生未知错误: {e}")
            self.is_connected = False
            if self.ep_robot:
                try:
                    # 当机器人对象处于不确定状态时，关闭操作也可能失败
                    self.ep_robot.close()
                except Exception as close_e:
                    self.log(f"关闭机器人对象时出错: {close_e}")

        finally:
            self.connect_btn.config(state='normal')

    def disconnect_robot(self):
        """ 断开与RoboMaster的连接 """
        if self.ep_robot and self.is_connected:
            self.log("正在断开连接...")
            
            # --- 停止视频流 ---
            self.is_connected = False # 先设置标志位，让视频线程退出
            time.sleep(0.5) # 等待线程退出
            self.ep_robot.camera.stop_video_stream()
            self.log("视频流已停止。")
            self.video_label.config(image='') # 清空画面

            self.ep_robot.close()
            self.log("连接已断开。")
            self.connect_btn.config(text="连接")
            self.set_controls_state('disabled')

    def move_robot(self, x, y, z):
        """ 控制底盘移动 """
        if self.is_connected:
            self.log(f"执行底盘移动: x={x}, y={y}, z={z}")
            self.ep_robot.chassis.move(x=x, y=y, z=z, xy_speed=0.7, z_speed=45).wait_for_completed()
            self.log("移动完成。")

    def move_gimbal(self, pitch, yaw):
        """ 控制云台移动 """
        if self.is_connected:
            self.log(f"执行云台移动: pitch={pitch}, yaw={yaw}")
            self.ep_robot.gimbal.move(pitch=pitch, yaw=yaw, pitch_speed=100, yaw_speed=100).wait_for_completed()
            self.log("云台移动完成。")
            
    def recenter_gimbal(self):
        """ 云台回中 """
        if self.is_connected:
            self.log("云台回中...")
            self.ep_robot.gimbal.recenter(pitch_speed=100, yaw_speed=100).wait_for_completed()
            self.log("云台已回中。")

    def update_video_feed(self):
        """ 在独立线程中获取并更新视频画面 """
        while self.is_connected:
            try:
                # 读取一帧图像
                img = self.ep_robot.camera.read_cv2_image(timeout=0.5)
                if img is not None:
                    # 获取标签的尺寸
                    label_w = self.video_label.winfo_width()
                    label_h = self.video_label.winfo_height()

                    # 保持宽高比进行缩放
                    h, w, _ = img.shape
                    ratio = min(label_w / w, label_h / h)
                    new_w, new_h = int(w * ratio), int(h * ratio)

                    if new_w > 0 and new_h > 0:
                        # 缩放图像
                        resized_img = cv2.resize(img, (new_w, new_h))
                        
                        # BGR to RGB
                        cv2image = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
                        
                        # 转换为Tkinter格式
                        pil_img = Image.fromarray(cv2image)
                        tk_img = ImageTk.PhotoImage(image=pil_img)
                        
                        # 在GUI上更新图像
                        self.video_label.config(image=tk_img)
                        # 必须保留对图像的引用，否则会被垃圾回收
                        self.video_label.image = tk_img
                else:
                    # 等待一下再重试
                    time.sleep(0.1)
            except Exception as e:
                self.log(f"视频流错误: {e}")
                time.sleep(1)


    def on_closing(self):
        """ 关闭窗口时的清理操作 """
        self.disconnect_robot()
        self.destroy()

if __name__ == '__main__':
    app = RoboMasterController()
    app.mainloop()
