"""防火墙管理模块 - Windows Defender 防火墙控制"""

import subprocess
import re
from dataclasses import dataclass
from typing import Optional


class FirewallError(Exception):
    """防火墙操作错误"""
    pass


class FirewallPermissionError(FirewallError):
    """权限不足"""
    pass


class FirewallCommandError(FirewallError):
    """命令执行失败"""
    pass


@dataclass
class FirewallStatus:
    """防火墙状态"""
    enabled: bool
    profile: str  # "domain", "private", "public"
    error_message: Optional[str] = None


class FirewallManager:
    """防火墙管理器"""

    def __init__(self, timeout: int = 30):
        """
        初始化防火墙管理器

        Args:
            timeout: 命令执行超时时间（秒）
        """
        self.timeout = timeout

    def _run_powershell(self, command: str) -> tuple[bool, str, str]:
        """
        执行 PowerShell 命令

        Args:
            command: 要执行的 PowerShell 命令

        Returns:
            (成功标志, 标准输出, 标准错误)
        """
        try:
            # 构建完整的 PowerShell 命令
            ps_cmd = f'powershell -Command "{command}"'

            result = subprocess.run(
                ps_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            return result.returncode == 0, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            raise FirewallCommandError(f"PowerShell 命令执行超时: {command}")
        except Exception as e:
            raise FirewallCommandError(f"PowerShell 命令执行失败: {e}")

    def get_status(self, profile: str = "all") -> list[FirewallStatus]:
        """
        获取防火墙状态

        Args:
            profile: 防火墙配置文件 ("all", "domain", "private", "public")

        Returns:
            防火墙状态列表
        """
        statuses = []

        cmd = "Get-NetFirewallProfile | Select-Object Name, Enabled"
        success, stdout, stderr = self._run_powershell(cmd)

        if not success:
            raise FirewallCommandError(f"获取防火墙状态失败: {stderr}")

        # 解析输出
        lines = stdout.strip().split('\n')
        for line in lines[1:]:  # 跳过标题行
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0].lower()
                enabled = parts[1].lower() == "true"

                if profile == "all" or profile == name:
                    statuses.append(FirewallStatus(
                        enabled=enabled,
                        profile=name
                    ))

        return statuses

    def enable(self, profile: str = "all") -> bool:
        """
        启用防火墙

        Args:
            profile: 防火墙配置文件 ("all", "domain", "private", "public")

        Returns:
            操作是否成功
        """
        if profile == "all":
            cmd = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True"
        else:
            cmd = f"Set-NetFirewallProfile -Profile {profile.capitalize()} -Enabled True"

        success, stdout, stderr = self._run_powershell(cmd)

        if not success:
            raise FirewallCommandError(f"启用防火墙失败: {stderr}")

        return True

    def disable(self, profile: str = "all") -> bool:
        """
        禁用防火墙

        Args:
            profile: 防火墙配置文件 ("all", "domain", "private", "public")

        Returns:
            操作是否成功
        """
        if profile == "all":
            cmd = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False"
        else:
            cmd = f"Set-NetFirewallProfile -Profile {profile.capitalize()} -Enabled False"

        success, stdout, stderr = self._run_powershell(cmd)

        if not success:
            raise FirewallCommandError(f"禁用防火墙失败: {stderr}")

        return True

    def is_enabled(self, profile: str = "private") -> bool:
        """
        检查指定配置文件的防火墙是否启用

        Args:
            profile: 防火墙配置文件

        Returns:
            是否启用
        """
        statuses = self.get_status(profile)

        for status in statuses:
            if status.profile == profile:
                return status.enabled

        return False

    def add_rule(
        self,
        name: str,
        direction: str = "inbound",
        action: str = "allow",
        protocol: str = "tcp",
        localport: Optional[str] = None,
        remoteaddress: Optional[str] = None
    ) -> bool:
        """
        添加防火墙规则

        Args:
            name: 规则名称
            direction: 方向 ("inbound", "outbound")
            action: 动作 ("allow", "block")
            protocol: 协议 ("tcp", "udp", "icmpv4")
            localport: 本地端口
            remoteaddress: 远程地址

        Returns:
            操作是否成功
        """
        cmd = f'New-NetFirewallRule -DisplayName "{name}" -Direction {direction.capitalize()} -Action {action.capitalize()}'

        if protocol:
            cmd += f" -Protocol {protocol.upper()}"
        if localport:
            cmd += f" -LocalPort {localport}"
        if remoteaddress:
            cmd += f" -RemoteAddress {remoteaddress}"

        success, stdout, stderr = self._run_powershell(cmd)

        if not success:
            raise FirewallCommandError(f"添加防火墙规则失败: {stderr}")

        return True

    def remove_rule(self, name: str) -> bool:
        """
        移除防火墙规则

        Args:
            name: 规则名称

        Returns:
            操作是否成功
        """
        cmd = f'Remove-NetFirewallRule -DisplayName "{name}"'

        success, stdout, stderr = self._run_powershell(cmd)

        if not success:
            # 规则可能不存在
            if "没有找到匹配项" in stderr or "No matching rule" in stderr:
                return True
            raise FirewallCommandError(f"移除防火墙规则失败: {stderr}")

        return True
