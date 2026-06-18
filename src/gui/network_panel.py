"""网络配置面板模块"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

from ..core.network import NetworkManager, NetworkAdapter, NetworkError
from ..utils.config import ConfigManager, SavedConfig


class RefreshAdaptersThread(QThread):
    """刷新适配器线程"""
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

    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # 上部分：适配器列表
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        # 适配器列表组
        adapter_group = QGroupBox("网络适配器")
        adapter_layout = QVBoxLayout(adapter_group)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新适配器")
        self.refresh_btn.clicked.connect(self._refresh_adapters)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        adapter_layout.addLayout(refresh_layout)

        # 适配器表格
        self.adapter_table = QTableWidget()
        self.adapter_table.setColumnCount(5)
        self.adapter_table.setHorizontalHeaderLabels([
            "适配器名称", "状态", "IP 地址", "子网掩码", "默认网关"
        ])
        self.adapter_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.adapter_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.adapter_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.adapter_table.itemSelectionChanged.connect(
            self._on_adapter_selected
        )
        adapter_layout.addWidget(self.adapter_table)

        top_layout.addWidget(adapter_group)
        splitter.addWidget(top_widget)

        # 下部分：快速配置
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # 快速配置组
        config_group = QGroupBox("快速配置")
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
        self.gateway_input.setPlaceholderText("可选")
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

        bottom_layout.addWidget(config_group)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.set_static_ip_btn = QPushButton("配置静态 IP")
        self.set_static_ip_btn.clicked.connect(self._set_static_ip)
        btn_layout.addWidget(self.set_static_ip_btn)

        self.add_secondary_ip_btn = QPushButton("添加额外 IP")
        self.add_secondary_ip_btn.clicked.connect(self._add_secondary_ip)
        btn_layout.addWidget(self.add_secondary_ip_btn)

        self.remove_ip_btn = QPushButton("移除 IP")
        self.remove_ip_btn.clicked.connect(self._remove_ip)
        btn_layout.addWidget(self.remove_ip_btn)

        btn_layout.addStretch()
        bottom_layout.addLayout(btn_layout)

        splitter.addWidget(bottom_widget)

        # 加载保存的配置
        self._load_saved_configs()

    def _refresh_adapters(self):
        """刷新适配器列表"""
        self.status_message.emit("正在检测网络适配器...")
        self.refresh_btn.setEnabled(False)

        # 在后台线程中执行
        self.refresh_thread = RefreshAdaptersThread(self.network_manager)
        self.refresh_thread.finished.connect(self._on_adapters_refreshed)
        self.refresh_thread.error.connect(self._on_refresh_error)
        self.refresh_thread.start()

    def _on_adapters_refreshed(self, adapters: list):
        """适配器刷新完成"""
        self.adapters = adapters
        self._update_adapter_table()
        self.refresh_btn.setEnabled(True)
        self.status_message.emit(f"检测到 {len(adapters)} 个网络适配器")

    def _on_refresh_error(self, error: str):
        """适配器刷新失败"""
        self.refresh_btn.setEnabled(True)
        self.error_message.emit("检测失败", error)
        self.status_message.emit("适配器检测失败")

    def _update_adapter_table(self):
        """更新适配器表格"""
        self.adapter_table.setRowCount(len(self.adapters))

        for i, adapter in enumerate(self.adapters):
            self.adapter_table.setItem(i, 0, QTableWidgetItem(adapter.name))
            self.adapter_table.setItem(i, 1, QTableWidgetItem(adapter.status.value))
            self.adapter_table.setItem(i, 2, QTableWidgetItem(adapter.ip_address))
            self.adapter_table.setItem(i, 3, QTableWidgetItem(adapter.subnet_mask))
            self.adapter_table.setItem(i, 4, QTableWidgetItem(adapter.default_gateway or ""))

    def _on_adapter_selected(self):
        """适配器选择变更"""
        selected_rows = self.adapter_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self.current_adapter = self.adapters[row]
            self.status_message.emit(f"已选择: {self.current_adapter.name}")

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
            description=f"快速配置 - {self.current_adapter.name}"
        )

        # 保存配置
        try:
            self.config_manager.add_saved_config(config)
            self.status_message.emit(f"配置 '{name}' 已保存")
            self.config_name_input.clear()
        except Exception as e:
            self.error_message.emit("保存失败", str(e))

    def _load_saved_configs(self):
        """加载保存的配置"""
        try:
            configs = self.config_manager.load_saved_configs()
            if configs:
                # 可以在这里添加加载配置的逻辑
                pass
        except Exception as e:
            pass

    def _set_static_ip(self):
        """配置静态 IP"""
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
            f"确定要为 {self.current_adapter.name} 配置静态 IP 吗？\n\n"
            f"IP 地址: {ip_address}\n"
            f"子网掩码: {subnet_mask}\n"
            f"默认网关: {gateway or '无'}\n"
            f"DNS: {dns[0] if dns else '无'}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_message.emit("正在配置静态 IP...")
                self.network_manager.set_static_ip(
                    self.current_adapter.name,
                    ip_address,
                    subnet_mask,
                    gateway,
                    dns
                )
                self.status_message.emit("静态 IP 配置成功")
                self._refresh_adapters()
            except NetworkError as e:
                self.error_message.emit("配置失败", str(e))
                self.status_message.emit("静态 IP 配置失败")

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
            f"子网掩码: {subnet_mask}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_message.emit("正在添加额外 IP...")
                self.network_manager.add_secondary_ip(
                    self.current_adapter.name,
                    ip_address,
                    subnet_mask
                )
                self.status_message.emit("额外 IP 添加成功")
                self._refresh_adapters()
            except NetworkError as e:
                self.error_message.emit("添加失败", str(e))
                self.status_message.emit("额外 IP 添加失败")

    def _remove_ip(self):
        """移除 IP"""
        if not self.current_adapter:
            QMessageBox.warning(self, "警告", "请先选择网络适配器")
            return

        # 构建 IP 地址
        ip_address = f"{self.subnet_input.text()}.{self.ip_suffix_input.text()}"

        # 确认操作
        reply = QMessageBox.question(
            self,
            "确认",
            f"确定要从 {self.current_adapter.name} 移除 IP {ip_address} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.status_message.emit("正在移除 IP...")
                self.network_manager.remove_secondary_ip(
                    self.current_adapter.name,
                    ip_address
                )
                self.status_message.emit("IP 移除成功")
                self._refresh_adapters()
            except NetworkError as e:
                self.error_message.emit("移除失败", str(e))
                self.status_message.emit("IP 移除失败")
