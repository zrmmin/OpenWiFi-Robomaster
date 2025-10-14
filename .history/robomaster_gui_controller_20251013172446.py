import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import socket

# --- 移除所有robomaster SDK的导入，我们将使用明文协议 ---
# try:
#     import robomaster
#     from robomaster import robot
# except ImportError:
#     print("错误：robomaster SDK 未安装。")
#     print("请使用 'pip install robomaster' 命令进行安装。")
#     exit()

# 视频流仍然需要opencv和Pillow，暂时注释掉，首先确保连接和控制成功
# try:
#     import cv2
#     from PIL import Image, ImageTk
# except ImportError:
#     print("错误：缺少必要的库用于显示视频流。")
#     print("请使用 'pip install opencv-python Pillow' 命令进行安装。")
#     exit()


class RoboMasterController(tk.Tk):
    """
    RoboMaster 图形化控制主窗口 (明文SDK - TCP模式)
    """
    def __init__(self):
        super().__init__()
        self.title("RoboMaster GUI 控制器 - [明文SDK-TCP模式]")
        self.geometry("600x450")

        self.robot_ip = ""
        self.robot_port = 40923 # 控制命令默认TCP端口
        self.sock = None
        self.is_connected = False
        self.heartbeat_thread = None
        self.listen_thread = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        conn_frame = ttk.LabelFrame(main_frame, text="连接控制", padding="10")
        conn_frame.pack(fill=tk.X, pady=5)

        ttk.Label(conn_frame, text="机器人IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.ip_entry.insert(0, "192.168.13.11")

        self.connect_btn = ttk.Button(conn_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)
        conn_frame.columnconfigure(1, weight=1)

        control_frame = ttk.LabelFrame(main_frame, text="机器人控制", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        self.control_btn = ttk.Button(control_frame, text="1. 开启控制 (获取控制权)", command=lambda: self.send_command("robot mode chassis_lead;"))
        self.control_btn.pack(pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="状态日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=5)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        chassis_frame = ttk.LabelFrame(main_frame, text="2. 底盘控制", padding="10")
        chassis_frame.pack(fill=tk.X, pady=5)

        ttk.Button(chassis_frame, text="↑\n前进", command=lambda: self.send_command("chassis speed x 0.5 y 0 z 0;")).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(chassis_frame, text="↓\n后退", command=lambda: self.send_command("chassis speed x -0.5 y 0 z 0;")).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(chassis_frame, text="←\n左移", command=lambda: self.send_command("chassis speed x 0 y -0.5 z 0;")).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(chassis_frame, text="→\n右移", command=lambda: self.send_command("chassis speed x 0 y 0.5 z 0;")).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(chassis_frame, text="↺\n左旋", command=lambda: self.send_command("chassis speed x 0 y 0 z -90;")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(chassis_frame, text="↻\n右旋", command=lambda: self.send_command("chassis speed x 0 y 0 z 90;")).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(chassis_frame, text="■\n停止", command=lambda: self.send_command("chassis speed x 0 y 0 z 0;")).grid(row=1, column=1, padx=5, pady=5)
        for i in range(3): chassis_frame.columnconfigure(i, weight=1)

        gimbal_frame = ttk.LabelFrame(main_frame, text="3. 云台控制", padding="10")
        gimbal_frame.pack(fill=tk.X, pady=5)
        ttk.Button(gimbal_frame, text="↑\n向上", command=lambda: self.send_command("gimbal move p 10 y 0;")).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(gimbal_frame, text="↓\n向下", command=lambda: self.send_command("gimbal move p -10 y 0;")).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(gimbal_frame, text="←\n向左", command=lambda: self.send_command("gimbal move p 0 y -15;")).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(gimbal_frame, text="→\n向右", command=lambda: self.send_command("gimbal move p 0 y 15;")).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(gimbal_frame, text="回中", command=lambda: self.send_command("gimbal recenter;")).grid(row=0, column=2, padx=5, pady=5)
        for i in range(3): gimbal_frame.columnconfigure(i, weight=1)

        self.set_controls_state('disabled')


    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def set_controls_state(self, state):
        for child in self.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, ttk.Button) and widget != self.connect_btn:
                        widget.config(state=state)
                if child.cget("text") == "机器人控制":
                    for widget in child.winfo_children():
                        widget.config(state=state)

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_robot()
        else:
            threading.Thread(target=self.connect_robot, daemon=True).start()

    def connect_robot(self):
        self.connect_btn.config(state='disabled')
        self.robot_ip = self.ip_entry.get()
        if not self.robot_ip:
            self.log("错误：请输入机器人IP地址。")
            self.connect_btn.config(state='normal')
            return

        try:
            address = (self.robot_ip, self.robot_port)
            self.log(f"正在创建TCP套接字，目标: {self.robot_ip}:{self.robot_port}")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            self.log("正在连接到机器人...")
            self.sock.connect(address)
            self.log("TCP连接成功！")

            # --- 关键修正：必须在发送任何指令之前，先设置连接状态 ---
            self.is_connected = True

            self.listen_thread = threading.Thread(target=self.listen_for_responses, daemon=True)
            self.listen_thread.start()

            self.log("发送 'command;' 进入SDK模式...")
            self.send_command("command;")
            time.sleep(1) # 等待机器人响应

            self.log("已进入SDK明文控制模式。")
            self.log("注意：此模式下机器人若15秒内无指令会自动退出SDK模式。")

            self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
            self.heartbeat_thread.start()

            self.connect_btn.config(text="断开")
            self.set_controls_state('normal')

        except Exception as e:
            self.log(f"连接失败: {e}")
            self.is_connected = False
            if self.sock:
                self.sock.close()
                self.sock = None
        finally:
            self.connect_btn.config(state='normal')

    def disconnect_robot(self):
        self.log("正在断开连接...")
        if self.is_connected:
            self.send_command("robot mode free;")
            time.sleep(0.2)
            self.send_command("quit;")
            self.is_connected = False
        if self.sock:
            self.sock.close()
            self.sock = None
        self.log("连接已断开。")
        self.connect_btn.config(text="连接")
        self.set_controls_state('disabled')

    def send_command(self, cmd_str):
        if self.is_connected and self.sock:
            try:
                self.log(f"发送: {cmd_str}")
                msg_with_end = cmd_str + ';' if not cmd_str.endswith(';') else cmd_str
                self.sock.send(msg_with_end.encode('utf-8'))
            except Exception as e:
                self.log(f"指令发送失败: {e}")
                self.disconnect_robot()
        else:
            self.log("错误：未连接，无法发送指令。")

    def listen_for_responses(self):
        """ 在独立线程中监听机器人返回的消息 """
        while self.is_connected:
            try:
                buf = self.sock.recv(1024)
                if buf:
                    self.log(f"收到响应: {buf.decode('utf-8', errors='ignore')}")
                else:
                    # 连接已断开
                    self.log("机器人断开了连接。")
                    self.disconnect_robot()
                    break
            except Exception:
                # 忽略超时等错误，或在断开连接时发生
                break

    def send_heartbeat(self):
        while self.is_connected:
            time.sleep(10)
            self.send_command("robot mode free;")

    def on_closing(self):
        self.disconnect_robot()
        self.destroy()

if __name__ == '__main__':
    app = RoboMasterController()
    app.mainloop()
