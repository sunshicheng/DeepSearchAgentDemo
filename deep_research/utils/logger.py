"""
Author : sunshicheng
DateTime : 2021/1/13.10:57 上午
FileName : logger.py
Desc: 定义日志相关内容

"""

import json
import logging
import logging.handlers
import time
from functools import lru_cache
from pathlib import Path
from uuid import uuid4


# 对整条日志进行着色
class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',  # 蓝色
        # 'INFO': '\033[92m',  # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',  # 红色
        'CRITICAL': '\033[1;91m',  # 粗体红色
        'RESET': '\033[0m'  # 重置颜色
    }

    def __init__(self, fmt, use_color=True):
        super().__init__(fmt)
        self.use_color = use_color

    def format(self, record):
        # 保存原始消息
        original_message = record.msg

        # 特殊处理字典类型的消息，防止二次序列化
        if isinstance(record.msg, dict):
            # 先将原始的字典保存下来
            record.dict_message = record.msg
            # 将msg设置为占位符，避免被格式化
            record.msg = "{dict_placeholder}"

        # 进行标准格式化
        formatted_message = super().format(record)

        # 如果是字典消息，替换占位符
        if hasattr(record, 'dict_message'):
            # 替换占位符为实际的字典
            formatted_message = formatted_message.replace('"{dict_placeholder}"',
                                                          json.dumps(record.dict_message, ensure_ascii=False))

        # 恢复原始消息
        record.msg = original_message

        # 如果启用了颜色，且日志级别有对应的颜色，则给整条消息添加颜色
        if self.use_color and record.levelname in self.COLORS:
            formatted_message = f"{self.COLORS[record.levelname]}{formatted_message}{self.COLORS['RESET']}"

        return formatted_message


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_dict = {
            "time": f"[{self.formatTime(record, self.datefmt)}]",
            "level": f"[{record.levelname}]",
            "file": f"[{getattr(record, 'real_filename', 'unknown')}]",
            "line": f"[{getattr(record, 'real_lineno', 0)}]",
            "local_trace": getattr(record, "local_trace", ""),
            "category": getattr(record, "category", "")
        }

        # 特殊处理 message 字段
        if isinstance(record.msg, dict):
            log_dict["message"] = record.msg  # 如果已经是字典，直接使用
        else:
            log_dict["message"] = record.getMessage()  # 否则按常规方式处理

        return json.dumps(log_dict, ensure_ascii=False)


@lru_cache(maxsize=1)
def get_logger(level='info'):
    """
    获取日志记录器实例
    :param level: 日志级别，默认为 info
    :return: 日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger('DeepSearchAgentDemo')

    # 如果已经有处理器，说明已经初始化过了
    if logger.handlers:
        return logger

    # 设置输出的等级
    level_relations = {
        'noset': logging.NOTSET,
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }

    # 设置日志级别
    logger_level = level_relations.get(level.lower(), logging.INFO)
    logger.setLevel(logger_level)

    # 生成 trace_id
    global trace_id
    trace_id = (str(int(time.time())) + str(uuid4())).replace('-', '')[:32]

    # 确定日志路径
    base_dir = Path(__file__).parent.parent.parent
    log_dir = base_dir / 'logs'
    log_dir.mkdir(exist_ok=True)  # 创建日志目录（如果不存在）

    # 日志文件名
    log_file = log_dir / f'deep_research.log'

    # 日志输出格式
    log_format = {
        "time": "[%(asctime)s]",
        "level": "[%(levelname)s]",
        "file": "[%(real_filename)s]",  # 使用我们自定义的属性
        "line": "[%(real_lineno)d]",  # 使用我们自定义的属性
        "message": "%(message)s",
        "local_trace": trace_id,
        "category": "%(category)s"  # 添加 category 字段
    }

    # 文件日志使用普通格式（无颜色）
    # file_formatter = logging.Formatter(json.dumps(log_format, ensure_ascii=False))
    file_formatter = JSONFormatter()

    # 控制台日志使用彩色格式
    console_formatter = ColorFormatter(json.dumps(log_format, ensure_ascii=False))

    # 创建 FileHandler，启用日志轮转
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',  # 每天午夜切换日志文件
        interval=1,  # 间隔为1天
        backupCount=7,  # 保留7天的日志
    )
    file_handler.setLevel(logger_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 创建 StreamHandler，输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logger_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def get_trace_id():
    global trace_id
    # 如果全局 trace_id 不存在，初始化一个
    if not globals().get('trace_id'):
        trace_id = (str(int(time.time())) + str(uuid4())).replace('-', '')[:32]
    return trace_id


# 创建一个支持 category 的 LoggerAdapter 类
class CategoryLogger:
    def __init__(self, logger):
        self.logger = logger

    def _process_message(self, msg):
        """预处理 message，如果是 dict 类型则不需要再次序列化"""
        if isinstance(msg, dict):
            return msg  # 直接返回字典，避免二次序列化
        return msg

    def _get_caller_info(self):
        """获取调用者的文件名和行号"""
        import inspect
        # 0是当前函数，1是调用当前函数的函数，2是调用调用函数的函数（即实际的调用者）
        frame = inspect.currentframe().f_back.f_back
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        # 只获取文件名，不包括路径
        filename = Path(filename).name
        return filename, lineno

    def debug(self, msg, category="", *args, **kwargs):
        filename, lineno = self._get_caller_info()
        extra = kwargs.get("extra", {})
        extra["category"] = category
        extra["real_filename"] = filename
        extra["real_lineno"] = lineno
        extra["local_trace"] = get_trace_id()
        processed_msg = self._process_message(msg)
        kwargs["extra"] = extra
        self.logger.debug(processed_msg, *args, **kwargs)

    def info(self, msg, category="", *args, **kwargs):
        filename, lineno = self._get_caller_info()
        extra = kwargs.get("extra", {})
        extra["category"] = category
        extra["real_filename"] = filename
        extra["real_lineno"] = lineno
        extra["local_trace"] = get_trace_id()
        processed_msg = self._process_message(msg)
        kwargs["extra"] = extra
        self.logger.info(processed_msg, *args, **kwargs)

    def warning(self, msg, category="", *args, **kwargs):
        filename, lineno = self._get_caller_info()
        extra = kwargs.get("extra", {})
        extra["category"] = category
        extra["real_filename"] = filename
        extra["real_lineno"] = lineno
        extra["local_trace"] = get_trace_id()
        processed_msg = self._process_message(msg)
        kwargs["extra"] = extra
        self.logger.warning(processed_msg, *args, **kwargs)

    def error(self, msg, category="", *args, **kwargs):
        filename, lineno = self._get_caller_info()
        extra = kwargs.get("extra", {})
        extra["category"] = category
        extra["real_filename"] = filename
        extra["real_lineno"] = lineno
        extra["local_trace"] = get_trace_id()
        processed_msg = self._process_message(msg)
        kwargs["extra"] = extra
        self.logger.error(processed_msg, *args, **kwargs)

    def critical(self, msg, category="", *args, **kwargs):
        filename, lineno = self._get_caller_info()
        extra = kwargs.get("extra", {})
        extra["category"] = category
        extra["real_filename"] = filename
        extra["real_lineno"] = lineno
        extra["local_trace"] = get_trace_id()
        processed_msg = self._process_message(msg)
        kwargs["extra"] = extra
        self.logger.critical(processed_msg, *args, **kwargs)


# 默认实例化一个 logger
_base_logger = get_logger()
logger = CategoryLogger(_base_logger)
