# Subnet Link Weaver - 项目指南

## 项目概述
Subnet Link Weaver 是一个 Windows 桌面应用程序，用于帮助多台电脑在同一个局域网下配置固定 IP（如 192.168.88.X 网段），实现双向互相访问。

## 技术栈
- **语言**: Python 3.10+
- **GUI**: PyQt6 / tkinter (备选)
- **打包**: PyInstaller
- **版本控制**: Git
- **包管理**: uv

## 核心功能
1. **网络适配器检测**: 自动检测当前系统的所有网络适配器及其 IP 配置
2. **静态 IP 配置**: 自动将动态 IP 转换为静态 IP
3. **多 IP 挂载**: 在同一网卡上添加额外的 IP 地址（如 192.168.88.X）
4. **防火墙管理**: 一键关闭/开启 Windows Defender 阁火墙
5. **连通性测试**: 使用 ping 命令测试网络连通性
6. **配置导出/导入**: 保存和加载配置文件

## 架构约束
- 仅支持 Windows 10/11 操作系统
- 需要管理员权限运行
- 使用 `netsh` 命令进行网络配置
- 使用 PowerShell 命令管理防火墙

## 项目结构
```
subnet_link_weaver/
├── src/
│   ├── main.py              # 入口点
│   ├── app.py               # 主应用程序
│   ├── gui/                 # GUI 组件
│   │   ├── main_window.py   # 主窗口
│   │   ├── network_panel.py # 网络配置面板
│   │   └── status_bar.py    # 状态栏
│   ├── core/                # 核心逻辑
│   │   ├── network.py       # 网络检测与配置
│   │   ├── firewall.py      # 防火墙管理
│   │   └── ping.py          # 连通性测试
│   └── utils/               # 工具函数
│       ├── config.py        # 配置管理
│       └── logger.py        # 日志记录
├── assets/
│   └── icon.svg             # 应用图标
├── dist/                    # PyInstaller 打包输出
├── CLAUDE.md                # 本文件
└── requirements.txt         # 依赖
```

## 开发规范
- 所有网络操作需要管理员权限
- GUI 操作需要在主线程，网络操作在子线程
- 使用信号槽机制进行线程间通信
- 错误处理需要用户友好的提示信息

## 构建命令
```bash
# 使用 uv 安装依赖
uv pip install -r requirements.txt

# 运行应用程序
uv run python src/main.py

# 使用 PyInstaller 打包
uv run pyinstaller --onefile --windowed --icon=assets/icon.ico src/main.py
```
