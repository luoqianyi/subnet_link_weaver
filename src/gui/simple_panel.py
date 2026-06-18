"""新手模式面板 - 傻瓜式自动配置"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGroupBox, QMessageBox,
    QProgressBar, QTextEdit, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QFont, QColor

from ..core.network import NetworkManager, NetworkError, NetworkAdapter
from ..core.firewall import FirewallManager
from ..core.ping import PingTester
from ..utils.config import ConfigManager, SavedConfig


class LoadAdaptersThread(QThread):
    """加载网络适配器线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, network_manager: NetworkManager):
        super().__init__()
        self.network_manager = network_manager

    def run(self):
        try:
            adapters = self.network_manager.get_adapters()
            self.finished.emit(adapters)
        except Exception as e:
            self.error.emit(str(e))


class AutoConfigThread(QThread):
    """自动配置线程 - 双 IP 挂载方案"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(
        self,
        network_manager: NetworkManager,
        firewall_manager: FirewallManager,
        additional_ips: list,
        auto_disable_firewall: bool = True
    ):
        super().__init__()
        self.network_manager = network_manager
        self.firewall_manager = firewall_manager
        self.additional_ips = additional_ips
        self.auto_disable_firewall = auto_disable_firewall

    def run(self):
        try:
            # ============================================
            # 第一步：检测网络适配器，获取当前热点信息
            # ============================================
            self.progress.emit(10, "正在检测网络适配器...")
            adapters = self.network_manager.get_adapters()

            # 找到已连接的适配器（通常是 Wi-Fi）
            connected_adapter = None
            for adapter in adapters:
                if adapter.status.value == "connected":
                    connected_adapter = adapter
                    break

            if not connected_adapter:
                self.error.emit("未找到已连接的网络适配器\n请先连接手机热点或网络")
                return

            self.progress.emit(15, f"找到适配器: {connected_adapter.name}")

            # 记录当前热点信息（从 DHCP 获取的）
            current_ip = connected_adapter.ip_address
            current_mask = connected_adapter.subnet_mask
            current_gateway = connected_adapter.default_gateway
            current_dns = connected_adapter.dns_servers[0] if connected_adapter.dns_servers else "114.114.114.114"

            if not current_ip:
                self.error.emit(f"适配器 {connected_adapter.name} 没有 IP 地址\n请先连接网络")
                return

            self.progress.emit(20, f"当前热点 IP: {current_ip}")
            self.progress.emit(20, f"当前网关: {current_gateway or '无'}")

            # ============================================
            # 第二步：将当前热点 IP 从 DHCP 固定为静态
            # ============================================
            self.progress.emit(30, "正在将当前热点 IP 固定为静态...")

            # 检查是否已经是静态 IP
            if connected_adapter.is_dhcp:
                # 需要从 DHCP 转为静态
                try:
                    self.network_manager.set_static_ip(
                        connected_adapter.name,
                        current_ip,
                        current_mask or "255.255.255.0",
                        current_gateway,
                        [current_dns] if current_dns else ["114.114.114.114"]
                    )
                    self.progress.emit(35, "热点 IP 已固定为静态")
                except NetworkError as e:
                    self.progress.emit(35, f"固定静态 IP 失败: {e}")
                    # 继续尝试添加额外 IP
            else:
                self.progress.emit(35, "热点 IP 已经是静态，跳过此步骤")

            # ============================================
            # 第三步：挂载所有额外的局域网 IP
            # ============================================
            total_ips = len(self.additional_ips)
            for i, ip_info in enumerate(self.additional_ips):
                ip_address = ip_info["ip"]
                subnet_mask = ip_info.get("mask", "255.255.255.0")

                progress = 40 + int((i / total_ips) * 20)
                self.progress.emit(progress, f"正在挂载 IP ({i+1}/{total_ips}): {ip_address}...")

                try:
                    self.network_manager.add_secondary_ip(
                        connected_adapter.name,
                        ip_address,
                        subnet_mask
                    )
                    self.progress.emit(progress + 5, f"IP {ip_address} 挂载成功")
                except NetworkError as e:
                    if "已存在" in str(e) or "already exists" in str(e).lower():
                        self.progress.emit(progress + 5, f"IP {ip_address} 已存在，跳过")
                    else:
                        self.error.emit(f"挂载 IP {ip_address} 失败: {e}")
                        return

            # ============================================
            # 第四步：关闭防火墙（90% 失败都是因为这个）
            # ============================================
            if self.auto_disable_firewall:
                self.progress.emit(65, "正在关闭 Windows 防火墙...")
                try:
                    self.firewall_manager.disable()
                    self.progress.emit(75, "防火墙已关闭")
                except Exception as e:
                    self.progress.emit(75, f"关闭防火墙失败: {e}")
                    self.progress.emit(75, "请手动关闭防火墙后再测试")
            else:
                self.progress.emit(75, "跳过防火墙配置（建议手动关闭）")

            # ============================================
            # 第五步：联调测试
            # ============================================
            self.progress.emit(80, "正在测试连通性...")
            from ..core.ping import PingTester
            ping_tester = PingTester()

            # 测试第一个额外 IP 的网关
            if self.additional_ips:
                first_ip = self.additional_ips[0]["ip"]
                parts = first_ip.split('.')
                new_subnet = '.'.join(parts[:3])
                test_ip = f"{new_subnet}.1"
                result = ping_tester.ping(test_ip, count=2)
            else:
                result = None

            # 构建结果消息
            ips_text = "\n".join([ip["ip"] for ip in self.additional_ips])
            result_msg = (
                f"双 IP 挂载配置完成！\n\n"
                f"【当前网络状态】\n"
                f"适配器: {connected_adapter.name}\n"
                f"原主 IP: {current_ip} (用于上网)\n\n"
                f"【已添加的额外 IP】\n{ips_text}\n"
                f"(用于双机通信)\n\n"
                f"【配置说明】\n"
                f"电脑现在同时拥有多个 IP：\n"
                f"1. 原主 IP ({current_ip}) - 保持上网功能\n"
                f"2. 额外 IP - 用于与对方电脑通信\n\n"
            )

            if result and result.success:
                result_msg += f"连通性测试: 通过 (延迟 {result.average_time}ms)"
            else:
                result_msg += (
                    f"连通性测试: 未通过\n\n"
                    f"这是正常的！因为对方电脑还没有配置。\n"
                    f"请在另一台电脑上也运行此程序，配置对应的 IP 地址。\n"
                    f"例如: 对方配置 192.168.88.197"
                )

            self.progress.emit(100, "配置完成！")
            self.finished.emit(True, result_msg)

        except Exception as e:
            self.error.emit(f"配置过程出错: {e}")


class SimplePanel(QWidget):
    """新手模式面板"""

    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str, str)

    def __init__(
        self,
        network_manager: NetworkManager,
        firewall_manager: FirewallManager,
        ping_tester: PingTester,
        config_manager: ConfigManager
    ):
        super().__init__()

        self.network_manager = network_manager
        self.firewall_manager = firewall_manager
        self.ping_tester = ping_tester
        self.config_manager = config_manager

        # 当前检测到的适配器
        self.adapters = []
        self.connected_adapter = None

        # 添加的额外 IP 列表
        self.additional_ips = []

        # 初始化 UI
        self._init_ui()

        # 不在这里加载适配器，等待主窗口传递预加载数据

    def _init_ui(self):
        """初始化用户界面"""
        # 使用滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title = QLabel("双 IP 挂载 - 一键配置")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ============================================
        # 网络适配器信息区
        # ============================================
        adapter_group = QGroupBox("当前网络适配器")
        adapter_layout = QVBoxLayout(adapter_group)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新适配器")
        self.refresh_btn.clicked.connect(self._load_adapters)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        adapter_layout.addLayout(refresh_layout)

        # 适配器信息显示
        self.adapter_info_label = QLabel("正在检测网络适配器...")
        self.adapter_info_label.setStyleSheet("background-color: #f8f9fa; padding: 8px; border-radius: 4px;")
        self.adapter_info_label.setWordWrap(True)
        adapter_layout.addWidget(self.adapter_info_label)

        # 适配器 IP 列表
        self.ip_table = QTableWidget()
        self.ip_table.setColumnCount(3)
        self.ip_table.setHorizontalHeaderLabels(["IP 地址", "子网掩码", "类型"])
        self.ip_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ip_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ip_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ip_table.setMaximumHeight(150)
        adapter_layout.addWidget(self.ip_table)

        layout.addWidget(adapter_group)

        # ============================================
        # 添加额外 IP 区域
        # ============================================
        add_ip_group = QGroupBox("添加额外的局域网 IP")
        add_ip_layout = QVBoxLayout(add_ip_group)

        # IP 输入
        ip_input_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("输入想要挂载的 IP，例如: 192.168.88.26")
        self.ip_input.setFont(QFont("Consolas", 12))
        self.ip_input.setMinimumHeight(35)
        ip_input_layout.addWidget(self.ip_input)

        self.add_ip_btn = QPushButton("添加")
        self.add_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.add_ip_btn.clicked.connect(self._add_ip)
        ip_input_layout.addWidget(self.add_ip_btn)
        add_ip_layout.addLayout(ip_input_layout)

        # 快速选择（从历史记录加载）
        self.quick_frame = QFrame()
        self.quick_layout = QHBoxLayout(self.quick_frame)
        self.quick_layout.setContentsMargins(0, 5, 0, 0)
        self._update_quick_buttons()
        add_ip_layout.addWidget(self.quick_frame)

        # 已添加的 IP 列表
        self.added_ip_table = QTableWidget()
        self.added_ip_table.setColumnCount(2)
        self.added_ip_table.setHorizontalHeaderLabels(["IP 地址", "操作"])
        self.added_ip_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.added_ip_table.setMaximumHeight(120)
        add_ip_layout.addWidget(self.added_ip_table)

        # IP 操作按钮
        ip_btn_layout = QHBoxLayout()
        self.remove_ip_btn = QPushButton("删除选中")
        self.remove_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 15px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.remove_ip_btn.clicked.connect(self._remove_selected_ip)
        ip_btn_layout.addWidget(self.remove_ip_btn)
        ip_btn_layout.addStretch()
        add_ip_layout.addLayout(ip_btn_layout)

        layout.addWidget(add_ip_group)

        # ============================================
        # 防火墙选项
        # ============================================
        firewall_group = QGroupBox("防火墙设置（重要！）")
        firewall_layout = QVBoxLayout(firewall_group)

        firewall_warning = QLabel(
            "90% 配置失败都是因为防火墙！\n"
            "Windows 防火墙会丢弃非原生网段（如 .88.X）的数据包，\n"
            "必须关闭防火墙才能让两台电脑通过新 IP 互相通信。"
        )
        firewall_warning.setStyleSheet("color: #e74c3c; font-size: 11px; background-color: #fadbd8; padding: 8px; border-radius: 4px;")
        firewall_warning.setWordWrap(True)
        firewall_layout.addWidget(firewall_warning)

        self.disable_firewall_cb = QPushButton("自动关闭防火墙（推荐）")
        self.disable_firewall_cb.setCheckable(True)
        self.disable_firewall_cb.setChecked(True)
        self.disable_firewall_cb.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:checked {
                background-color: #27ae60;
            }
        """)
        firewall_layout.addWidget(self.disable_firewall_cb)

        layout.addWidget(firewall_group)

        # ============================================
        # 进度和状态
        # ============================================
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(20)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪 - 正在检测网络适配器...")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # ============================================
        # 操作按钮
        # ============================================
        btn_layout = QHBoxLayout()

        self.config_btn = QPushButton("一键配置")
        self.config_btn.setMinimumHeight(45)
        self.config_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.config_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.config_btn.clicked.connect(self._start_auto_config)
        btn_layout.addWidget(self.config_btn)

        self.restore_btn = QPushButton("一键还原")
        self.restore_btn.setMinimumHeight(45)
        self.restore_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #ba4a00;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.restore_btn.clicked.connect(self._restore_network)
        btn_layout.addWidget(self.restore_btn)

        layout.addLayout(btn_layout)

        # ============================================
        # 结果显示
        # ============================================
        result_group = QGroupBox("配置结果")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setMaximumHeight(120)
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

        # 设置容器
        scroll.setWidget(container)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _load_adapters(self):
        """加载网络适配器"""
        self.status_label.setText("正在检测网络适配器...")
        self.refresh_btn.setEnabled(False)

        # 在后台线程中执行
        self.load_thread = LoadAdaptersThread(self.network_manager)
        self.load_thread.finished.connect(self._on_adapters_loaded)
        self.load_thread.error.connect(self._on_adapters_error)
        self.load_thread.start()

    def _on_adapters_loaded(self, adapters: list):
        """适配器加载完成"""
        self.adapters = adapters
        self.refresh_btn.setEnabled(True)

        # 找到已连接的适配器
        self.connected_adapter = None
        for adapter in adapters:
            if adapter.status.value == "connected":
                self.connected_adapter = adapter
                break

        # 更新适配器信息显示
        self._update_adapter_info()

        # 更新 IP 列表
        self._update_ip_table()

        # 保存当前状态（用于还原）
        self._save_current_state()

    def _on_adapters_error(self, error: str):
        """适配器加载失败"""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("检测失败")
        self.adapter_info_label.setText(f"检测失败: {error}")

    def _update_adapter_info(self):
        """更新适配器信息显示"""
        if not self.connected_adapter:
            self.adapter_info_label.setText("未找到已连接的网络适配器\n请先连接手机热点或网络")
            self.status_label.setText("未找到已连接的网络适配器")
            return

        # 显示适配器信息
        info_text = (
            f"适配器: {self.connected_adapter.name}\n"
            f"状态: {self.connected_adapter.status.value}\n"
            f"主 IP: {self.connected_adapter.ip_address or '未分配'}\n"
            f"子网掩码: {self.connected_adapter.subnet_mask or '未分配'}\n"
            f"默认网关: {self.connected_adapter.default_gateway or '未分配'}\n"
            f"DNS: {', '.join(self.connected_adapter.dns_servers) if self.connected_adapter.dns_servers else '未分配'}\n"
            f"DHCP: {'是' if self.connected_adapter.is_dhcp else '否（静态）'}"
        )
        self.adapter_info_label.setText(info_text)
        self.status_label.setText(f"已检测到适配器: {self.connected_adapter.name}")

    def _update_ip_table(self):
        """更新 IP 列表表格"""
        self.ip_table.setRowCount(0)

        if not self.connected_adapter:
            return

        # 获取所有 IP 地址
        ips = self.network_manager.get_all_ips(self.connected_adapter.name)

        self.ip_table.setRowCount(len(ips))
        for i, ip_info in enumerate(ips):
            self.ip_table.setItem(i, 0, QTableWidgetItem(ip_info.get("ip", "")))
            self.ip_table.setItem(i, 1, QTableWidgetItem(ip_info.get("mask", "")))

            # 确定类型
            ip = ip_info.get("ip", "")
            if ip == self.connected_adapter.ip_address:
                ip_type = "主 IP（上网用）"
            else:
                ip_type = "额外 IP（双机通信）"
            self.ip_table.setItem(i, 2, QTableWidgetItem(ip_type))

    def _add_ip(self):
        """添加额外的 IP"""
        ip_address = self.ip_input.text().strip()

        if not ip_address:
            QMessageBox.warning(self, "警告", "请输入 IP 地址")
            return

        if not self._validate_ip(ip_address):
            QMessageBox.warning(self, "警告", "请输入有效的 IP 地址格式\n例如: 192.168.88.26")
            return

        # 检查是否已添加
        for ip_info in self.additional_ips:
            if ip_info["ip"] == ip_address:
                QMessageBox.warning(self, "警告", "该 IP 已添加")
                return

        # 添加到列表
        self.additional_ips.append({
            "ip": ip_address,
            "mask": "255.255.255.0"
        })

        # 更新表格
        self._update_added_ip_table()

        # 保存到历史记录
        self._save_to_history(ip_address)

        # 清空输入框
        self.ip_input.clear()

        self.status_label.setText(f"已添加 IP: {ip_address}")

    def _remove_selected_ip(self):
        """删除选中的 IP"""
        selected_rows = self.added_ip_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要删除的 IP")
            return

        row = selected_rows[0].row()
        ip_address = self.additional_ips[row]["ip"]

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 IP {ip_address} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 从网卡上移除 IP
            if self.connected_adapter:
                try:
                    self.network_manager.remove_secondary_ip(
                        self.connected_adapter.name,
                        ip_address
                    )
                except Exception:
                    pass  # 忽略错误

            # 从列表中移除
            self.additional_ips.pop(row)
            self._update_added_ip_table()
            self.status_label.setText(f"已删除 IP: {ip_address}")

    def _update_added_ip_table(self):
        """更新已添加 IP 表格"""
        self.added_ip_table.setRowCount(len(self.additional_ips))

        for i, ip_info in enumerate(self.additional_ips):
            self.added_ip_table.setItem(i, 0, QTableWidgetItem(ip_info["ip"]))

            delete_btn = QPushButton("删除")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 3px 8px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            delete_btn.clicked.connect(lambda checked, idx=i: self._delete_ip(idx))
            self.added_ip_table.setCellWidget(i, 1, delete_btn)

    def _delete_ip(self, index: int):
        """删除指定索引的 IP"""
        if 0 <= index < len(self.additional_ips):
            ip_address = self.additional_ips[index]["ip"]

            # 从网卡上移除 IP
            if self.connected_adapter:
                try:
                    self.network_manager.remove_secondary_ip(
                        self.connected_adapter.name,
                        ip_address
                    )
                except Exception:
                    pass

            # 从列表中移除
            self.additional_ips.pop(index)
            self._update_added_ip_table()
            self.status_label.setText(f"已删除 IP: {ip_address}")

    def _update_quick_buttons(self):
        """更新快速选择按钮（从历史记录加载）"""
        # 清空现有按钮
        while self.quick_layout.count():
            item = self.quick_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 获取历史记录
        history = self.config_manager.load_history_ips()

        if not history:
            # 没有历史记录，显示提示
            hint_label = QLabel("（添加过的 IP 会显示在这里）")
            hint_label.setStyleSheet("color: #999; font-size: 11px;")
            self.quick_layout.addWidget(hint_label)
        else:
            quick_label = QLabel("历史记录:")
            quick_label.setStyleSheet("font-weight: bold;")
            self.quick_layout.addWidget(quick_label)

            for ip in history[:5]:  # 最多显示 5 个
                btn = QPushButton(ip)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #34495e;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #2c3e50;
                    }
                """)
                btn.clicked.connect(lambda checked, ip=ip: self.ip_input.setText(ip))
                self.quick_layout.addWidget(btn)

        self.quick_layout.addStretch()

    def _save_to_history(self, ip_address: str):
        """保存 IP 到历史记录"""
        self.config_manager.add_history_ip(ip_address)
        self._update_quick_buttons()

    def _save_current_state(self):
        """保存当前网络状态（用于还原）"""
        if not self.connected_adapter:
            return

        state = {
            "adapter_name": self.connected_adapter.name,
            "original_ip": self.connected_adapter.ip_address,
            "original_mask": self.connected_adapter.subnet_mask,
            "original_gateway": self.connected_adapter.default_gateway,
            "original_dns": self.connected_adapter.dns_servers,
            "is_dhcp": self.connected_adapter.is_dhcp,
            "additional_ips": self.additional_ips.copy()
        }
        self.config_manager.save_network_state(state)

    def _restore_network(self):
        """一键还原网络配置"""
        state = self.config_manager.load_network_state()
        if not state:
            QMessageBox.warning(self, "警告", "没有找到可还原的网络状态")
            return

        reply = QMessageBox.question(
            self,
            "确认还原",
            f"即将还原网络配置：\n\n"
            f"适配器: {state['adapter_name']}\n"
            f"还原为 DHCP: {'是' if state.get('is_dhcp', True) else '否'}\n"
            f"删除额外 IP: {', '.join([ip['ip'] for ip in state.get('additional_ips', [])])}\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._execute_restore(state)

    def _execute_restore(self, state: dict):
        """执行还原操作"""
        self.config_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)
        self.restore_btn.setText("还原中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.result_text.clear()
        self.result_text.append("开始还原网络配置...\n")

        try:
            adapter_name = state["adapter_name"]

            # 步骤 1: 删除额外 IP
            self.progress_bar.setValue(20)
            self.status_label.setText("正在删除额外 IP...")
            for ip_info in state.get("additional_ips", []):
                try:
                    self.network_manager.remove_secondary_ip(adapter_name, ip_info["ip"])
                    self.result_text.append(f"已删除额外 IP: {ip_info['ip']}\n")
                except Exception as e:
                    self.result_text.append(f"删除 IP {ip_info['ip']} 失败: {e}\n")

            # 步骤 2: 还原为 DHCP
            self.progress_bar.setValue(50)
            self.status_label.setText("正在还原为 DHCP...")
            if state.get("is_dhcp", True):
                try:
                    self.network_manager.set_dhcp(adapter_name)
                    self.result_text.append("已还原为 DHCP 自动获取 IP\n")
                except Exception as e:
                    self.result_text.append(f"还原 DHCP 失败: {e}\n")

            # 步骤 3: 重新加载适配器
            self.progress_bar.setValue(80)
            self.status_label.setText("正在重新检测网络...")
            self._load_adapters()

            # 完成
            self.progress_bar.setValue(100)
            self.result_text.append("\n" + "=" * 40 + "\n")
            self.result_text.append("网络还原完成！\n")
            self.result_text.append("电脑已恢复到配置前的网络状态。\n")

            self.status_label.setText("还原完成")
            self.status_message.emit("网络还原完成")

        except Exception as e:
            self.result_text.append(f"\n还原失败: {e}")
            self.status_label.setText("还原失败")
            self.error_message.emit("还原失败", str(e))

        finally:
            self.config_btn.setEnabled(True)
            self.restore_btn.setEnabled(True)
            self.restore_btn.setText("一键还原")
            self.progress_bar.setVisible(False)

    def _start_auto_config(self):
        """开始自动配置"""
        if not self.connected_adapter:
            QMessageBox.warning(self, "警告", "请先连接网络")
            return

        if not self.additional_ips:
            QMessageBox.warning(self, "警告", "请先添加至少一个额外的局域网 IP")
            return

        # 确认操作
        auto_disable = self.disable_firewall_cb.isChecked()
        ips_text = "\n".join([ip["ip"] for ip in self.additional_ips])
        reply = QMessageBox.question(
            self,
            "确认配置",
            f"即将执行双 IP 挂载配置：\n\n"
            f"【适配器】{self.connected_adapter.name}\n"
            f"【当前主 IP】{self.connected_adapter.ip_address}\n\n"
            f"【将添加的额外 IP】\n{ips_text}\n\n"
            f"【关闭防火墙】{'是' if auto_disable else '否'}\n\n"
            f"配置完成后，电脑将同时拥有多个 IP：\n"
            f"1. 原主 IP - 用于上网\n"
            f"2. 额外 IP - 用于双机通信\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._execute_config(auto_disable)

    def _execute_config(self, auto_disable_firewall: bool):
        """执行自动配置"""
        self.config_btn.setEnabled(False)
        self.config_btn.setText("配置中...")
        self.restore_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.result_text.clear()
        self.result_text.append("开始双 IP 挂载配置...\n")

        # 在后台线程中执行
        self.config_thread = AutoConfigThread(
            self.network_manager,
            self.firewall_manager,
            self.additional_ips,
            auto_disable_firewall
        )
        self.config_thread.progress.connect(self._on_progress)
        self.config_thread.finished.connect(self._on_config_finished)
        self.config_thread.error.connect(self._on_config_error)
        self.config_thread.start()

    def _on_progress(self, value: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self.result_text.append(f"[{value}%] {message}")

    def _on_config_finished(self, success: bool, message: str):
        """配置完成"""
        self.config_btn.setEnabled(True)
        self.config_btn.setText("一键配置")
        self.restore_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.result_text.append(f"\n{'=' * 40}\n{message}")

        if success:
            self.status_label.setText("配置完成！")
            self.status_message.emit("配置成功")
            # 重新加载适配器
            self._load_adapters()
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("配置失败")
            self.status_message.emit("配置失败")

    def _on_config_error(self, error: str):
        """配置失败"""
        self.config_btn.setEnabled(True)
        self.config_btn.setText("一键配置")
        self.restore_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.result_text.append(f"\n错误: {error}")
        self.status_label.setText("配置失败")
        self.error_message.emit("配置失败", error)
        self.status_message.emit("配置失败")

    def _validate_ip(self, ip: str) -> bool:
        """验证 IP 地址格式"""
        import re
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False

        for i in range(1, 5):
            octet = int(match.group(i))
            if octet < 0 or octet > 255:
                return False

        return True

    def closeEvent(self, event):
        """关闭事件 - 保存当前状态"""
        self._save_current_state()
        event.accept()

    def _start_auto_config(self):
        """开始自动配置"""
        ip_address = self.ip_input.text().strip()

        # 验证 IP 地址
        if not ip_address:
            QMessageBox.warning(self, "警告", "请输入 IP 地址")
            return

        if not self._validate_ip(ip_address):
            QMessageBox.warning(self, "警告", "请输入有效的 IP 地址格式\n例如: 192.168.88.26")
            return

        # 确认操作
        auto_disable = self.disable_firewall_cb.isChecked()
        reply = QMessageBox.question(
            self,
            "确认配置",
            f"即将执行双 IP 挂载配置：\n\n"
            f"【第一步】固定当前热点 IP 为静态\n"
            f"【第二步】挂载新的局域网 IP: {ip_address}\n"
            f"【第三步】关闭防火墙: {'是' if auto_disable else '否'}\n"
            f"【第四步】测试连通性\n\n"
            f"配置完成后，电脑将同时拥有两个 IP：\n"
            f"1. 原热点 IP - 用于上网\n"
            f"2. 新局域网 IP ({ip_address}) - 用于双机通信\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._execute_config(ip_address, auto_disable)

    def _execute_config(self, ip_address: str, auto_disable_firewall: bool):
        """执行自动配置"""
        # 禁用按钮
        self.config_btn.setEnabled(False)
        self.config_btn.setText("配置中...")

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 清除结果
        self.result_text.clear()
        self.result_text.append("开始自动配置...\n")

        # 更新状态
        self.status_label.setText("正在配置...")
        self.status_message.emit("开始自动配置")

        # 在后台线程中执行
        self.config_thread = AutoConfigThread(
            self.network_manager,
            self.firewall_manager,
            ip_address,
            auto_disable_firewall
        )
        self.config_thread.progress.connect(self._on_progress)
        self.config_thread.finished.connect(self._on_config_finished)
        self.config_thread.error.connect(self._on_config_error)
        self.config_thread.start()

    def _on_progress(self, value: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self.result_text.append(f"[{value}%] {message}")

    def _on_config_finished(self, success: bool, message: str):
        """配置完成"""
        # 启用按钮
        self.config_btn.setEnabled(True)
        self.config_btn.setText("一键配置")

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 更新结果
        self.result_text.append(f"\n{'=' * 40}\n{message}")

        if success:
            self.status_label.setText("配置完成！")
            self.status_message.emit("配置成功")
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("配置失败")
            self.status_message.emit("配置失败")

    def _on_config_error(self, error: str):
        """配置失败"""
        # 启用按钮
        self.config_btn.setEnabled(True)
        self.config_btn.setText("一键配置")

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 更新结果
        self.result_text.append(f"\n错误: {error}")

        # 更新状态
        self.status_label.setText("配置失败")
        self.error_message.emit("配置失败", error)
        self.status_message.emit("配置失败")

    def _validate_ip(self, ip: str) -> bool:
        """验证 IP 地址格式"""
        import re
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False

        # 检查每个 octet 的范围
        for i in range(1, 5):
            octet = int(match.group(i))
            if octet < 0 or octet > 255:
                return False

        return True
