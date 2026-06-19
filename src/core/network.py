"""网络管理模块 - 网络适配器检测与配置"""

import subprocess
import re
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class AdapterStatus(Enum):
    """网络适配器状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass
class NetworkAdapter:
    """网络适配器数据模型"""
    name: str
    status: AdapterStatus
    ip_address: str = ""
    subnet_mask: str = ""
    default_gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    is_dhcp: bool = False

    def __str__(self) -> str:
        return f"{self.name} ({self.status.value}) - {self.ip_address}"


class NetworkError(Exception):
    """网络操作错误基类"""
    pass


class AdapterNotFoundError(NetworkError):
    """适配器不存在"""
    pass


class PermissionError(NetworkError):
    """权限不足"""
    pass


class CommandTimeoutError(NetworkError):
    """命令执行超时"""
    pass


class InvalidIPError(NetworkError):
    """无效的 IP 地址"""
    pass


class NetworkManager:
    """网络配置管理器"""

    def __init__(self, timeout: int = 30):
        """
        初始化网络管理器

        Args:
            timeout: 命令执行超时时间（秒）
        """
        self.timeout = timeout

    def _run_command(self, command: str, use_powershell: bool = False) -> tuple[bool, str, str]:
        """
        执行系统命令

        Args:
            command: 要执行的命令
            use_powershell: 是否使用 PowerShell 执行

        Returns:
            (成功标志, 标准输出, 标准错误)
        """
        try:
            if use_powershell:
                # 使用 PowerShell 执行命令，设置 UTF-8 编码
                cmd = f'powershell -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"'
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    timeout=self.timeout
                )
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'cp936', 'latin1']:
                    try:
                        stdout = result.stdout.decode(encoding)
                        stderr = result.stderr.decode(encoding)
                        return result.returncode == 0, stdout, stderr
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 如果所有编码都失败，使用 latin1 作为后备
                stdout = result.stdout.decode('latin1')
                stderr = result.stderr.decode('latin1')
                return result.returncode == 0, stdout, stderr
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    timeout=self.timeout
                )
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'cp936', 'latin1']:
                    try:
                        stdout = result.stdout.decode(encoding)
                        stderr = result.stderr.decode(encoding)
                        return result.returncode == 0, stdout, stderr
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 如果所有编码都失败，使用 latin1 作为后备
                stdout = result.stdout.decode('latin1')
                stderr = result.stderr.decode('latin1')
                return result.returncode == 0, stdout, stderr
        except subprocess.TimeoutExpired:
            raise CommandTimeoutError(f"命令执行超时: {command}")
        except Exception as e:
            raise NetworkError(f"命令执行失败: {e}")

    # 物理网卡判断：排除虚拟/隧道/回环等
    _VIRTUAL_KEYWORDS = (
        "virtual", "vmware", "virtualbox", "hyper-v", "loopback", "vethernet",
        "tap", "tun", "pseudo", "teredo", "isatap", "vpn", "bluetooth", "蓝牙",
        "wan miniport", "miniport", "kernel debug", "wfp",
    )

    def _is_physical(self, name: str, description: str) -> bool:
        """根据名称/描述判断是否物理网卡"""
        text = f"{name} {description}".lower()
        return not any(kw in text for kw in self._VIRTUAL_KEYWORDS)

    def _run_ps_script(self, script: str) -> tuple[bool, str, str]:
        """
        将 PowerShell 脚本写入临时 .ps1 文件并执行，
        避免 Python -> shell -> PowerShell 多层引号转义问题。
        """
        import tempfile
        import os

        # 用 UTF-8 BOM 保证 PowerShell 正确识别中文
        fd, path = tempfile.mkstemp(suffix=".ps1")
        try:
            with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
                f.write(script)

            cmd = (
                f'powershell -NoProfile -ExecutionPolicy Bypass '
                f'-Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & \'{path}\'"'
            )
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=self.timeout
            )
            for encoding in ("utf-8", "gbk", "cp936", "latin1"):
                try:
                    stdout = result.stdout.decode(encoding)
                    stderr = result.stderr.decode(encoding)
                    return result.returncode == 0, stdout, stderr
                except (UnicodeDecodeError, LookupError):
                    continue
            return (
                result.returncode == 0,
                result.stdout.decode("latin1"),
                result.stderr.decode("latin1"),
            )
        except subprocess.TimeoutExpired:
            raise CommandTimeoutError("PowerShell 脚本执行超时")
        except Exception as e:
            raise NetworkError(f"PowerShell 脚本执行失败: {e}")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def get_adapters(self, physical_only: bool = True) -> List[NetworkAdapter]:
        """
        获取所有网络适配器（单条 PowerShell 调用，输出 JSON）

        关键设计：一次性拿到全部适配器 + IP + 网关 + DNS + DHCP，
        避免为每个适配器单独起 4 个 PowerShell 进程造成的进程风暴。

        Args:
            physical_only: 仅返回物理且已连接的适配器

        Returns:
            网络适配器列表
        """
        ps_script = """
$ErrorActionPreference = 'SilentlyContinue'
$result = @()
foreach ($a in Get-NetAdapter) {
    $cfg = Get-NetIPConfiguration -InterfaceIndex $a.ifIndex
    $v4 = Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4
    $dhcp = (Get-NetIPInterface -InterfaceIndex $a.ifIndex -AddressFamily IPv4).Dhcp
    $ips = @($v4 | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" }) -join ','
    $dns = @($cfg.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | ForEach-Object { $_.ServerAddresses }) -join ','
    $result += [PSCustomObject]@{
        Name        = $a.Name
        Status      = "$($a.Status)"
        Description = $a.InterfaceDescription
        Gateway     = $cfg.IPv4DefaultGateway.NextHop
        Dns         = $dns
        Dhcp        = "$dhcp"
        Ips         = $ips
    }
}
$result | ConvertTo-Json -Compress
"""

        success, stdout, stderr = self._run_ps_script(ps_script)
        if not success:
            raise NetworkError(f"获取适配器列表失败: {stderr}")

        import json
        stdout = stdout.strip()
        if not stdout:
            return []

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise NetworkError(f"解析适配器信息失败: {e}")

        # 单个对象时 ConvertTo-Json 返回 dict，统一成 list
        if isinstance(raw, dict):
            raw = [raw]

        adapters = []
        for item in raw:
            name = item.get("Name", "")
            description = item.get("Description", "")
            status_str = str(item.get("Status", "")).lower()

            if status_str == "up":
                status = AdapterStatus.CONNECTED
            elif status_str == "down":
                status = AdapterStatus.DISCONNECTED
            else:
                status = AdapterStatus.UNKNOWN

            # 过滤：仅物理 + 已连接
            if physical_only:
                if status != AdapterStatus.CONNECTED:
                    continue
                if not self._is_physical(name, description):
                    continue

            # 解析 IP 列表（"ip/prefix,ip/prefix"）
            ips_str = item.get("Ips", "") or ""
            gateway = item.get("Gateway") or None

            ip_entries = []
            for entry in ips_str.split(","):
                entry = entry.strip()
                if "/" not in entry:
                    continue
                ip, _, prefix = entry.partition("/")
                if self._validate_ip(ip):
                    mask = self._prefix_to_subnet_mask(int(prefix)) if prefix.isdigit() else "255.255.255.0"
                    ip_entries.append((ip, mask))

            # 主 IP：优先取与网关同网段的；否则取第一个
            ip_address = ""
            subnet_mask = ""
            if ip_entries:
                ip_address, subnet_mask = ip_entries[0]
                if gateway:
                    for ip, mask in ip_entries:
                        if self._same_subnet(ip, gateway, mask):
                            ip_address, subnet_mask = ip, mask
                            break

            dns_str = item.get("Dns", "") or ""
            dns_servers = [d.strip() for d in dns_str.split(",") if self._validate_ip(d.strip())]

            is_dhcp = str(item.get("Dhcp", "")).lower() == "enabled"

            adapters.append(NetworkAdapter(
                name=name,
                status=status,
                ip_address=ip_address,
                subnet_mask=subnet_mask,
                default_gateway=gateway,
                dns_servers=dns_servers,
                is_dhcp=is_dhcp,
            ))

        return adapters

    def _same_subnet(self, ip1: str, ip2: str, mask: str) -> bool:
        """判断两个 IP 是否在同一子网"""
        try:
            def to_int(s):
                a, b, c, d = (int(x) for x in s.split("."))
                return (a << 24) | (b << 16) | (c << 8) | d
            m = to_int(mask)
            return (to_int(ip1) & m) == (to_int(ip2) & m)
        except (ValueError, AttributeError):
            return False

    def _prefix_to_subnet_mask(self, prefix: int) -> str:
        """
        将前缀长度转换为子网掩码

        Args:
            prefix: 前缀长度

        Returns:
            子网掩码
        """
        if prefix < 0 or prefix > 32:
            return "255.255.255.0"

        mask = (0xffffffff >> (32 - prefix)) << (32 - prefix)
        return f"{(mask >> 24) & 0xff}.{(mask >> 16) & 0xff}.{(mask >> 8) & 0xff}.{mask & 0xff}"

    def set_static_ip(
        self,
        adapter_name: str,
        ip_address: str,
        subnet_mask: str,
        default_gateway: Optional[str] = None,
        dns_servers: Optional[List[str]] = None
    ) -> bool:
        """
        设置静态 IP

        Args:
            adapter_name: 适配器名称
            ip_address: IP 地址
            subnet_mask: 子网掩码
            default_gateway: 默认网关（可选）
            dns_servers: DNS 服务器列表（可选）

        Returns:
            操作是否成功
        """
        # 验证 IP 地址格式
        if not self._validate_ip(ip_address):
            raise InvalidIPError(f"无效的 IP 地址: {ip_address}")

        if not self._validate_ip(subnet_mask):
            raise InvalidIPError(f"无效的子网掩码: {subnet_mask}")

        # 设置 IP 地址和子网掩码
        cmd = f'netsh interface ip set address "{adapter_name}" static {ip_address} {subnet_mask}'
        if default_gateway:
            cmd += f" {default_gateway}"

        success, stdout, stderr = self._run_command(cmd)
        if not success:
            raise NetworkError(f"设置 IP 地址失败: {stderr}")

        # 设置 DNS 服务器
        if dns_servers:
            for i, dns in enumerate(dns_servers):
                if i == 0:
                    cmd = f'netsh interface ip set dns "{adapter_name}" static {dns}'
                else:
                    cmd = f'netsh interface ip add dns "{adapter_name}" {dns} index={i + 1}'

                success, stdout, stderr = self._run_command(cmd)
                if not success:
                    raise NetworkError(f"设置 DNS 服务器失败: {stderr}")

        return True

    def add_secondary_ip(
        self,
        adapter_name: str,
        ip_address: str,
        subnet_mask: str
    ) -> bool:
        """
        添加额外的 IP 地址

        Args:
            adapter_name: 适配器名称
            ip_address: 要添加的 IP 地址
            subnet_mask: 子网掩码

        Returns:
            操作是否成功
        """
        # 验证 IP 地址格式
        if not self._validate_ip(ip_address):
            raise InvalidIPError(f"无效的 IP 地址: {ip_address}")

        if not self._validate_ip(subnet_mask):
            raise InvalidIPError(f"无效的子网掩码: {subnet_mask}")

        # 添加 IP 地址
        cmd = f'netsh interface ip add address "{adapter_name}" {ip_address} {subnet_mask}'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"添加 IP 地址失败: {stderr}")

        return True

    def remove_secondary_ip(
        self,
        adapter_name: str,
        ip_address: str
    ) -> bool:
        """
        移除额外的 IP 地址

        Args:
            adapter_name: 适配器名称
            ip_address: 要移除的 IP 地址

        Returns:
            操作是否成功
        """
        cmd = f'netsh interface ip delete address "{adapter_name}" {ip_address}'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"移除 IP 地址失败: {stderr}")

        return True

    def _validate_ip(self, ip: str) -> bool:
        """
        验证 IP 地址格式

        Args:
            ip: IP 地址

        Returns:
            是否有效
        """
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

    def get_all_ips(self, adapter_name: str) -> List[dict]:
        """
        获取指定适配器的所有 IP 地址

        Args:
            adapter_name: 适配器名称

        Returns:
            IP 地址列表
        """
        ips = []

        cmd = f'Get-NetIPAddress -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 | Select-Object IPAddress, PrefixLength'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            lines = stdout.strip().split('\n')
            for line in lines[2:]:  # 跳过标题行
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    prefix_length = parts[1]

                    if self._validate_ip(ip):
                        mask = "255.255.255.0"
                        if prefix_length.isdigit():
                            mask = self._prefix_to_subnet_mask(int(prefix_length))

                        ips.append({
                            "ip": ip,
                            "mask": mask,
                            "prefix": prefix_length
                        })

        return ips

    def set_dhcp(self, adapter_name: str) -> bool:
        """
        设置适配器为 DHCP 自动获取 IP

        Args:
            adapter_name: 适配器名称

        Returns:
            操作是否成功
        """
        # 设置 IP 为 DHCP
        cmd = f'netsh interface ip set address "{adapter_name}" dhcp'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"设置 DHCP 失败: {stderr}")

        # 设置 DNS 为 DHCP
        cmd = f'netsh interface ip set dns "{adapter_name}" dhcp'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"设置 DNS DHCP 失败: {stderr}")

        return True
