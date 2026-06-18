"""配置管理模块 - 配置文件读写和验证"""

import json
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


class ConfigError(Exception):
    """配置操作错误"""
    pass


class ConfigNotFoundError(ConfigError):
    """配置文件不存在"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    pass


@dataclass
class AppConfig:
    """应用程序配置"""
    # 网络配置
    default_subnet: str = "192.168.88"
    default_mask: str = "255.255.255.0"
    default_dns: list[str] = field(default_factory=lambda: ["114.114.114.114"])

    # 防火墙配置
    auto_disable_firewall: bool = False
    firewall_restore_reminder: bool = True

    # Ping 配置
    ping_count: int = 4
    ping_timeout: int = 1000

    # 界面配置
    window_width: int = 800
    window_height: int = 600
    theme: str = "light"

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "default_subnet": self.default_subnet,
            "default_mask": self.default_mask,
            "default_dns": self.default_dns,
            "auto_disable_firewall": self.auto_disable_firewall,
            "firewall_restore_reminder": self.firewall_restore_reminder,
            "ping_count": self.ping_count,
            "ping_timeout": self.ping_timeout,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "theme": self.theme,
            "log_level": self.log_level,
            "log_file": self.log_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建配置"""
        return cls(
            default_subnet=data.get("default_subnet", "192.168.88"),
            default_mask=data.get("default_mask", "255.255.255.0"),
            default_dns=data.get("default_dns", ["114.114.114.114"]),
            auto_disable_firewall=data.get("auto_disable_firewall", False),
            firewall_restore_reminder=data.get("firewall_restore_reminder", True),
            ping_count=data.get("ping_count", 4),
            ping_timeout=data.get("ping_timeout", 1000),
            window_width=data.get("window_width", 800),
            window_height=data.get("window_height", 600),
            theme=data.get("theme", "light"),
            log_level=data.get("log_level", "INFO"),
            log_file=data.get("log_file", "logs/app.log"),
        )


@dataclass
class SavedConfig:
    """保存的配置（用户保存的网络配置）"""
    name: str
    adapter_name: str
    ip_address: str
    subnet_mask: str
    default_gateway: Optional[str] = None
    dns_servers: list[str] = field(default_factory=list)
    description: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "adapter_name": self.adapter_name,
            "ip_address": self.ip_address,
            "subnet_mask": self.subnet_mask,
            "default_gateway": self.default_gateway,
            "dns_servers": self.dns_servers,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavedConfig":
        """从字典创建配置"""
        return cls(
            name=data.get("name", ""),
            adapter_name=data.get("adapter_name", ""),
            ip_address=data.get("ip_address", ""),
            subnet_mask=data.get("subnet_mask", "255.255.255.0"),
            default_gateway=data.get("default_gateway"),
            dns_servers=data.get("dns_servers", ["114.114.114.114"]),
            description=data.get("description"),
        )


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置目录路径
        """
        if config_dir is None:
            # 使用默认配置目录
            self.config_dir = Path.home() / ".subnet_link_weaver"
        else:
            self.config_dir = Path(config_dir)

        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 配置文件路径
        self.app_config_file = self.config_dir / "app_config.json"
        self.saved_configs_file = self.config_dir / "saved_configs.json"
        self.history_ips_file = self.config_dir / "history_ips.json"
        self.network_state_file = self.config_dir / "network_state.json"

    def load_app_config(self) -> AppConfig:
        """
        加载应用程序配置

        Returns:
            应用程序配置
        """
        if not self.app_config_file.exists():
            # 返回默认配置
            return AppConfig()

        try:
            with open(self.app_config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except json.JSONDecodeError as e:
            raise ConfigError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise ConfigError(f"加载配置文件失败: {e}")

    def save_app_config(self, config: AppConfig) -> bool:
        """
        保存应用程序配置

        Args:
            config: 应用程序配置

        Returns:
            操作是否成功
        """
        try:
            with open(self.app_config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            raise ConfigError(f"保存配置文件失败: {e}")

    def load_saved_configs(self) -> list[SavedConfig]:
        """
        加载保存的配置列表

        Returns:
            保存的配置列表
        """
        if not self.saved_configs_file.exists():
            return []

        try:
            with open(self.saved_configs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [SavedConfig.from_dict(item) for item in data]
        except json.JSONDecodeError as e:
            raise ConfigError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise ConfigError(f"加载配置文件失败: {e}")

    def save_saved_configs(self, configs: list[SavedConfig]) -> bool:
        """
        保存配置列表

        Args:
            configs: 保存的配置列表

        Returns:
            操作是否成功
        """
        try:
            data = [config.to_dict() for config in configs]
            with open(self.saved_configs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            raise ConfigError(f"保存配置文件失败: {e}")

    def add_saved_config(self, config: SavedConfig) -> bool:
        """
        添加保存的配置

        Args:
            config: 要添加的配置

        Returns:
            操作是否成功
        """
        configs = self.load_saved_configs()

        # 检查是否已存在同名配置
        for i, existing in enumerate(configs):
            if existing.name == config.name:
                # 替换现有配置
                configs[i] = config
                return self.save_saved_configs(configs)

        # 添加新配置
        configs.append(config)
        return self.save_saved_configs(configs)

    def remove_saved_config(self, name: str) -> bool:
        """
        移除保存的配置

        Args:
            name: 配置名称

        Returns:
            操作是否成功
        """
        configs = self.load_saved_configs()
        configs = [c for c in configs if c.name != name]
        return self.save_saved_configs(configs)

    def get_saved_config(self, name: str) -> Optional[SavedConfig]:
        """
        获取指定名称的保存配置

        Args:
            name: 配置名称

        Returns:
            保存的配置，如果不存在则返回 None
        """
        configs = self.load_saved_configs()
        for config in configs:
            if config.name == name:
                return config
        return None

    # ============================================
    # 历史 IP 记录
    # ============================================

    def load_history_ips(self) -> list[str]:
        """
        加载历史 IP 记录

        Returns:
            历史 IP 列表
        """
        if not self.history_ips_file.exists():
            return []

        try:
            with open(self.history_ips_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("ips", [])
        except Exception:
            return []

    def save_history_ips(self, ips: list[str]) -> bool:
        """
        保存历史 IP 记录

        Args:
            ips: IP 列表

        Returns:
            操作是否成功
        """
        try:
            with open(self.history_ips_file, "w", encoding="utf-8") as f:
                json.dump({"ips": ips}, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def add_history_ip(self, ip: str) -> bool:
        """
        添加历史 IP 记录

        Args:
            ip: IP 地址

        Returns:
            操作是否成功
        """
        ips = self.load_history_ips()

        # 移除重复项
        if ip in ips:
            ips.remove(ip)

        # 添加到开头
        ips.insert(0, ip)

        # 最多保存 10 条
        ips = ips[:10]

        return self.save_history_ips(ips)

    def remove_history_ip(self, ip: str) -> bool:
        """
        移除历史 IP 记录

        Args:
            ip: IP 地址

        Returns:
            操作是否成功
        """
        ips = self.load_history_ips()
        if ip in ips:
            ips.remove(ip)
        return self.save_history_ips(ips)

    # ============================================
    # 网络状态保存/加载（用于还原）
    # ============================================

    def save_network_state(self, state: dict) -> bool:
        """
        保存当前网络状态

        Args:
            state: 网络状态字典

        Returns:
            操作是否成功
        """
        try:
            with open(self.network_state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_network_state(self) -> Optional[dict]:
        """
        加载网络状态

        Returns:
            网络状态字典，如果不存在则返回 None
        """
        if not self.network_state_file.exists():
            return None

        try:
            with open(self.network_state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def clear_network_state(self) -> bool:
        """
        清除网络状态

        Returns:
            操作是否成功
        """
        try:
            if self.network_state_file.exists():
                self.network_state_file.unlink()
            return True
        except Exception:
            return False
