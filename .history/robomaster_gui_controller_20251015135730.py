import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import socket

# --- 视频流与图像处理依赖 ---
# 请确保已安装所需库: pip install opencv-python Pillow
try:
    import cv2
except ImportError:
    print("="*40 + "\n错误: 缺少 'opencv-python' 库。\n请运行: pip install opencv-python\n" + "="*40)
    exit()

try:
    from PIL import Image, ImageTk
except ImportError:
    print("="*40 + "\n错误: 缺少 'Pillow' 库。\n请运行: pip install Pillow\n" + "="*40)
    exit()

try:
    import pygame
except ImportError:
    print("="*40 + "\n警告: 缺少 'pygame' 库，手柄控制功能将不可用。\n请运行: pip install pygame\n" + "="*40)
    pygame = None # 设置为None以便后续检查

# 不再需要 h264decoder 和 numpy (numpy是cv2的依赖)

class RoboMasterController(tk.Tk):
    """
    RoboMaster 图形化控制主窗口 (明文SDK - TCP模式)
    """
    def __init__(self):
        super().__init__()
        self.title("RoboMaster GUI 控制器 - [明文SDK-TCP模式]")
        self.geometry("1200x720") # 采用更适合左右布局的宽屏尺寸

        # 网络与连接状态
        self.robot_ip = ""
        self.control_port = 40923 # 控制命令TCP端口
        self.video_port = 40921   # 视频流TCP端口
        self.control_sock = None
        # self.video_sock = None # 不再需要手动管理视频socket
        self.is_connected = False
        self.is_video_on = False
        self.control_mode = tk.StringVar(value="连续") # 新增：控制模式
        self.is_gamepad_control_on = False           # 新增：手柄控制状态

        # 后台线程
        self.heartbeat_thread = None
        self.listen_thread = None
        self.video_thread = None
        self.gamepad_thread = None                   # 新增：手柄线程

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # --- 主框架，采用左右布局 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=3) # 左侧视频区占3/4
        main_frame.columnconfigure(1, weight=1) # 右侧控制区占1/4
        main_frame.rowconfigure(0, weight=1)

        # --- 左侧：视频显示区 ---
        video_frame = ttk.LabelFrame(main_frame, text="摄像头画面", padding="10")
        video_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.video_label = ttk.Label(video_frame, text="视频流关闭", anchor=tk.CENTER)
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # --- 右侧：控制面板区 ---
        control_panel = ttk.Frame(main_frame)
        control_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        control_panel.rowconfigure(2, weight=1) # 让日志区可以扩展

        # --- 右侧-上：连接与视频 ---
        conn_frame = ttk.LabelFrame(control_panel, text="连接与视频", padding="10")
        conn_frame.grid(row=0, column=0, sticky="ew")
        conn_frame.columnconfigure(0, weight=1) # 让IP输入框可伸缩

        ip_frame = ttk.Frame(conn_frame)
        ip_frame.pack(fill=tk.X)
        ip_frame.columnconfigure(1, weight=1)
        ttk.Label(ip_frame, text="机器人IP:").grid(row=0, column=0, padx=(0, 5))
        self.ip_entry = ttk.Entry(ip_frame)
        self.ip_entry.grid(row=0, column=1, sticky="ew")
        self.ip_entry.insert(0, "192.168.13.11")
        
        button_frame = ttk.Frame(conn_frame)
        button_frame.pack(fill=tk.X, pady=(5,0))
        self.connect_btn = ttk.Button(button_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        self.video_btn = ttk.Button(button_frame, text="开启视频", command=self.toggle_video_stream)
        self.video_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

        # --- 右侧-中：机器人控制 ---
        control_tabs = ttk.Notebook(control_panel)
        control_tabs.grid(row=1, column=0, sticky="ew", pady=5)
        
        base_tab = ttk.Frame(control_tabs, padding=10)
        arm_tab = ttk.Frame(control_tabs, padding=10)
        control_tabs.add(base_tab, text='基础控制')
        control_tabs.add(arm_tab, text='机械臂控制')
        
        # --- 基础控制选项卡 ---
        
        # --- 新增：模式选择 ---
        mode_frame = ttk.LabelFrame(base_tab, text="控制模式", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Radiobutton(mode_frame, text="连续", variable=self.control_mode, value="连续", command=self.on_control_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="单次", variable=self.control_mode, value="单次", command=self.on_control_mode_change).pack(side=tk.LEFT, padx=5)
        self.gamepad_radio = ttk.Radiobutton(mode_frame, text="手柄", variable=self.control_mode, value="手柄", command=self.on_control_mode_change)
        self.gamepad_radio.pack(side=tk.LEFT, padx=5)
        if not pygame:
            self.gamepad_radio.config(state='disabled')

        self.gamepad_status_label = ttk.Label(mode_frame, text="手柄: 未启动")
        self.gamepad_status_label.pack(side=tk.RIGHT, padx=5)
        
        control_frame = ttk.LabelFrame(base_tab, text="1. 机器人控制", padding="10")
        control_frame.pack(fill=tk.X)
        self.control_btn = ttk.Button(control_frame, text="开启控制 (获取控制权)", command=lambda: self.send_command("robot mode chassis_lead;"))
        self.control_btn.pack(fill=tk.X)

        chassis_frame = ttk.LabelFrame(base_tab, text="2. 底盘控制", padding="10")
        chassis_frame.pack(fill=tk.X, pady=5)
        ttk.Button(chassis_frame, text="↑\n前进", command=lambda: self.handle_chassis_move(x=0.5, y=0, z=0)).grid(row=0, column=1, sticky="ew")
        ttk.Button(chassis_frame, text="↓\n后退", command=lambda: self.handle_chassis_move(x=-0.5, y=0, z=0)).grid(row=2, column=1, sticky="ew")
        ttk.Button(chassis_frame, text="←\n左移", command=lambda: self.handle_chassis_move(x=0, y=-0.5, z=0)).grid(row=1, column=0, sticky="ew")
        ttk.Button(chassis_frame, text="→\n右移", command=lambda: self.handle_chassis_move(x=0, y=0.5, z=0)).grid(row=1, column=2, sticky="ew")
        ttk.Button(chassis_frame, text="↺\n左旋", command=lambda: self.handle_chassis_move(x=0, y=0, z=-90)).grid(row=0, column=0, sticky="ew")
        ttk.Button(chassis_frame, text="↻\n右旋", command=lambda: self.handle_chassis_move(x=0, y=0, z=90)).grid(row=0, column=2, sticky="ew")
        ttk.Button(chassis_frame, text="■\n停止", command=lambda: self.handle_chassis_move(x=0, y=0, z=0)).grid(row=1, column=1, sticky="ew")
        for i in range(3): chassis_frame.columnconfigure(i, weight=1)

        gimbal_frame = ttk.LabelFrame(base_tab, text="3. 云台控制", padding="10")
        gimbal_frame.pack(fill=tk.X)
        ttk.Button(gimbal_frame, text="↑\n向上", command=lambda: self.handle_gimbal_move(p=10, y=0)).grid(row=0, column=1, sticky="ew")
        ttk.Button(gimbal_frame, text="↓\n向下", command=lambda: self.handle_gimbal_move(p=-10, y=0)).grid(row=1, column=1, sticky="ew")
        ttk.Button(gimbal_frame, text="←\n向左", command=lambda: self.handle_gimbal_move(p=0, y=-15)).grid(row=1, column=0, sticky="ew")
        ttk.Button(gimbal_frame, text="→\n向右", command=lambda: self.handle_gimbal_move(p=0, y=15)).grid(row=1, column=2, sticky="ew")
        ttk.Button(gimbal_frame, text="回中", command=lambda: self.send_command("gimbal recenter;")).grid(row=0, column=2, sticky="ew")
        for i in range(3): gimbal_frame.columnconfigure(i, weight=1)
        
        # --- 机械臂控制选项卡 ---
        arm_pos_frame = ttk.LabelFrame(arm_tab, text="机械臂位置", padding=10)
        arm_pos_frame.pack(fill=tk.X)
        ttk.Button(arm_pos_frame, text="向前", command=lambda: self.send_command("robotic_arm move x 20;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(arm_pos_frame, text="向后", command=lambda: self.send_command("robotic_arm move x -20;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,2))
        ttk.Button(arm_pos_frame, text="向上", command=lambda: self.send_command("robotic_arm move y 20;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,2))
        ttk.Button(arm_pos_frame, text="向下", command=lambda: self.send_command("robotic_arm move y -20;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
        
        arm_recenter_frame = ttk.Frame(arm_tab)
        arm_recenter_frame.pack(fill=tk.X, pady=5)
        ttk.Button(arm_recenter_frame, text="位置复位", command=lambda: self.send_command("robotic_arm recenter;")).pack(fill=tk.X)

        gripper_frame = ttk.LabelFrame(arm_tab, text="机械爪", padding=10)
        gripper_frame.pack(fill=tk.X)
        ttk.Button(gripper_frame, text="张开", command=lambda: self.send_command("robotic_gripper open;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(gripper_frame, text="闭合", command=lambda: self.send_command("robotic_gripper close;")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

        # --- 右侧-下：日志 ---
        log_frame = ttk.LabelFrame(control_panel, text="状态日志", padding="10")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=4)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.set_controls_state('disabled')

    def set_controls_state(self, state):
        self.video_btn.config(state=state)
        # 遍历Notebook中的所有按钮
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                for panel in child.winfo_children():
                    if isinstance(panel, ttk.Frame):
                        for item in panel.winfo_children():
                           if isinstance(item, ttk.Notebook):
                                for tab in item.winfo_children():
                                    for frame in tab.winfo_children():
                                        for widget in frame.winfo_children():
                                            if isinstance(widget, ttk.Button):
                                                widget.config(state=state)
                                            elif isinstance(widget, ttk.Frame): # 机械臂复位按钮在Frame里
                                                for btn in widget.winfo_children():
                                                    if isinstance(btn, ttk.Button):
                                                        btn.config(state=state)

    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_robot()
        else:
            threading.Thread(target=self.connect_robot, daemon=True).start()

    def connect_robot(self):
        self.connect_btn.config(state='disabled')
        self.robot_ip = self.ip_entry.get()
        if not self.robot_ip: self.log("错误：请输入机器人IP地址。"); self.connect_btn.config(state='normal'); return

        try:
            address = (self.robot_ip, self.control_port)
            self.log(f"正在创建TCP控制套接字: {self.robot_ip}:{self.control_port}")
            self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.log("正在连接到机器人..."); self.control_sock.connect(address); self.log("TCP控制连接成功！")
            
            self.is_connected = True
            self.listen_thread = threading.Thread(target=self.listen_for_responses, daemon=True); self.listen_thread.start()
            self.log("发送 'command;' 进入SDK模式..."); self.send_command("command;")
            time.sleep(1)
            self.log("已进入SDK明文控制模式。")
            self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True); self.heartbeat_thread.start()
            
            self.connect_btn.config(text="断开"); self.set_controls_state('normal')
        except Exception as e:
            self.log(f"连接失败: {e}"); self.is_connected = False
            if self.control_sock: self.control_sock.close(); self.control_sock = None
        finally:
            self.connect_btn.config(state='normal')

    def disconnect_robot(self):
        self.log("正在断开连接...")
        if self.is_gamepad_control_on: self.toggle_gamepad_control() # 关闭手柄
        if self.is_video_on: self.stop_video_stream()
        if self.is_connected:
            self.send_command("robot mode free;")
            time.sleep(0.2)
            self.send_command("quit;")
            self.is_connected = False
        if self.control_sock: self.control_sock.close(); self.control_sock = None
        self.log("连接已断开。")
        self.connect_btn.config(text="连接")
        self.set_controls_state('disabled')

    def send_command(self, cmd_str):
        if self.is_connected and self.control_sock:
            try:
                self.log(f"发送: {cmd_str}")
                msg = cmd_str + ';' if not cmd_str.endswith(';') else cmd_str
                self.control_sock.send(msg.encode('utf-8'))
            except Exception as e:
                self.log(f"指令发送失败: {e}"); self.disconnect_robot()

    def listen_for_responses(self):
        while self.is_connected:
            try:
                buf = self.control_sock.recv(1024)
                if buf: self.log(f"收到响应: {buf.decode('utf-8', errors='ignore')}")
                else: self.log("机器人断开了连接。"); self.disconnect_robot(); break
            except Exception: break

    def send_heartbeat(self):
        while self.is_connected:
            # RoboMaster的明文SDK要求5秒内必须有指令，否则会断开连接
            # 同时，心跳指令不应使用 "robot mode free;"，因为它会释放控制权
            # 这里我们使用一个无害的查询指令作为心跳
            time.sleep(4)
            self.send_command("robot get version;")

    def toggle_video_stream(self):
        if self.is_video_on:
            self.stop_video_stream()
        else:
            self.start_video_stream()

    def start_video_stream(self):
        if self.is_connected and not self.is_video_on:
            self.log("正在开启视频流...")
            self.send_command("stream on;")
            self.video_thread = threading.Thread(target=self.receive_video_data, daemon=True)
            self.video_thread.start()
            self.is_video_on = True
            self.video_btn.config(text="关闭视频")

    def stop_video_stream(self):
        if self.is_connected and self.is_video_on:
            self.log("正在关闭视频流...")
            self.send_command("stream off;")
            self.is_video_on = False # 这将使视频接收线程的循环停止
            self.video_btn.config(text="开启视频")
            time.sleep(1) # 等待线程完全退出
            self.video_label.config(image='', text="视频流关闭")
            self.video_label.image = None


    def receive_video_data(self):
        """ 使用OpenCV VideoCapture直接处理TCP视频流 """
        video_url = f"tcp://{self.robot_ip}:{self.video_port}"
        cap = None
        try:
            self.log(f"正在使用OpenCV连接视频流: {video_url}")
            # 设置OpenCV不进行缓冲，以降低延迟
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            cap = cv2.VideoCapture(video_url, cv2.CAP_FFMPEG)

            if not cap.isOpened():
                self.log("错误：OpenCV无法打开视频流。请检查：")
                self.log("1. PC与机器人网络是否可达。")
                self.log("2. 是否已发送 stream on 指令。")
                self.log("3. OpenCV的ffmpeg后端是否完整。")
                self.is_video_on = False
                self.video_btn.config(text="开启视频")
                return

            self.log("视频流连接成功！正在解码...")

            while self.is_video_on:
                ret, frame = cap.read()
                if not ret:
                    self.log("无法从视频流读取帧，可能已结束。")
                    break
                
                # 在GUI上显示图像
                self.update_video_label(frame)
                
        except Exception as e:
            self.log(f"视频流错误: {e}")
        finally:
            if cap:
                cap.release()
            if self.is_video_on: # 如果是意外退出
                self.is_video_on = False
                self.video_btn.config(text="开启视频")
            self.log("视频流接收线程已退出。")
            

    def update_video_label(self, frame_cv2):
        """ 将OpenCV图像帧更新到Tkinter标签上 """
        try:
            # 缩放以适应标签大小
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            if label_w < 50 or label_h < 50: # 窗口初始化时尺寸可能很小
                label_w, label_h = 480, 360 # 给一个默认尺寸

            h, w, _ = frame_cv2.shape
            ratio = min(label_w / w, label_h / h)
            new_w, new_h = int(w * ratio), int(h * ratio)

            if new_w > 0 and new_h > 0:
                resized = cv2.resize(frame_cv2, (new_w, new_h))
                cv2image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.config(image=imgtk, text="")
                self.video_label.image = imgtk
        except Exception:
            # 忽略在关闭窗口时可能发生的tkinter错误
            pass

    def on_closing(self):
        self.disconnect_robot()
        self.destroy()

    # --- 新增：控制模式处理 ---
    def handle_chassis_move(self, x, y, z):
        mode = self.control_mode.get()
        if mode == "手柄":
            self.log("请在手柄模式下使用手柄进行控制。")
            return
            
        cmd = f"chassis speed x {x} y {y} z {z};"
        self.send_command(cmd)

        if mode == "单次" and (x != 0 or y != 0 or z != 0):
            threading.Timer(0.2, lambda: self.send_command("chassis speed x 0 y 0 z 0;")).start()

    def handle_gimbal_move(self, p, y):
        mode = self.control_mode.get()
        if mode == "手柄":
            self.log("手柄模式暂不支持控制云台。")
            return

        cmd = f"gimbal move p {p} y {y};"
        self.send_command(cmd)

        if mode == "单次":
            # 单次模式下，云台移动后不需要发停止指令
            pass

    def on_control_mode_change(self):
        mode = self.control_mode.get()
        self.log(f"控制模式已切换为: {mode}")
        if mode == "手柄":
            if not self.is_gamepad_control_on:
                self.toggle_gamepad_control()
        else:
            if self.is_gamepad_control_on:
                self.toggle_gamepad_control() # 关闭手柄控制

    def toggle_gamepad_control(self):
        if not pygame:
            self.log("错误：pygame库未加载，无法使用手柄功能。")
            return

        if self.is_gamepad_control_on:
            self.is_gamepad_control_on = False
            self.log("手柄控制已关闭。")
            self.gamepad_status_label.config(text="手柄: 未启动")
        else:
            self.is_gamepad_control_on = True
            self.log("正在启动手柄控制...")
            self.gamepad_thread = threading.Thread(target=self.gamepad_poll_loop, daemon=True)
            self.gamepad_thread.start()

    def gamepad_poll_loop(self):
        """ 循环检测手柄输入并发送指令 """
        pygame.init()
        pygame.joystick.init()
        joystick = None
        
        while self.is_gamepad_control_on:
            # 1. 检测手柄连接
            if not joystick:
                pygame.joystick.quit()
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    joystick = pygame.joystick.Joystick(0)
                    joystick.init()
                    self.log(f"已连接手柄: {joystick.get_name()}")
                    self.gamepad_status_label.config(text=f"手柄: {joystick.get_name()}")
                else:
                    self.log("未检测到手柄，请连接...")
                    self.gamepad_status_label.config(text="手柄: 未连接")
                    time.sleep(2)
                    continue
            
            # 2. 事件处理 (手柄插拔)
            should_reconnect = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_gamepad_control_on = False
                    break
                if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    joystick = None
                    should_reconnect = True
                    break
            if should_reconnect: continue
            if not self.is_gamepad_control_on: break

            # 3. 获取摇杆数据并发送指令
            # --- 新增DEBUG: 打印所有轴的值，方便调试 ---
            try:
                all_axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
                # self.log(f"手柄轴: {[f'{v:.2f}' for v in all_axes]}") # 取消此行注释以在GUI日志中查看
            except pygame.error: # 手柄可能断开
                joystick = None
                continue

            # Xbox Controller Mapping (Common on Windows)
            # 左摇杆: axis 1 (Y, 上-1/下+1), axis 0 (X, 左-1/右+1) -> 前后/左右平移
            # 右摇杆: axis 4 (X, 左-1/右+1) -> 左右旋转
            dead_zone = 0.15

            # 前后速度 (x) - Pygame Y轴向上为负，需反转
            fwd_speed = -joystick.get_axis(1) if joystick.get_numaxes() > 1 else 0
            if abs(fwd_speed) < dead_zone: fwd_speed = 0

            # 左右平移速度 (y)
            strafe_speed = joystick.get_axis(0) if joystick.get_numaxes() > 0 else 0
            if abs(strafe_speed) < dead_zone: strafe_speed = 0

            # 旋转速度 (z) - Xbox手柄右摇杆X轴通常是 axis 4
            turn_speed = joystick.get_axis(4) if joystick.get_numaxes() > 4 else 0
            if abs(turn_speed) < dead_zone: turn_speed = 0

            # 将摇杆值 (-1.0 ~ 1.0) 映射到机器人速度
            # 底盘速度: x(m/s), y(m/s), z(deg/s)
            x_val = fwd_speed * 0.7   # 最大前进速度0.7m/s
            y_val = strafe_speed * 0.7  # 最大平移速度0.7m/s
            z_val = turn_speed * 180    # 最大旋转速度180deg/s
            
            cmd = f"chassis speed x {x_val:.2f} y {y_val:.2f} z {z_val:.2f};"
            self.send_command(cmd)

            time.sleep(0.1) # 每100ms发送一次指令

        # 循环结束，停止机器人并退出pygame
        if self.is_connected:
            self.send_command("chassis speed x 0 y 0 z 0;")
        pygame.quit()
        self.log("手柄控制线程已安全退出。")


if __name__ == '__main__':
    app = RoboMasterController()
    app.mainloop()
