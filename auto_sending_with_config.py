#!/usr/bin/env python3
# auto_sending_with_config.py
# 运行前确保: pip install requests

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading, time, random, requests, traceback, json, datetime, os, re, math

CONFIG_PATH = "config.json"
LOGFILE = "auto_send_log.txt"

def log_to_file(s):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {s}\n")

class DanmakuSender:
    def __init__(self, gui_log):
        self.session = requests.Session()
        self.cookie_dict = {}
        self.bili_jct = None
        self.sessdata = None
        self.running = threading.Event()
        self.thread = None
        self.gui_log = gui_log

    # ---------------- cookie 管理 ----------------
    def parse_cookie_string(self, cookie_str):
        d = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
        return d

    def update_cookie(self, cookie_str):
        d = self.parse_cookie_string(cookie_str)
        self.cookie_dict = d
        self.bili_jct = d.get("bili_jct") or d.get("bili_jct ")
        self.sessdata = d.get("SESSDATA") or d.get("SESSDATA ")
        # apply to session
        self.session.cookies.clear()
        for k, v in d.items():
            self.session.cookies.set(k, v)
        return d

    def clear_cookie(self):
        self.cookie_dict = {}
        self.bili_jct = None
        self.sessdata = None
        self.session.cookies.clear()
        self._log("已清除内存中的 Cookie（不会影响 config.json）")

    # -------------- 验证登录 --------------
    def validate_cookie_login(self, timeout=8):
        url = "https://api.bilibili.com/x/web-interface/nav"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.bilibili.com"
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            return False, f"网络异常: {e}", None

        text = resp.text
        try:
            j = resp.json()
        except Exception:
            return False, f"非 JSON 响应，HTTP {resp.status_code}", text[:2000]

        code = j.get("code")
        data = j.get("data") or {}
        is_login = data.get("isLogin") or data.get("is_login") or False
        uname = data.get("uname") or data.get("username") or None

        if code == 0 and is_login:
            return True, f"已登录（用户：{uname}）", j
        if code == 0 and uname:
            return True, f"已登录（用户：{uname}）", j
        return False, f"未登录或 cookie 无效，返回 code={code}, message={j.get('message')}", j

    # -------------- 日志 --------------
    def _log(self, s, to_file=True):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {s}"
        try:
            self.gui_log.insert(tk.END, line + "\n")
            self.gui_log.see(tk.END)
        except Exception:
            pass
        if to_file:
            try:
                log_to_file(line)
            except Exception:
                pass

    # -------------- 发送弹幕 --------------
    def send_single(self, roomid, message_text, timeout=10):
        url = "https://api.live.bilibili.com/msg/send"
        referer = f"https://live.bilibili.com/{roomid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Origin": "https://live.bilibili.com",
            "Referer": referer,
        }

        if not self.bili_jct:
            return {"ok": False, "error": "缺少 bili_jct (csrf)，请在 Cookie 中包含 bili_jct"}

        data = {
            "color": "16777215",
            "fontsize": "25",
            "mode": "1",
            "msg": message_text,
            "rnd": str(int(time.time())),
            "roomid": str(roomid),
            "bubble": "0",
            "csrf_token": self.bili_jct,
            "csrf": self.bili_jct,
        }

        try:
            resp = self.session.post(url, headers=headers, data=data, timeout=timeout)
        except requests.RequestException as e:
            self._log(f"网络异常: {e}")
            return {"ok": False, "error": f"网络异常: {e}"}

        status = resp.status_code
        try:
            j = resp.json()
        except Exception:
            text = resp.text
            self._log(f"HTTP {status} 非 JSON 响应，前 1000 字: {text[:1000]}")
            return {"ok": False, "http_status": status, "raw": text}

        code = j.get("code")
        msg = j.get("message") or j.get("msg") or ""
        self._log(f"HTTP {status} 返回 code={code} message={msg} json={json.dumps(j, ensure_ascii=False)[:1000]}")
        if status == 200 and code == 0:
            return {"ok": True, "resp": j}
        else:
            return {"ok": False, "http_status": status, "code": code, "message": msg, "resp": j}

    # -------------- 自动发送线程 --------------
    def start_auto(self, roomid, messages, interval=2.0, randomize=False):
        if not messages:
            self._log("错误：弹幕列表为空，停止。")
            return
        if self.running.is_set():
            self._log("已经在运行中。")
            return
        self.running.set()
        self.thread = threading.Thread(target=self._auto_loop, args=(roomid, messages, interval, randomize), daemon=True)
        self.thread.start()
        self._log("已启动自动发送线程。")

    def stop_auto(self):
        if self.running.is_set():
            self.running.clear()
            self._log("停止信号已发送，等待线程退出...")
            if self.thread:
                self.thread.join(timeout=5)
            self._log("已停止自动发送。")
        else:
            self._log("当前没有运行中的自动发送。")

    def _auto_loop(self, roomid, messages, interval, randomize):
        counter = 0
        while self.running.is_set():
            try:
                counter += 1
                msg = random.choice(messages) if randomize else messages[(counter-1) % len(messages)]
                res = self.send_single(roomid, msg)
                if res.get("ok"):
                    self._log(f"第{counter}条弹幕发送成功: {msg}")
                else:
                    code = res.get("code")
                    http_status = res.get("http_status")
                    err = res.get("error") or res.get("message") or res.get("raw") or res.get("resp")
                    self._log(f"第{counter}条弹幕发送失败: http_status={http_status} code={code} err={err}")
                    if http_status in (401, 403, 412, 429):
                        self._log(f"检测到 HTTP {http_status}，自动停止以避免风控（请检查 cookie/csrf/referer）。")
                        self.running.clear()
                        break
                sleep_time = max(0.1, float(interval)) if interval else 2.0
                time.sleep(sleep_time + random.uniform(0, 0.5))
            except Exception as e:
                self._log("自动线程异常: " + str(e))
                self._log(traceback.format_exc())
                self.running.clear()
                break

# ----------------- GUI -----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("弹幕自动发送（含 Config 保存/加载 & Cookie 验证）")
        root.geometry("940x800")

        # 输入区
        frame = tk.Frame(root)
        frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(frame, text="房间ID:").grid(row=0, column=0, sticky=tk.W)
        self.room_entry = tk.Entry(frame, width=12)
        self.room_entry.grid(row=0, column=1, sticky=tk.W)

        tk.Label(frame, text="间隔(秒):").grid(row=0, column=2, sticky=tk.W, padx=(8,0))
        self.interval_entry = tk.Entry(frame, width=8)
        self.interval_entry.insert(0, "2.0")
        self.interval_entry.grid(row=0, column=3, sticky=tk.W)

        self.random_var = tk.IntVar(value=0)
        tk.Checkbutton(frame, text="随机从列表选取弹幕", variable=self.random_var).grid(row=0, column=4, sticky=tk.W, padx=(12,0))

        # Cookie 粘贴
        tk.Label(root, text="Cookie（完整复制浏览器中的 cookie 字符串，例如: SESSDATA=xxx; bili_jct=yyy; ...）:").pack(anchor=tk.W, padx=8)
        self.cookie_text = scrolledtext.ScrolledText(root, height=4)
        self.cookie_text.pack(fill=tk.X, padx=8, pady=(0,8))

        # 弹幕列表
        tk.Label(root, text="弹幕（每行一条）:").pack(anchor=tk.W, padx=8)
        self.msg_text = scrolledtext.ScrolledText(root, height=8)
        self.msg_text.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0,8))

        # 新增：从文件读取选项
        file_frame = tk.Frame(root)
        file_frame.pack(fill=tk.X, padx=8, pady=(0,6))
        self.use_file_var = tk.IntVar(value=0)
        tk.Checkbutton(file_frame, text="从文件读取并按分割长度切分(忽略空格/换行)", variable=self.use_file_var).pack(side=tk.LEFT)

        tk.Label(file_frame, text="分割长度(字符数):").pack(side=tk.LEFT, padx=(8,0))
        self.chunk_entry = tk.Entry(file_frame, width=6)
        self.chunk_entry.insert(0, "20")
        self.chunk_entry.pack(side=tk.LEFT, padx=(0,6))

        self.half_count_var = tk.IntVar(value=0)
        tk.Checkbutton(file_frame, text="英文/数字算0.5", variable=self.half_count_var).pack(side=tk.LEFT, padx=(0,8))

        tk.Label(file_frame, text="文件名:").pack(side=tk.LEFT)
        self.file_entry = tk.Entry(file_frame, width=36)
        self.file_entry.insert(0, "message.txt")
        self.file_entry.pack(side=tk.LEFT, padx=4)
        tk.Button(file_frame, text="加载并预览文件", command=self.load_and_preview_file).pack(side=tk.LEFT, padx=6)

        # 按钮区域
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill=tk.X, padx=8, pady=4)

        self.validate_btn = tk.Button(btn_frame, text="验证 Cookie", command=self.validate_cookie)
        self.validate_btn.pack(side=tk.LEFT)

        self.test_send_btn = tk.Button(btn_frame, text="测试发送 1 条", command=self.test_send_once)
        self.test_send_btn.pack(side=tk.LEFT, padx=6)

        self.start_btn = tk.Button(btn_frame, text="开始自动发送", command=self.start_auto)
        self.start_btn.pack(side=tk.LEFT, padx=6)
        self.stop_btn = tk.Button(btn_frame, text="停止自动发送", command=self.stop_auto)
        self.stop_btn.pack(side=tk.LEFT, padx=6)

        # config 保存/加载/删除
        self.save_cfg_btn = tk.Button(btn_frame, text="保存配置", command=self.save_config)
        self.save_cfg_btn.pack(side=tk.LEFT, padx=6)
        self.load_cfg_btn = tk.Button(btn_frame, text="加载配置", command=self.load_config)
        self.load_cfg_btn.pack(side=tk.LEFT, padx=6)
        self.del_cfg_btn = tk.Button(btn_frame, text="删除保存配置", command=self.delete_config)
        self.del_cfg_btn.pack(side=tk.LEFT, padx=6)

        # 清除 cookie（仅清除内存 / GUI，不会删除 config.json 除非保存）
        self.clear_cookie_btn = tk.Button(btn_frame, text="清除内存 Cookie", command=self.clear_cookie)
        self.clear_cookie_btn.pack(side=tk.LEFT, padx=6)

        self.clear_log_btn = tk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.pack(side=tk.RIGHT)

        # 日志区
        tk.Label(root, text="日志:").pack(anchor=tk.W, padx=8)
        self.log = scrolledtext.ScrolledText(root, height=18)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        self.sender = DanmakuSender(self.log)

        # 尝试自动加载 config（但不自动验证）
        try:
            if os.path.exists(CONFIG_PATH):
                self.load_config(auto_loaded=True)
        except Exception:
            pass

    # ---------------- 文件处理逻辑 ----------------
    def is_ascii_alnum(self, ch):
        """判断字符是否为 ASCII 字母或数字"""
        # ord范围检查：0-127 and isalnum
        return ord(ch) < 128 and ch.isalnum()

    def load_messages_from_file(self, filename, chunk_size=20, half_count=False):
        """
        读取 filename（utf-8），移除所有空白(包含空格/换行/制表符)，
        然后按 chunk_size 分割并返回字符串列表。
        如果 half_count=True，则 ASCII 字母/数字计 0.5，其他字符计 1。
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"{filename} 不存在")
        with open(filename, "r", encoding="utf-8") as f:
            raw = f.read()
        # 去除所有空白字符（空格、换行、制表符等）
        cleaned = re.sub(r"\s+", "", raw)
        if not cleaned:
            return []

        # 防坏输入
        try:
            chunk_size_val = int(chunk_size)
            if chunk_size_val < 1:
                chunk_size_val = 20
        except Exception:
            chunk_size_val = 20

        if not half_count:
            # 简单切割
            chunks = [cleaned[i:i+chunk_size_val] for i in range(0, len(cleaned), chunk_size_val)]
            return chunks

        # half_count=True 的复杂计数逻辑
        chunks = []
        current = []
        acc = 0.0
        for ch in cleaned:
            w = 0.5 if self.is_ascii_alnum(ch) else 1.0
            # If adding this char exceeds chunk_size, then flush current chunk first
            if acc + w > chunk_size_val and current:
                chunks.append("".join(current))
                current = []
                acc = 0.0
            current.append(ch)
            acc += w
        if current:
            chunks.append("".join(current))
        return chunks

    def load_and_preview_file(self):
        filename = self.file_entry.get().strip() or "message.txt"
        try:
            chunk_size = int(self.chunk_entry.get().strip() or 20)
            half_count = bool(self.half_count_var.get())
        except Exception:
            chunk_size = 20
            half_count = False
        try:
            chunks = self.load_messages_from_file(filename, chunk_size=chunk_size, half_count=half_count)
        except FileNotFoundError:
            messagebox.showwarning("文件未找到", f"{filename} 不存在，请检查路径。")
            return
        except Exception as e:
            messagebox.showerror("读取失败", f"读取文件失败: {e}")
            return
        if not chunks:
            messagebox.showwarning("文件为空", "文件读取后为空（或全部为空白）。")
            return
        # 把分割结果预览到弹幕编辑区（每行一条）
        self.msg_text.delete("1.0", tk.END)
        for c in chunks:
            self.msg_text.insert(tk.END, c + "\n")
        self.sender._log(f"已从 {filename} 加载并预览 {len(chunks)} 条消息（每条 {chunk_size} 计数单位，英文/数字算0.5={half_count}）")
        messagebox.showinfo("预览已生成", f"已生成 {len(chunks)} 条消息并显示在弹幕编辑区。")

    # ---------------- UI 操作 ----------------
    def validate_cookie(self):
        cookie_str = self.cookie_text.get("1.0", tk.END).strip()
        if not cookie_str:
            messagebox.showwarning("提示", "请粘贴 Cookie 字符串后再验证。")
            return
        d = self.sender.update_cookie(cookie_str)
        has_bj = bool(self.sender.bili_jct)
        has_sess = bool(self.sender.sessdata)
        self.sender._log(f"已解析 Cookie：包含 bili_jct={has_bj} SESSDATA={has_sess} （请确认）")
        ok, msg, raw = self.sender.validate_cookie_login()
        if ok:
            messagebox.showinfo("验证通过", f"Cookie 验证成功：{msg}")
            self.sender._log(f"验证通过: {msg}")
        else:
            messagebox.showerror("验证失败", f"Cookie 验证失败：{msg}\n详细返回已写入日志。")
            self.sender._log(f"验证失败: {msg} 原始: {json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw)[:1000]}")

    def test_send_once(self):
        roomid = self.room_entry.get().strip()
        if not roomid:
            messagebox.showwarning("提示", "请输入房间ID。")
            return

        # 若选择使用文件模式，优先尝试从文件获取第一条
        if self.use_file_var.get():
            filename = self.file_entry.get().strip() or "message.txt"
            try:
                chunk_size = int(self.chunk_entry.get().strip() or 20)
            except Exception:
                chunk_size = 20
            half_count = bool(self.half_count_var.get())
            try:
                chunks = self.load_messages_from_file(filename, chunk_size=chunk_size, half_count=half_count)
            except FileNotFoundError:
                messagebox.showwarning("文件未找到", f"{filename} 不存在，请检查路径。")
                return
            except Exception as e:
                messagebox.showerror("读取失败", f"读取文件失败: {e}")
                return
            if not chunks:
                messagebox.showwarning("文件为空", "文件读取后为空（或全部为空白）。")
                return
            first_msg = chunks[0]
            messages = [first_msg]
        else:
            messages = self.msg_text.get("1.0", tk.END).strip().splitlines()

        if not messages:
            messagebox.showwarning("提示", "请在弹幕列表中至少填写一条弹幕或启用文件模式并确保文件非空。")
            return

        cookie_str = self.cookie_text.get("1.0", tk.END).strip()
        if cookie_str:
            self.sender.update_cookie(cookie_str)

        def job():
            self.sender._log("单次发送开始...")
            res = self.sender.send_single(roomid, messages[0])
            if res.get("ok"):
                self.sender._log("单次发送成功。")
                messagebox.showinfo("结果", "单次发送成功（响应 code=0）。")
            else:
                self.sender._log("单次发送失败: " + str(res))
                messagebox.showerror("结果", f"单次发送失败，请查看日志（或检查 cookie / bili_jct / referer）。\n详情见日志。")
        threading.Thread(target=job, daemon=True).start()

    def start_auto(self):
        roomid = self.room_entry.get().strip()
        if not roomid:
            messagebox.showwarning("提示", "请输入房间ID。")
            return

        # 决定消息来源：文件模式优先
        if self.use_file_var.get():
            filename = self.file_entry.get().strip() or "message.txt"
            try:
                chunk_size = int(self.chunk_entry.get().strip() or 20)
            except Exception:
                chunk_size = 20
            half_count = bool(self.half_count_var.get())
            try:
                messages = self.load_messages_from_file(filename, chunk_size=chunk_size, half_count=half_count)
            except FileNotFoundError:
                messagebox.showwarning("文件未找到", f"{filename} 不存在，请检查路径。")
                return
            except Exception as e:
                messagebox.showerror("读取失败", f"读取文件失败: {e}")
                return
            if not messages:
                messagebox.showwarning("文件为空", "文件读取后为空（或全部为空白）。")
                return
            self.sender._log(f"从文件 {filename} 加载到 {len(messages)} 条消息（分割长度={chunk_size}, 英文/数字半字={half_count}）并开始发送。")
        else:
            messages = [line.strip() for line in self.msg_text.get("1.0", tk.END).splitlines() if line.strip()]
            if not messages:
                messagebox.showwarning("提示", "弹幕列表为空，请至少填写一条弹幕或启用文件模式并确保文件非空。")
                return

        cookie_str = self.cookie_text.get("1.0", tk.END).strip()
        if cookie_str:
            self.sender.update_cookie(cookie_str)
        ok, msg, raw = self.sender.validate_cookie_login()
        if not ok:
            if not messagebox.askyesno("cookie 未通过验证", f"Cookie 验证未通过：{msg}\n仍要继续发送吗？(不建议继续)"):
                return
        try:
            interval = float(self.interval_entry.get().strip())
        except Exception:
            interval = 2.0
        randomize = bool(self.random_var.get())
        self.sender.start_auto(roomid, messages, interval=interval, randomize=randomize)

    def stop_auto(self):
        self.sender.stop_auto()

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def clear_cookie(self):
        self.cookie_text.delete("1.0", tk.END)
        self.sender.clear_cookie()
        messagebox.showinfo("已清除", "内存和界面中的 Cookie 已清除（config.json 不受影响）。")

    # ---------------- Config 保存/加载 ----------------
    def save_config(self):
        try:
            chunk_size = int(self.chunk_entry.get().strip() or 20)
        except Exception:
            chunk_size = 20
        cfg = {
            "roomid": self.room_entry.get().strip(),
            "interval": float(self.interval_entry.get().strip() or 2.0),
            "randomize": bool(self.random_var.get()),
            "messages": [line.strip() for line in self.msg_text.get("1.0", tk.END).splitlines() if line.strip()],
            "cookie": self.cookie_text.get("1.0", tk.END).strip(),
            "use_file": bool(self.use_file_var.get()),
            "file": self.file_entry.get().strip() or "message.txt",
            "chunk_size": int(chunk_size),
            "half_count": bool(self.half_count_var.get())
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self.sender._log(f"配置已保存到 {CONFIG_PATH}")
            messagebox.showinfo("保存成功", f"配置已保存到 {CONFIG_PATH}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            self.sender._log("保存配置失败: " + str(e))

    def load_config(self, auto_loaded=False):
        if not os.path.exists(CONFIG_PATH):
            if not auto_loaded:
                messagebox.showwarning("未找到配置", f"{CONFIG_PATH} 不存在")
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.room_entry.delete(0, tk.END); self.room_entry.insert(0, cfg.get("roomid", ""))
            self.interval_entry.delete(0, tk.END); self.interval_entry.insert(0, str(cfg.get("interval", 2.0)))
            self.random_var.set(1 if cfg.get("randomize", False) else 0)
            self.msg_text.delete("1.0", tk.END)
            self.msg_text.insert(tk.END, "\n".join(cfg.get("messages", [])))
            cookie_value = cfg.get("cookie", "")
            self.cookie_text.delete("1.0", tk.END)
            self.cookie_text.insert(tk.END, cookie_value)
            # 文件/模式设置
            use_file = bool(cfg.get("use_file", False))
            self.use_file_var.set(1 if use_file else 0)
            file_name = cfg.get("file", "message.txt")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_name)
            chunk_size = int(cfg.get("chunk_size", 20))
            self.chunk_entry.delete(0, tk.END)
            self.chunk_entry.insert(0, str(chunk_size))
            half_flag = bool(cfg.get("half_count", False))
            self.half_count_var.set(1 if half_flag else 0)
            # 同步到 session（但不自动验证）
            if cookie_value:
                self.sender.update_cookie(cookie_value)
            self.sender._log(f"已从 {CONFIG_PATH} 加载配置（auto_loaded={auto_loaded}）。请点击 验证 Cookie 以确认登录状态。")
            if not auto_loaded:
                messagebox.showinfo("加载成功", f"配置已从 {CONFIG_PATH} 加载（请点击 验证 Cookie 按钮来验证登录）。")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
            self.sender._log("加载配置失败: " + str(e))

    def delete_config(self):
        if not os.path.exists(CONFIG_PATH):
            messagebox.showinfo("删除配置", "当前没有保存的配置文件。")
            return
        if not messagebox.askyesno("确认删除", f"确定要删除 {CONFIG_PATH} 吗？"):
            return
        try:
            os.remove(CONFIG_PATH)
            self.sender._log(f"已删除 {CONFIG_PATH}")
            messagebox.showinfo("删除成功", f"{CONFIG_PATH} 已删除。")
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
            self.sender._log("删除配置失败: " + str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
