import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import socket

# --- 视频流与图像处理依赖 ---
# 请确保已安装所需库: pip install opencv-python Pillow pyh264
try:
    import cv2
    from PIL import Image, ImageTk
    from pyh264.decoder import Decoder
    import numpy as np
except ImportError:
    print("="*40)
    print("错误：缺少视频功能所需的依赖库。")
    print("请打开终端并运行以下命令进行安装:")
    print("pip install opencv-python Pillow pyh264")
    print("="*40)
    exit()


class RoboMasterController(tk.Tk):
    """
    RoboMaster 图形化控制主窗口 (明文SDK - TCP模式)
    """
    def __init__(self):
        super().__init__()
        self.title("RoboMaster GUI 控制器 - [明文SDK-TCP模式]")
        self.geometry("600x850") # 增加窗口高度以容纳新组件

        # 网络与连接状态
        self.robot_ip = ""
        self.control_port = 40923 # 控制命令TCP端口
        self.video_port = 40921   # 视频流TCP端口
        self.control_sock = None
        self.video_sock = None
        self.is_connected = False
        self.is_video_on = False

        # 后台线程
        self.heartbeat_thread = None
        self.listen_thread = None
        self.video_thread = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 连接与视频控制 ---
        conn_frame = ttk.LabelFrame(main_frame, text="连接与视频", padding="10")
        conn_frame.pack(fill=tk.X, pady=5)
        conn_frame.columnconfigure(1, weight=1)

        ttk.Label(conn_frame, text="机器人IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.ip_entry.insert(0, "192.168.13.11")

        self.connect_btn = ttk.Button(conn_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.video_btn = ttk.Button(conn_frame, text="开启视频", command=self.toggle_video_stream)
        self.video_btn.grid(row=0, column=3, padx=5, pady=5)

        # --- 视频显示 ---
        video_frame = ttk.LabelFrame(main_frame, text="摄像头画面", padding="10")
        video_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.video_label = ttk.Label(video_frame, text="视频流关闭", anchor=tk.CENTER)
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # --- 日志 ---
        log_frame = ttk.LabelFrame(main_frame, text="状态日志", padding="10")
        log_frame.pack(fill=tk.X, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=4)
        self.log_text.pack(fill=tk.X, expand=True)

        # --- 机器人控制 ---
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.X, pady=5, expand=True)
        
        base_tab = ttk.Frame(notebook, padding=10)
        arm_tab = ttk.Frame(notebook, padding=10)
        notebook.add(base_tab, text='基础控制')
        notebook.add(arm_tab, text='机械臂控制')

        # --- 基础控制选项卡 ---
        control_frame = ttk.LabelFrame(base_tab, text="1. 机器人控制", padding="10")
        control_frame.pack(fill=tk.X)
        self.control_btn = ttk.Button(control_frame, text="开启控制 (获取控制权)", command=lambda: self.send_command("robot mode chassis_lead;"))
        self.control_btn.pack()

        chassis_frame = ttk.LabelFrame(base_tab, text="2. 底盘控制", padding="10")
        chassis_frame.pack(fill=tk.X, pady=5)
        ttk.Button(chassis_frame, text="↑\n前进", command=lambda: self.send_command("chassis speed x 0.5 y 0 z 0;")).grid(row=0, column=1)
        ttk.Button(chassis_frame, text="↓\n后退", command=lambda: self.send_command("chassis speed x -0.5 y 0 z 0;")).grid(row=2, column=1)
        ttk.Button(chassis_frame, text="←\n左移", command=lambda: self.send_command("chassis speed x 0 y -0.5 z 0;")).grid(row=1, column=0)
        ttk.Button(chassis_frame, text="→\n右移", command=lambda: self.send_command("chassis speed x 0 y 0.5 z 0;")).grid(row=1, column=2)
        ttk.Button(chassis_frame, text="↺\n左旋", command=lambda: self.send_command("chassis speed x 0 y 0 z -90;")).grid(row=0, column=0)
        ttk.Button(chassis_frame, text="↻\n右旋", command=lambda: self.send_command("chassis speed x 0 y 0 z 90;")).grid(row=0, column=2)
        ttk.Button(chassis_frame, text="■\n停止", command=lambda: self.send_command("chassis speed x 0 y 0 z 0;")).grid(row=1, column=1)
        for i in range(3): chassis_frame.columnconfigure(i, weight=1)

        gimbal_frame = ttk.LabelFrame(base_tab, text="3. 云台控制", padding="10")
        gimbal_frame.pack(fill=tk.X, pady=5)
        ttk.Button(gimbal_frame, text="↑\n向上", command=lambda: self.send_command("gimbal move p 10 y 0;")).grid(row=0, column=1)
        ttk.Button(gimbal_frame, text="↓\n向下", command=lambda: self.send_command("gimbal move p -10 y 0;")).grid(row=1, column=1)
        ttk.Button(gimbal_frame, text="←\n向左", command=lambda: self.send_command("gimbal move p 0 y -15;")).grid(row=1, column=0)
        ttk.Button(gimbal_frame, text="→\n向右", command=lambda: self.send_command("gimbal move p 0 y 15;")).grid(row=1, column=2)
        ttk.Button(gimbal_frame, text="回中", command=lambda: self.send_command("gimbal recenter;")).grid(row=0, column=2)
        for i in range(3): gimbal_frame.columnconfigure(i, weight=1)
        
        # --- 机械臂控制选项卡 ---
        arm_pos_frame = ttk.LabelFrame(arm_tab, text="机械臂位置", padding=10)
        arm_pos_frame.pack(fill=tk.X)
        ttk.Button(arm_pos_frame, text="向前", command=lambda: self.send_command("robotic_arm move x 20;")).pack(side=tk.LEFT, expand=True)
        ttk.Button(arm_pos_frame, text="向后", command=lambda: self.send_command("robotic_arm move x -20;")).pack(side=tk.LEFT, expand=True)
        ttk.Button(arm_pos_frame, text="向上", command=lambda: self.send_command("robotic_arm move y 20;")).pack(side=tk.LEFT, expand=True)
        ttk.Button(arm_pos_frame, text="向下", command=lambda: self.send_command("robotic_arm move y -20;")).pack(side=tk.LEFT, expand=True)
        ttk.Button(arm_pos_frame, text="位置复位", command=lambda: self.send_command("robotic_arm recenter;")).pack(side=tk.LEFT, expand=True)

        gripper_frame = ttk.LabelFrame(arm_tab, text="机械爪", padding=10)
        gripper_frame.pack(fill=tk.X, pady=5)
        ttk.Button(gripper_frame, text="张开", command=lambda: self.send_command("robotic_gripper open;")).pack(side=tk.LEFT, expand=True)
        ttk.Button(gripper_frame, text="闭合", command=lambda: self.send_command("robotic_gripper close;")).pack(side=tk.LEFT, expand=True)

        self.set_controls_state('disabled')

    def set_controls_state(self, state):
        # ... (禁用/启用所有控制按钮)
        self.video_btn.config(state=state)
        for child in self.winfo_children():
            if isinstance(child, ttk.Notebook):
                for tab in child.winfo_children():
                    for frame in tab.winfo_children():
                        for widget in frame.winfo_children():
                            if isinstance(widget, ttk.Button):
                                widget.config(state=state)
    
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
            time.sleep(10)
            self.send_command("robot mode free;")

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
            self.is_video_on = False
            self.video_btn.config(text="开启视频")
            # 线程会自动退出
            time.sleep(0.5)
            if self.video_sock:
                self.video_sock.close()
                self.video_sock = None
            self.video_label.config(image='', text="视频流关闭")
            self.video_label.image = None


    def receive_video_data(self):
        decoder = Decoder()
        try:
            self.log(f"正在连接视频端口: {self.robot_ip}:{self.video_port}")
            video_address = (self.robot_ip, self.video_port)
            self.video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_sock.connect(video_address)
            self.log("视频端口连接成功！等待数据...")

            while self.is_video_on:
                raw_data = self.video_sock.recv(2048)
                if not raw_data:
                    self.log("视频流连接断开。")
                    break
                
                # 使用新的解码库 pyh264
                frames = decoder.decode(raw_data)
                for framedata in frames:
                    if framedata.is_finished:
                        # pyh264直接输出Pillow Image对象
                        pil_image = framedata.image
                        # 将Pillow Image转换为OpenCV图像格式以便处理
                        frame_cv2 = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                        
                        # 在GUI上显示图像
                        self.update_video_label(frame_cv2)

        except Exception as e:
            self.log(f"视频流错误: {e}")
        finally:
            if self.is_video_on: # 如果是意外退出，也要更新UI
                self.is_video_on = False
                self.video_btn.config(text="开启视频")
            if self.video_sock:
                self.video_sock.close()
                self.video_sock = None
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

if __name__ == '__main__':
    app = RoboMasterController()
    app.mainloop()
