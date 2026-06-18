"""主窗口模块"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QStatusBar, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

from .network_panel import NetworkPanel
from .firewall_panel import FirewallPanel
from .test_panel import TestPanel
from ..core.network import NetworkManager
from ..core.firewall import FirewallManager
from ..core.ping import PingTester
from ..utils.config import ConfigManager


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化管理器
        self.network_manager = NetworkManager()
        self.firewall_manager = FirewallManager()
        self.ping_tester = PingTester()
        self.config_manager = ConfigManager()

        # 初始化 UI
        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("Subnet Link Weaver v1.0.0")
        self.setMinimumSize(QSize(800, 600))

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建标题
        title_label = QLabel("局域网多 IP 配置工具")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 添加标签页
        self.network_panel = NetworkPanel(
            self.network_manager,
            self.config_manager
        )
        self.firewall_panel = FirewallPanel(self.firewall_manager)
        self.test_panel = TestPanel(self.ping_tester)

        self.tab_widget.addTab(self.network_panel, "网络配置")
        self.tab_widget.addTab(self.firewall_panel, "防火墙管理")
        self.tab_widget.addTab(self.test_panel, "连通性测试")

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 连接信号
        self._connect_signals()

    def _connect_signals(self):
        """连接信号"""
        # 网络面板信号
        self.network_panel.status_message.connect(self._update_status)
        self.network_panel.error_message.connect(self._show_error)

        # 防火墙面板信号
        self.firewall_panel.status_message.connect(self._update_status)
        self.firewall_panel.error_message.connect(self._show_error)

        # 测试面板信号
        self.test_panel.status_message.connect(self._update_status)
        self.test_panel.error_message.connect(self._show_error)

    def _update_status(self, message: str):
        """更新状态栏消息"""
        self.status_bar.showMessage(message)

    def _show_error(self, title: str, message: str):
        """显示错误消息框"""
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 保存窗口大小
        config = self.config_manager.load_app_config()
        config.window_width = self.width()
        config.window_height = self.height()
        self.config_manager.save_app_config(config)

        event.accept()
