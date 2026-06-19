"""网络配置面板模块"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QSplitter, QFrame,
    QAbstractItemView, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from ..core.network import NetworkManager, NetworkAdapter, NetworkError
from ..utils.config import ConfigManager, SavedConfig


class LoadAdaptersThread(QThread):
    """加载适配器线程"""
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


class NetworkPanel(QWidget):
    """网络配置面板"""

    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str, str)

    def __init__(
        self,
        network_manager: NetworkManager,
        config_manager: ConfigManager
    ):
        super().__init__()

        self.network_manager = network_manager
        self.config_manager = config_manager
        self.adapters = []
        self.current_adapter = None

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

        # ============================================
        # 网络适配器信息区
        # ============================================
        adapter_group = QGroupBox("网络适配器")
        adapter_layout = QVBoxLayout(adapter_group)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新适配器")
        self.refresh_btn.clicked.connect(self._load_adapters)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        adapter_layout.addLayout(refresh_layout)

        # 适配器详细信息
        self.adapter_info_label = QLabel("正在检测网络适配器...")
        self.adapter_info_label.setStyleSheet("background-color: #f8f9fa; padding: 8px; border-radius: 4px;")
        self.adapter_info_label.setWordWrap(True)
        adapter_layout.addWidget(self.adapter_info_label)

        # 适配器选择
        adapter_select_layout = QHBoxLayout()
        adapter_select_layout.addWidget(QLabel("选择适配器:"))
        self.adapter_combo = QComboBox()
        self.adapter_combo.setMinimumWidth(200)
        self.adapter_combo.currentIndexChanged.connect(self._on_adapter_combo_changed)
        adapter_select_layout.addWidget(self.adapter_combo)
        adapter_select_layout.addStretch()
        adapter_layout.addLayout(adapter_select_layout)

        layout.addWidget(adapter_group)

        # ============================================
        # 当前适配器的 IP 列表
        # ============================================
        ip_list_group = QGroupBox("当前适配器的 IP 列表")
        ip_list_layout = QVBoxLayout(ip_list_group)

        self.ip_table = QTableWidget()
        self.ip_table.setColumnCount(3)
        self.ip_table.setHorizontalHeaderLabels(["IP 地址", "子网掩码", "类型"])
        self.ip_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ip_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ip_table.setMaximumHeight(150)
        ip_list_layout.addWidget(self.ip_table)

        layout.addWidget(ip_list_group)

        # ============================================
        # 手动配置区
        # ============================================
        config_group = QGroupBox("手动配置")
        config_layout = QFormLayout(config_group)

        # 目标网段
        subnet_layout = QHBoxLayout()
        self.subnet_input = QLineEdit("192.168.88")
        self.subnet_input.setMaximumWidth(150)
        subnet_layout.addWidget(self.subnet_input)
        subnet_layout.addWidget(QLabel("."))
        self.ip_suffix_input = QLineEdit("26")
        self.ip_suffix_input.setMaximumWidth(80)
        subnet_layout.addWidget(self.ip_suffix_input)
        subnet_layout.addStretch()
        config_layout.addRow("目标网段:", subnet_layout)

        # 子网掩码
        self.mask_input = QLineEdit("255.255.255.0")
        config_layout.addRow("子网掩码:", self.mask_input)

        # 默认网关
        self.gateway_input = QLineEdit()
        self.gateway_input.setPlaceholderText("可选（保持原网关即可）")
        config_layout.addRow("默认网关:", self.gateway_input)

        # DNS 服务器
        self.dns_input = QLineEdit("114.114.114.114")
        config_layout.addRow("DNS 服务器:", self.dns_input)

        # 保存配置
        save_config_layout = QHBoxLayout()
        self.config_name_input = QLineEdit()
        self.config_name_input.setPlaceholderText("配置名称")
        save_config_layout.addWidget(self.config_name_input)
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self._save_config)
        save_config_layout.addWidget(self.save_config_btn)
        config_layout.addRow("保存配置:", save_config_layout)

        layout.addWidget(config_group)

        # ============================================
        # 操作按钮
        # ============================================
        btn_layout = QHBoxLayout()

        self.set_static_ip_btn = QPushButton("设置静态 IP")
        self.set_static_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.set_static_ip_btn.clicked.connect(self._set_static_ip)
        btn_layout.addWidget(self.set_static_ip_btn)

        self.add_secondary_ip_btn = QPushButton("添加额外 IP")
        self.add_secondary_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.add_secondary_ip_btn.clicked.connect(self._add_secondary_ip)
        btn_layout.addWidget(self.add_secondary_ip_btn)

        self.remove_ip_btn = QPushButton("移除选中 IP")
        self.remove_ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.remove_ip_btn.clicked.connect(self._remove_ip)
        btn_layout.addWidget(self.remove_ip_btn)

        self.set_dhcp_btn = QPushButton("还原为 DHCP")
        self.set_dhcp_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        self.set_dhcp_btn.clicked.connect(self._set_dhcp)
        btn_layout.addWidget(self.set_dhcp_btn)

        layout.addLayout(btn_layout)

        # ============================================
        # 状态显示
        # ============================================
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

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

        # 填充下拉框时阻塞信号，避免 addItem/setCurrentIndex 反复触发回调
        self.adapter_combo.blockSignals(True)
        self.adapter_combo.clear()
        for adapter in adapters:
            self.adapter_combo.addItem(f"{adapter.name} ({adapter.status.value})", adapter.name)

        # 选中第一个已连接的适配器
        target_index = 0
        for i, adapter in enumerate(adapters):
            if adapter.status.value == "connected":
                target_index = i
                break
        if adapters:
            self.adapter_combo.setCurrentIndex(target_index)
        self.adapter_combo.blockSignals(False)

        # 填充完成后手动同步一次当前适配器的信息
        if adapters:
            self.current_adapter = adapters[target_index]
            self._update_adapter_info()
            self._update_ip_table()
        else:
            self.current_adapter = None
            self.adapter_info_label.setText("未检测到物理网卡")

        self.status_label.setText(f"检测到 {len(adapters)} 个网络适配器")

    def _on_adapters_error(self, error: str):
        """适配器加载失败"""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("检测失败")
        self.adapter_info_label.setText(f"检测失败: {error}")

    def _on_adapter_combo_changed(self, index):
        """适配器选择变更"""
        if index >= 0 and index < len(self.adapters):
            self.current_adapter = self.adapters[index]
            self._update_adapter_info()
            self._update_ip_table()
            self.status_message.emit(f"已选择: {self.current_adapter.name}")

    def _update_adapter_info(self):
        """更新适配器详细信息"""
        if not self.current_adapter:
            self.adapter_info_label.setText("未选择适配器")
            return

        info_text = (
            f"适配器: {self.current_adapter.name}\n"
            f"状态: {self.current_adapter.status.value}\n"
            f"主 IP: {self.current_adapter.ip_address or '未分配'}\n"
            f"子网掩码: {self.current_adapter.subnet_mask or '未分配'}\n"
            f"默认网关: {self.current_adapter.default_gateway or '未分配'}\n"
            f"DNS: {', '.join(self.current_adapter.dns_servers) if self.current_adapter.dns_servers else '未分配'}\n"
            f"DHCP: {'是' if self.current_adapter.is_dhcp else '否（静态）'}"
        )
        self.adapter_info_label.setText(info_text)

    def _update_ip_table(self):
        """更新 IP 列表表格"""
        self.ip_table.setRowCount(0)

        if not self.current_adapter:
            return

        # 获取所有 IP 地址
        ips = self.network_manager.get_all_ips(self.current_adapter.name)

        self.ip_table.setRowCount(len(ips))
        for i, ip_info in enumerate(ips):
            self.ip_table.setItem(i, 0, QTableWidgetItem(ip_info.get("ip", "")))
            self.ip_table.setItem(i, 1, QTableWidgetItem(ip_info.get("mask", "")))

            # 确定类型
            ip = ip_info.get("ip", "")
            if ip == self.current_adapter.ip_address:
                ip_type = "主 IP（上网用）"
            else:
                ip_type = "额外 IP（双机通信）"
            self.ip_table.setItem(i, 2, QTableWidgetItem(ip_type))

    def _save_config(self):
        """保存配置"""
        name = self.config_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入配置名称")
            return

        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 创建配置
        config = SavedConfig(
            name=name,
            adapter_name=self.current_adapter.name,
            ip_address=f"{self.subnet_input.text()}.{self.ip_suffix_input.text()}",
            subnet_mask=self.mask_input.text(),
            default_gateway=self.gateway_input.text() or None,
            dns_servers=[self.dns_input.text()],
            description=f"手动配置 - {self.current_adapter.name}"
        )

        # 保存配置
        try:
            self.config_manager.add_saved_config(config)
            self.status_label.setText(f"配置 '{name}' 已保存")
            self.config_name_input.clear()
            self.status_message.emit(f"配置 '{name}' 已保存")
        except Exception as e:
            self.error_message.emit("保存失败", str(e))

    def _set_static_ip(self):
        """设置静态 IP"""
        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 构建 IP 地址
        ip_address = f"{self.subnet_input.text()}.{self.ip_suffix_input.text()}"
        subnet_mask = self.mask_input.text()
        gateway = self.gateway_input.text() or None
        dns = [self.dns_input.text()] if self.dns_input.text() else None

        # 确认操作
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要为 {self.current_adapter.name} 设置静态 IP 吗？\n\n"
            f"IP 地址: {ip_address}\n"
            f"子网掩码: {subnet_mask}\n"
            f"默认网关: {gateway or '保持不变'}\n"
            f"DNS: {dns[0] if dns else '保持不变'}\n\n"
            f"注意: 这会替换当前的主 IP！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_label.setText("正在配置静态 IP...")
                self.network_manager.set_static_ip(
                    self.current_adapter.name,
                    ip_address,
                    subnet_mask,
                    gateway,
                    dns
                )
                self.status_label.setText("静态 IP 配置成功")
                self.status_message.emit("静态 IP 配置成功")
                self._load_adapters()
            except NetworkError as e:
                self.error_message.emit("配置失败", str(e))
                self.status_label.setText("静态 IP 配置失败")

    def _add_secondary_ip(self):
        """添加额外的 IP"""
        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 构建 IP 地址
        ip_address = f"{self.subnet_input.text()}.{self.ip_suffix_input.text()}"
        subnet_mask = self.mask_input.text()

        # 确认操作
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要为 {self.current_adapter.name} 添加额外的 IP 吗？\n\n"
            f"IP 地址: {ip_address}\n"
            f"子网掩码: {subnet_mask}\n\n"
            f"注意: 这会保留当前主 IP，额外添加一个新的 IP。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_label.setText("正在添加额外 IP...")
                self.network_manager.add_secondary_ip(
                    self.current_adapter.name,
                    ip_address,
                    subnet_mask
                )
                self.status_label.setText("额外 IP 添加成功")
                self.status_message.emit("额外 IP 添加成功")
                self._load_adapters()
            except NetworkError as e:
                self.error_message.emit("添加失败", str(e))
                self.status_label.setText("额外 IP 添加失败")

    def _remove_ip(self):
        """移除 IP"""
        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 获取选中的 IP
        selected_rows = self.ip_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先在 IP 列表中选择要移除的 IP")
            return

        row = selected_rows[0].row()
        ip_address = self.ip_table.item(row, 0).text()

        # 检查是否是主 IP
        if ip_address == self.current_adapter.ip_address:
            QMessageBox.warning(self, "警告", "不能移除主 IP！\n请使用「设置静态 IP」或「还原为 DHCP」来修改主 IP。")
            return

        # 确认操作
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要从 {self.current_adapter.name} 移除 IP {ip_address} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_label.setText("正在移除 IP...")
                self.network_manager.remove_secondary_ip(
                    self.current_adapter.name,
                    ip_address
                )
                self.status_label.setText("IP 移除成功")
                self.status_message.emit("IP 移除成功")
                self._load_adapters()
            except NetworkError as e:
                self.error_message.emit("移除失败", str(e))
                self.status_label.setText("IP 移除失败")

    def _set_dhcp(self):
        """设置为 DHCP"""
        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 确认操作
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要将 {self.current_adapter.name} 还原为 DHCP 自动获取 IP 吗？\n\n"
            f"这会：\n"
            f"1. 删除所有额外的 IP 地址\n"
            f"2. 将主 IP 改为自动获取\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_label.setText("正在还原为 DHCP...")
                self.network_manager.set_dhcp(self.current_adapter.name)
                self.status_label.setText("已还原为 DHCP")
                self.status_message.emit("已还原为 DHCP")
                self._load_adapters()
            except NetworkError as e:
                self.error_message.emit("还原失败", str(e))
                self.status_label.setText("还原失败")
