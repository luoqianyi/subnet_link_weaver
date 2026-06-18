"""主窗口模块"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QStatusBar, QMessageBox,
    QPushButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

from .simple_panel import SimplePanel
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

        # 当前模式
        self.current_mode = "simple"  # "simple" 或 "advanced"

        # 预加载的适配器数据
        self.preloaded_adapters = []

        # 初始化 UI（先不显示）
        self._init_ui()

        # 隐藏主窗口，先显示加载窗口
        self.hide()
        self._show_loading()

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

        # 创建标题栏
        title_layout = QHBoxLayout()

        # 标题
        title_label = QLabel("Subnet Link Weaver")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 模式切换按钮
        self.simple_btn = QPushButton("新手模式")
        self.simple_btn.setCheckable(True)
        self.simple_btn.setChecked(True)
        self.simple_btn.setFont(QFont("Microsoft YaHei", 10))
        self.simple_btn.setMinimumHeight(35)
        self.simple_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:checked {
                background-color: #2471a3;
            }
        """)
        self.simple_btn.clicked.connect(lambda: self._switch_mode("simple"))
        title_layout.addWidget(self.simple_btn)

        self.advanced_btn = QPushButton("进阶模式")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.setFont(QFont("Microsoft YaHei", 10))
        self.advanced_btn.setMinimumHeight(35)
        self.advanced_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked {
                background-color: #2c3e50;
            }
        """)
        self.advanced_btn.clicked.connect(lambda: self._switch_mode("advanced"))
        title_layout.addWidget(self.advanced_btn)

        main_layout.addLayout(title_layout)

        # 创建内容区域
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 10, 0, 0)
        main_layout.addWidget(self.content_widget)

        # 创建标签页（进阶模式用）
        self.tab_widget = QTabWidget()
        self.tab_widget.setVisible(False)

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

        self.content_layout.addWidget(self.tab_widget)

        # 创建新手模式面板
        self.simple_panel = SimplePanel(
            self.network_manager,
            self.firewall_manager,
            self.ping_tester,
            self.config_manager
        )
        self.content_layout.addWidget(self.simple_panel)

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 使用新手模式快速配置")

        # 连接信号
        self._connect_signals()

    def _switch_mode(self, mode: str):
        """切换模式"""
        self.current_mode = mode

        if mode == "simple":
            self.simple_btn.setChecked(True)
            self.advanced_btn.setChecked(False)
            self.simple_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:checked {
                    background-color: #2471a3;
                }
            """)
            self.advanced_btn.setStyleSheet("""
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #7f8c8d;
                }
            """)
            self.simple_panel.setVisible(True)
            self.tab_widget.setVisible(False)
            self.status_bar.showMessage("就绪 - 使用新手模式快速配置")
        else:
            self.simple_btn.setChecked(False)
            self.advanced_btn.setChecked(True)
            self.simple_btn.setStyleSheet("""
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #7f8c8d;
                }
            """)
            self.advanced_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:checked {
                    background-color: #2471a3;
                }
            """)
            self.simple_panel.setVisible(False)
            self.tab_widget.setVisible(True)
            self.status_bar.showMessage("就绪 - 使用进阶模式进行详细配置")

    def _connect_signals(self):
        """连接信号"""
        # 新手模式面板信号
        self.simple_panel.status_message.connect(self._update_status)
        self.simple_panel.error_message.connect(self._show_error)

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
        # 保存窗口大小和模式
        config = self.config_manager.load_app_config()
        config.window_width = self.width()
        config.window_height = self.height()
        self.config_manager.save_app_config(config)

        event.accept()

    def _show_loading(self):
        """显示加载窗口"""
        from .loading_window import LoadingWindow

        self.loading_window = LoadingWindow()
        self.loading_window.adapters_loaded.connect(self._on_adapters_loaded)
        self.loading_window.show()

    def _on_adapters_loaded(self, adapters: list):
        """适配器加载完成"""
        self.preloaded_adapters = adapters

        # 关闭加载窗口
        if hasattr(self, 'loading_window'):
            self.loading_window.close()

        # 显示主窗口
        self.show()

        # 将预加载的适配器传递给面板
        if hasattr(self, 'simple_panel'):
            self.simple_panel.adapters = adapters
            self.simple_panel._on_adapters_loaded(adapters)

        if hasattr(self, 'network_panel'):
            self.network_panel.adapters = adapters
            self.network_panel._on_adapters_loaded(adapters)
