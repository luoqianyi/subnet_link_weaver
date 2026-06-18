"""防火墙管理面板模块"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from ..core.firewall import FirewallManager, FirewallStatus, FirewallError


class FirewallStatusThread(QThread):
    """防火墙状态检查线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, firewall_manager: FirewallManager):
        super().__init__()
        self.firewall_manager = firewall_manager

    def run(self):
        try:
            statuses = self.firewall_manager.get_status()
            self.finished.emit(statuses)
        except Exception as e:
            self.error.emit(str(e))


class FirewallToggleThread(QThread):
    """防火墙开关线程"""
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, firewall_manager: FirewallManager, enable: bool):
        super().__init__()
        self.firewall_manager = firewall_manager
        self.enable = enable

    def run(self):
        try:
            if self.enable:
                result = self.firewall_manager.enable()
            else:
                result = self.firewall_manager.disable()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FirewallPanel(QWidget):
    """防火墙管理面板"""

    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str, str)

    def __init__(self, firewall_manager: FirewallManager):
        super().__init__()

        self.firewall_manager = firewall_manager
        self.statuses = []

        self._init_ui()
        self._check_status()

    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 防火墙状态组
        status_group = QGroupBox("防火墙状态")
        status_layout = QVBoxLayout(status_group)

        # 状态显示
        self.status_label = QLabel("正在检查防火墙状态...")
        self.status_label.setFont(QFont("Microsoft YaHei", 12))
        status_layout.addWidget(self.status_label)

        # 状态详情
        self.detail_frame = QFrame()
        self.detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.detail_frame.setStyleSheet(
            "QFrame { background-color: #f5f5f5; border: 1px solid #ddd; padding: 10px; }"
        )
        self.detail_layout = QVBoxLayout(self.detail_frame)
        status_layout.addWidget(self.detail_frame)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self._check_status)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        status_layout.addLayout(refresh_layout)

        layout.addWidget(status_group)

        # 防火墙操作组
        operation_group = QGroupBox("防火墙操作")
        operation_layout = QVBoxLayout(operation_group)

        # 警告信息
        warning_label = QLabel(
            "警告: 关闭防火墙可能会降低系统安全性。\n"
            "建议在完成网络配置后重新启用防火墙。"
        )
        warning_label.setStyleSheet(
            "QLabel { color: #d35400; background-color: #fdebd0; "
            "padding: 10px; border: 1px solid #f5b041; }"
        )
        warning_label.setWordWrap(True)
        operation_layout.addWidget(warning_label)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.enable_btn = QPushButton("启用防火墙")
        self.enable_btn.setMinimumHeight(40)
        self.enable_btn.clicked.connect(self._enable_firewall)
        btn_layout.addWidget(self.enable_btn)

        self.disable_btn = QPushButton("禁用防火墙")
        self.disable_btn.setMinimumHeight(40)
        self.disable_btn.clicked.connect(self._disable_firewall)
        btn_layout.addWidget(self.disable_btn)

        operation_layout.addLayout(btn_layout)

        layout.addWidget(operation_group)

        # 添加弹性空间
        layout.addStretch()

    def _check_status(self):
        """检查防火墙状态"""
        self.status_label.setText("正在检查防火墙状态...")
        self.refresh_btn.setEnabled(False)

        # 在后台线程中执行
        self.status_thread = FirewallStatusThread(self.firewall_manager)
        self.status_thread.finished.connect(self._on_status_checked)
        self.status_thread.error.connect(self._on_status_error)
        self.status_thread.start()

    def _on_status_checked(self, statuses: list):
        """防火墙状态检查完成"""
        self.statuses = statuses
        self._update_status_display()
        self.refresh_btn.setEnabled(True)
        self.status_message.emit("防火墙状态检查完成")

    def _on_status_error(self, error: str):
        """防火墙状态检查失败"""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("检查失败")
        self.error_message.emit("检查失败", error)
        self.status_message.emit("防火墙状态检查失败")

    def _update_status_display(self):
        """更新状态显示"""
        if not self.statuses:
            self.status_label.setText("未找到防火墙配置")
            return

        # 检查是否有任何配置文件启用
        any_enabled = any(s.enabled for s in self.statuses)
        any_disabled = any(not s.enabled for s in self.statuses)

        if any_enabled and not any_disabled:
            self.status_label.setText("防火墙状态: 已启用")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        elif any_disabled and not any_enabled:
            self.status_label.setText("防火墙状态: 已禁用")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.status_label.setText("防火墙状态: 部分启用")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")

        # 更新详情
        # 清除旧的详情
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新的详情
        for status in self.statuses:
            detail_label = QLabel(
                f"{status.profile.capitalize()}: "
                f"{'已启用' if status.enabled else '已禁用'}"
            )
            if status.enabled:
                detail_label.setStyleSheet("color: green;")
            else:
                detail_label.setStyleSheet("color: red;")
            self.detail_layout.addWidget(detail_label)

    def _enable_firewall(self):
        """启用防火墙"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要启用所有防火墙配置文件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_message.emit("正在启用防火墙...")
            self.enable_btn.setEnabled(False)
            self.disable_btn.setEnabled(False)

            # 在后台线程中执行
            self.toggle_thread = FirewallToggleThread(
                self.firewall_manager,
                enable=True
            )
            self.toggle_thread.finished.connect(self._on_toggle_finished)
            self.toggle_thread.error.connect(self._on_toggle_error)
            self.toggle_thread.start()

    def _disable_firewall(self):
        """禁用防火墙"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要禁用所有防火墙配置文件吗？\n\n"
            "这可能会降低系统安全性。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_message.emit("正在禁用防火墙...")
            self.enable_btn.setEnabled(False)
            self.disable_btn.setEnabled(False)

            # 在后台线程中执行
            self.toggle_thread = FirewallToggleThread(
                self.firewall_manager,
                enable=False
            )
            self.toggle_thread.finished.connect(self._on_toggle_finished)
            self.toggle_thread.error.connect(self._on_toggle_error)
            self.toggle_thread.start()

    def _on_toggle_finished(self, result: bool):
        """防火墙开关操作完成"""
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)

        if result:
            self.status_message.emit("防火墙操作成功")
            self._check_status()
        else:
            self.error_message.emit("操作失败", "防火墙操作返回失败")

    def _on_toggle_error(self, error: str):
        """防火墙开关操作失败"""
        self.enable_btn.setEnabled(True)
        self.disable_btn.setEnabled(True)
        self.error_message.emit("操作失败", error)
        self.status_message.emit("防火墙操作失败")
