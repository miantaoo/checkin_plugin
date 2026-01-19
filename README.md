# checkin_plugin 项目文档

## 一、项目概述

一款基于 MaiCore 框架开发的 QQ 群自动打卡插件，核心功能为自动调用 napcat HTTP 接口获取已加入群列表，按配置时间每日执行一次批量打卡操作。插件无需手动触发，支持时区自定义配置和异常自动重试，可大幅简化多群打卡的重复操作流程。

## 二、项目基础信息

|信息类别|具体内容|
|---|---|
|项目作者|miantaoo|
|当前版本|1.0.10|
|开源许可证|GPL-3.0（GNU General Public License v3.0）|
|代码仓库地址|[https://github.com/miantaoo/checkin_plugin](https://github.com/miantaoo/checkin_plugin)|
|兼容框架|MaiCore（最低兼容版本：1.10.0）|
## 三、核心特性

1. **自动配置生成**：插件首次启动时，自动在插件目录生成 `config.toml` 配置文件，无需手动创建。

2. **每日定时打卡**：支持自定义打卡时间（格式：HH:MM:SS）和时区，每日仅执行一次批量打卡。

3. **自动获取群列表**：调用 napcat 的 `/get_group_list` 接口，自动抓取已加入的所有群号，无需手动维护群列表。

4. **批量打卡执行**：遍历获取到的群列表，逐个调用 napcat 的 `/set_group_sign` 接口完成打卡，高效避免重复操作。

5. **完善异常处理**：包含 napcat 服务连接异常、接口响应异常、配置格式错误等多场景捕获逻辑，异常后自动重试。

## 四、环境依赖要求

### 1. 基础环境

- Python 版本：≥3.8（推荐 3.10 及以上版本，兼容性更优）

- 框架环境：已搭建完成的 MaiCore 框架（版本 ≥1.10.0）

### 2. Napcat

- 已部署并正常启动的 napcat 服务（需开启 HTTP 接口，默认端口 9999）

- 网络环境：插件所在服务器可正常访问 napcat 服务地址及端口（无防火墙拦截）

- <img width="519" height="696" alt="image" src="https://github.com/user-attachments/assets/c3ede91e-d677-4abe-a6ad-03c109ccdfb3" />

## 五、安装部署步骤

### 1. 克隆代码仓库

```Bash

# 在plugin文件夹克隆项目到本地
git clone https://github.com/miantaoo/checkin_plugin.git

```
## 六、使用操作指南

### 1. 首次运行

插件启动后，会自动在 `plugins/checkin_plugin/` 目录下生成默认配置文件 `config.toml`，并读取默认配置打印初始化日志。

### 2. 配置修改

编辑 `config.toml` 文件，根据实际需求调整以下核心配置项（配置说明详见第七节），保存文件即可。

### 3. 重启生效

修改配置后，需重启 MaiCore 框架，插件会加载新配置并按指定时间执行打卡。

## 七、配置文件说明

### 1. 配置文件路径

`plugins/checkin_plugin/config.toml`

### 2. 配置项详情

```TOML

# 核心打卡配置（每日打卡时间及时区）
[sign_core]
# 每日自动打卡时间，格式必须严格遵循 HH:MM:SS（例：09:30:00）
auto_checkin_time = "08:00:00"
# 时区设置：东八区填 8（北京时间），东九区填 9，合法范围 -12~14
timezone = 8

# napcat 服务配置（接口连接信息）
[napcat_service]
# napcat 服务地址（本地部署默认填 127.0.0.1）
host = "127.0.0.1"
# napcat HTTP 服务端口（默认 9999，需与 napcat 实际配置一致）
port = 9999
# napcat 接口认证 Token（无认证则留空，有认证需填写完整 Token）
token = ""
```

### 3. 配置注意事项

- `auto_checkin_time`：格式错误会导致配置验证失败，插件无法启动定时打卡（例如 `08:00` 需改为 `08:00:00`）。

- `napcat_service.port`：端口号必须为 1~65535 之间的整数，需与 napcat 服务的 HTTP 端口严格一致。

- `token`：若 napcat 配置了接口认证，未填写 Token 会导致接口调用失败，打卡无响应。

## 八、运行日志示例

```Plain Text

[INFO] 配置文件已存在：plugins/checkin_plugin/config.toml，跳过默认配置生成
[INFO] ===== 打卡配置读取完成=====
[INFO] 核心配置：自动打卡时间=08:00:00，时区=东8区
[INFO] napcat配置：HTTP地址=127.0.0.1:9999
[INFO] 配置完整性验证：通过
[INFO] 当前时区时间：2026-01-19 07:30:00
[INFO] 下次打卡时间：2026-01-19 08:00:00（每日仅执行一次）
[INFO] 需等待时长：1800.00 秒（约 0.50 小时）
...
[INFO] ===== 开始执行每日一次批量打卡流程 =====
[INFO] 获取群列表成功：成功获取群列表，共2个可打卡群（群号列表：123456789,987654321）
[INFO] 开始处理群123456789打卡...
[INFO] 群123456789打卡成功：群打卡成功
[INFO] 开始处理群987654321打卡...
[INFO] 群987654321打卡成功：群打卡成功
[INFO] ===== 每日一次批量打卡流程结束 =====
[INFO] 汇总结果：共2个群，成功2个，失败0个
```

## 九、许可证说明

本项目采用 GPL-3.0 开源许可证，详细条款可查看项目根目录的 [LICENSE](https://github.com/miantaoo/checkin_plugin/blob/main/LICENSE) 文件。


> （注：文档部分内容可能由 AI 生成）
