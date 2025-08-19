"""
配置管理模块
处理环境变量和配置参数
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    """配置类"""
    # API密钥
    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    
    # 模型配置
    default_llm_provider: str = "deepseek"  # deepseek 或 openai
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"
    
    # 搜索配置
    max_search_results: int = 3
    search_timeout: int = 240
    max_content_length: int = 20000
    
    # Agent配置
    max_reflections: int = 2
    max_paragraphs: int = 5
    
    # 输出配置
    output_dir: str = "reports"
    save_intermediate_states: bool = True
    
    def validate(self) -> bool:
        """验证配置"""
        # 检查必需的API密钥
        if self.default_llm_provider == "deepseek" and not self.deepseek_api_key:
            print("错误: DeepSeek API Key未设置")
            return False
        
        if self.default_llm_provider == "openai" and not self.openai_api_key:
            print("错误: OpenAI API Key未设置")
            return False
        
        if not self.tavily_api_key:
            print("错误: Tavily API Key未设置")
            return False
        
        return True
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量创建配置"""
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "deepseek"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "3")),
            search_timeout=int(os.getenv("SEARCH_TIMEOUT", "240")),
            max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", "20000")),
            max_reflections=int(os.getenv("MAX_REFLECTIONS", "2")),
            max_paragraphs=int(os.getenv("MAX_PARAGRAPHS", "5")),
            output_dir=os.getenv("OUTPUT_DIR", "reports"),
            save_intermediate_states=os.getenv("SAVE_INTERMEDIATE_STATES", "true").lower() == "true"
        )


def load_config(env_file: Optional[str] = None) -> Config:
    """
    加载配置
    
    Args:
        env_file: 环境变量文件路径，如果不指定则使用默认路径
        
    Returns:
        配置对象
    """
    # 加载环境变量文件
    if env_file:
        load_dotenv(env_file)
    else:
        # 尝试加载常见的环境变量文件
        for env_path in [".env", "config.env"]:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                print(f"已加载环境变量文件: {env_path}")
                break
    
    # 创建配置对象
    config = Config.from_env()
    
    # 验证配置
    if not config.validate():
        raise ValueError("配置验证失败，请检查必需的环境变量")
    
    return config


def print_config(config: Config):
    """打印配置信息（隐藏敏感信息）"""
    print("\n=== 当前配置 ===")
    print(f"LLM提供商: {config.default_llm_provider}")
    print(f"DeepSeek模型: {config.deepseek_model}")
    print(f"OpenAI模型: {config.openai_model}")
    print(f"最大搜索结果数: {config.max_search_results}")
    print(f"搜索超时: {config.search_timeout}秒")
    print(f"最大内容长度: {config.max_content_length}")
    print(f"最大反思次数: {config.max_reflections}")
    print(f"最大段落数: {config.max_paragraphs}")
    print(f"输出目录: {config.output_dir}")
    print(f"保存中间状态: {config.save_intermediate_states}")
    
    # 显示API密钥状态（不显示实际密钥）
    print(f"DeepSeek API Key: {'已设置' if config.deepseek_api_key else '未设置'}")
    print(f"OpenAI API Key: {'已设置' if config.openai_api_key else '未设置'}")
    print(f"Tavily API Key: {'已设置' if config.tavily_api_key else '未设置'}")
    print("==================\n")
