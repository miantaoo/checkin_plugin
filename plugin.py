import asyncio
import json
import traceback
import os
from typing import Tuple, List, Optional
from datetime import datetime, timedelta, timezone
import httpx

try:
    import tomllib
except ImportError:
    import tomli as tomllib
try:
    import tomli_w
except ImportError:
    raise ImportError("请安装tomli-w库：pip install tomli-w")

from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ConfigField
)

# 初始化日志
logger = get_logger("checkin_plugin")

# ========== 调用napcat的/get_group_list接口获取所有群号 ==========
async def get_napcat_group_list(
    napcat_host: str,
    napcat_port: int,
    napcat_token: str
) -> Tuple[bool, Optional[List[str]], str]:
    """
    调用napcat的/get_group_list接口获取所有已加入群号
    :param napcat_host: napcat服务地址（从配置读取）
    :param napcat_port: napcat服务端口（从配置读取）
    :param napcat_token: napcat服务认证Token（从配置读取）
    :return: (是否成功, 群号列表/None, 结果信息/失败原因)
    """
    # 1. 构建/get_group_list接口信息
    base_url = f"http://{napcat_host}:{napcat_port}"
    full_url = f"{base_url}/get_group_list"
    headers = {"Content-Type": "application/json"}
    
    # 2. 添加napcat Token认证
    if napcat_token:
        headers["Authorization"] = napcat_token

    # 3. 构建请求参数
    payload = {
        "no_cache": False
    }
    logger.debug(f"发送获取群列表请求: {json.dumps(payload, ensure_ascii=False)}")

    try:
        # 4. 异步调用napcat接口（HTTP请求，超时10秒）
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url=full_url,
                json=payload,
                headers=headers
            )
        # 5. 解析napcat响应
        logger.debug(f"获取群列表响应状态: {resp.status_code}, 内容: {resp.text}")
        
        # 非200状态码直接判定失败
        if resp.status_code != 200:
            return False, None, f"napcat服务返回异常状态码: {resp.status_code}"
        
        # 解析JSON响应
        resp_data = resp.json()
        if resp_data.get("status") == "ok" or resp_data.get("retcode") == 0:
            # 提取群列表中的group_id
            group_data_list = resp_data.get("data", [])
            group_id_list = []
            for group_info in group_data_list:
                group_id = group_info.get("group_id")  # 从群信息对象中提取群号
                if group_id:
                    group_id_list.append(str(group_id))  # 统一转为字符串，适配打卡接口
            
            msg = f"成功获取群列表，共{len(group_id_list)}个可打卡群"
            return True, group_id_list, msg
        else:
            fail_msg = resp_data.get("message", "获取群列表失败，无具体原因")
            return False, None, fail_msg
            
    except httpx.ConnectError:
        return False, None, "无法连接到napcat服务，请检查地址/端口是否正确（确认开启HTTP服务）"
    except json.JSONDecodeError:
        return False, None, "napcat服务返回非JSON格式响应，接口异常"
    except Exception as e:
        logger.error(f"获取群列表异常：{traceback.format_exc()}")
        return False, None, f"获取群列表过程异常：{str(e)}"

# ========== 调用napcat的/set_group_sign接口完成单个群打卡 ==========
async def send_napcat_checkin(
    napcat_host: str,
    napcat_port: int,
    napcat_token: str,
    group_id: str
) -> Tuple[bool, str]:
    """
    调用napcat的/set_group_sign接口完成单个群打卡（HTTP协议，仅传group_id）
    :param napcat_host: napcat服务地址（从配置读取）
    :param napcat_port: napcat服务端口（从配置读取）
    :param napcat_token: napcat服务认证Token（从配置读取）
    :param group_id: 需打卡的群号（从/get_group_list接口获取）
    :return: (是否成功, 结果信息/失败原因)
    """
    # 1. 构建napcat的set_group_sign接口信息
    base_url = f"http://{napcat_host}:{napcat_port}"
    full_url = f"{base_url}/set_group_sign"
    headers = {"Content-Type": "application/json"}
    
    # 2. 添加napcat Token认证（如有，从配置读取）
    if napcat_token:
        headers["Authorization"] = napcat_token

    # 3. 构建请求参数
    payload = {
        "group_id": group_id
    }
    logger.debug(f"发送群{group_id}打卡请求: {json.dumps(payload, ensure_ascii=False)}")

    try:
        # 4. 异步调用napcat接口（HTTP请求，超时10秒）
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url=full_url,
                json=payload,
                headers=headers
            )
        # 5. 解析napcat响应
        logger.debug(f"群{group_id}打卡响应状态: {resp.status_code}, 内容: {resp.text}")
        
        # 非200状态码直接判定失败
        if resp.status_code != 200:
            return False, f"napcat服务返回异常状态码: {resp.status_code}"
        
        # 解析JSON响应
        resp_data = resp.json()
        if resp_data.get("status") == "success" or resp_data.get("code") == 0 or resp_data.get("retcode") == 0:
            msg = resp_data.get("message", "群打卡成功")
            return True, msg
        else:
            fail_msg = resp_data.get("message", "群打卡失败，无具体原因")
            return False, fail_msg
            
    except httpx.ConnectError:
        return False, "无法连接到napcat服务，请检查地址/端口是否正确"
    except json.JSONDecodeError:
        return False, "napcat服务返回非JSON格式响应，接口异常"
    except Exception as e:
        logger.error(f"群{group_id}打卡请求异常：{traceback.format_exc()}")
        return False, f"打卡过程异常：{str(e)}"

# ========== 插件核心类（修复抽象方法实现 + 每日仅一次打卡） ==========
@register_plugin
class CheckinPlugin(BasePlugin):
    """QQ群打卡插件（每日仅执行一次 + 配置自动生成）"""

    # 插件基本信息（关键：补充python_dependencies，满足抽象类实例化要求）
    plugin_name: str = "qq_checkin_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 保留空列表，不做插件依赖验证
    python_dependencies: List[str] = []  # 修复：实现抽象属性，设为空列表（不做Python依赖验证）
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {
        "sign_core": "核心打卡配置（时间+时区，每日仅执行一次）",
        "napcat_service": "napcat服务配置（HTTP协议，get_group_list/set_group_sign接口）",
    }

    # 配置Schema定义
    config_schema: dict = {
        "sign_core": {
            "auto_checkin_time": ConfigField(
                type=str,
                default="08:00:00",
                description="每日自动打卡时间，格式：HH:MM:SS（例如 09:30:00），每日仅执行一次"
            ),
            "timezone": ConfigField(
                type=int,
                default=8,
                description="时区设置，东八区填8（对应北京时间），东九区填9"
            )
        },
        "napcat_service": {
            "host": ConfigField(
                type=str,
                default="127.0.0.1",
                description="napcat服务地址"
            ),
            "port": ConfigField(
                type=int,
                default=9999,
                description="napcat服务端口（HTTP默认9999，可根据实际修改）"
            ),
            "token": ConfigField(
                type=str,
                default="",
                description="napcat服务认证Token（无认证则留空）"
            )
        }
    }

    def __init__(self, plugin_dir: str = None):
        """插件初始化（生成配置+读取配置+启动每日一次定时打卡）"""
        # 传递plugin_dir参数给父类BasePlugin
        super().__init__(plugin_dir=plugin_dir)
        # 1. 自动生成默认配置文件（若不存在）
        self._generate_default_config_if_not_exist()
        # 2. 读取并验证配置
        self._load_and_verify_config()
        # 3. 启动每日一次定时打卡任务
        asyncio.create_task(self._start_daily_checkin())

    def _generate_default_config_if_not_exist(self):
        """自动生成默认配置文件（若配置文件不存在，无需依赖验证）"""
        # 拼接配置文件完整路径
        config_path = os.path.join(self.plugin_dir, self.config_file_name) if self.plugin_dir else self.config_file_name
        # 若配置文件已存在，跳过生成
        if os.path.exists(config_path):
            logger.info(f"配置文件已存在：{config_path}，跳过默认配置生成")
            return
        
        # 构建默认配置字典（与config_schema默认值一致）
        default_config = {
            "sign_core": {
                "auto_checkin_time": self.config_schema["sign_core"]["auto_checkin_time"].default,
                "timezone": self.config_schema["sign_core"]["timezone"].default
            },
            "napcat_service": {
                "host": self.config_schema["napcat_service"]["host"].default,
                "port": self.config_schema["napcat_service"]["port"].default,
                "token": self.config_schema["napcat_service"]["token"].default
            }
        }
        
        # 写入默认配置到config.toml
        try:
            with open(config_path, "wb") as f:
                tomli_w.dump(default_config, f)
            logger.info(f"默认配置文件生成成功：{config_path}")
        except Exception as e:
            logger.error(f"生成默认配置文件失败：{str(e)}", exc_info=True)
            raise RuntimeError(f"配置文件生成失败：{str(e)}")

    def _load_and_verify_config(self):
        """读取并验证配置文件（仅验证核心功能配置，不验证依赖）"""
        # 1. 读取核心打卡配置
        self.auto_checkin_time = self.get_config("sign_core.auto_checkin_time")
        self.timezone = self.get_config("sign_core.timezone")

        # 2. 读取napcat服务配置
        self.napcat_host = self.get_config("napcat_service.host")
        self.napcat_port = self.get_config("napcat_service.port")
        self.napcat_token = self.get_config("napcat_service.token", "")

        # 3. 验证配置完整性
        config_valid = True
        error_msg = []
        if not self.napcat_host:
            error_msg.append("napcat服务地址为空")
            config_valid = False
        if not isinstance(self.napcat_port, int) or self.napcat_port <= 0 or self.napcat_port > 65535:
            error_msg.append("napcat服务端口无效（需为1-65535的整数）")
            config_valid = False
        # 验证时间格式（HH:MM:SS），确保每日打卡时间有效
        try:
            datetime.strptime(self.auto_checkin_time, "%H:%M:%S")
        except ValueError:
            error_msg.append(f"自动打卡时间格式错误（当前：{self.auto_checkin_time}，需为HH:MM:SS）")
            config_valid = False

        # 4. 打印配置信息
        logger.info(f"===== 打卡配置读取完成（每日仅执行一次） =====")
        logger.info(f"核心配置：自动打卡时间={self.auto_checkin_time}，时区=东{self.timezone}区")
        logger.info(f"napcat配置：HTTP地址={self.napcat_host}:{self.napcat_port}")
        logger.info(f"配置完整性验证：{'通过' if config_valid else '失败（' + '，'.join(error_msg) + '）'}")

        # 保存配置验证结果
        self.config_valid = config_valid

    def _calculate_next_checkin_seconds(self) -> float:
        """计算距离下一次打卡（次日同时间）的休眠秒数，确保每日仅一次"""
        # 1. 构建目标时区（东N区 = UTC+N）
        target_tz = timezone(timedelta(hours=self.timezone))
        # 2. 获取当前时间（目标时区）
        now = datetime.now(target_tz)
        # 3. 解析配置的目标时间（HH:MM:SS）
        target_h, target_m, target_s = map(int, self.auto_checkin_time.split(":"))
        # 4. 构建今日目标时间
        target_time = now.replace(hour=target_h, minute=target_m, second=target_s, microsecond=0)
        # 5. 若当前时间已过今日目标时间，顺延至次日
        if now > target_time:
            target_time += timedelta(days=1)
        # 6. 计算时间差（秒），此差值即为距离下一次打卡的时长
        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"当前时区时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"下次打卡时间：{target_time.strftime('%Y-%m-%d %H:%M:%S')}（每日仅执行一次）")
        logger.info(f"需等待时长：{sleep_seconds:.2f} 秒（约 {sleep_seconds/3600:.2f} 小时）")
        return sleep_seconds

    async def _start_daily_checkin(self):
        """启动每日一次打卡任务"""
        if not self.config_valid:
            logger.error("配置验证失败，每日打卡任务未启动")
            return
        
        # 无限循环：每日按配置时间执行一次打卡，执行完成后等待次日同时间
        while True:
            try:
                # 1. 计算距离下一次打卡的休眠秒数（指向今日/次日目标时间）
                sleep_seconds = self._calculate_next_checkin_seconds()
                # 2. 休眠至目标打卡时间
                await asyncio.sleep(sleep_seconds)
                # 3. 执行单次批量打卡（每日仅这一次）
                await self._execute_batch_checkin()
                # 4. 打卡完成后，直接进入下一轮循环（计算次日打卡时间，确保一天一次）
                # 无额外休眠，避免累计误差，下一轮会自动计算次日同时间
            except Exception as e:
                logger.error(f"每日打卡任务异常：{str(e)}", exc_info=True)
                # 异常后等待60秒重试，避免无限报错，且不影响后续每日打卡逻辑
                await asyncio.sleep(60)

    async def _execute_batch_checkin(self):
        """执行单次批量打卡"""
        logger.info("===== 开始执行每日一次批量打卡流程 =====")
        
        # 获取所有群号列表
        group_list_success, group_id_list, group_list_msg = await get_napcat_group_list(
            napcat_host=self.napcat_host,
            napcat_port=self.napcat_port,
            napcat_token=self.napcat_token
        )
        if not group_list_success or not group_id_list:
            logger.error(f"每日打卡终止：{group_list_msg}")
            return
        logger.info(f"获取群列表成功：{group_list_msg}（群号列表：{','.join(group_id_list)}）")
        
        # 遍历群号列表，逐个执行打卡
        total_group = len(group_id_list)
        success_count = 0
        fail_count = 0
        fail_group_log = []

        for group_id in group_id_list:
            logger.info(f"开始处理群{group_id}打卡...")
            checkin_success, checkin_msg = await send_napcat_checkin(
                napcat_host=self.napcat_host,
                napcat_port=self.napcat_port,
                napcat_token=self.napcat_token,
                group_id=group_id
            )
            
            if checkin_success:
                success_count += 1
                logger.info(f"群{group_id}打卡成功：{checkin_msg}")
            else:
                fail_count += 1
                fail_group_log.append(f"群{group_id}：{checkin_msg}")
                logger.warning(f"群{group_id}打卡失败：{checkin_msg}")
            
            # 间隔0.1秒，避免请求过快触发napcat限流
            await asyncio.sleep(0.1)
        
        # 打印每日打卡汇总结果
        logger.info(f"===== 每日一次批量打卡流程结束 =====")
        logger.info(f"汇总结果：共{total_group}个群，成功{success_count}个，失败{fail_count}个")
        if fail_group_log:
            logger.warning(f"失败详情：{'; '.join(fail_group_log)}")

    def get_plugin_components(self):
        return []
