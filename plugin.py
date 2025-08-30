from typing import List, Tuple, Type, Optional
import io
import sys
import re

from src.plugin_system import BasePlugin, register_plugin, ComponentInfo, BaseCommand
from src.plugin_system.apis import llm_api

# 安全的代码执行函数
async def safe_execute_code(code: str) -> Tuple[bool, str]:
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    redirected_error = io.StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_error

    success = False
    result = ""

    # 限制可用的内置函数和模块，防止恶意操作
    safe_builtins = {
        'print': print,
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'range': range,
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
        'type': type,
        'isinstance': isinstance,
        'issubclass': issubclass,
        'Exception': Exception,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'KeyError': KeyError,
        'IndexError': IndexError,
        'AttributeError': AttributeError,
        'NameError': NameError,
        'SyntaxError': SyntaxError,
        'ZeroDivisionError': ZeroDivisionError,
    }

    # 限制全局和局部变量
    restricted_globals = {"__builtins__": safe_builtins}
    restricted_locals = {}

    try:
        exec(code, restricted_globals, restricted_locals)
        success = True
        result = redirected_output.getvalue()
    except Exception as e:
        result = f"代码执行错误: {e}\n{redirected_error.getvalue()}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return success, result.strip()

class CodeGeneratorCommand(BaseCommand):
    command_name = "generate_code"
    command_description = "让机器人生成并执行Python代码"
    command_pattern = r"^/generate_code\s+(?P<prompt>.+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        prompt = self.matched_groups.get("prompt")
        if not prompt:
            await self.send_text("请提供一个代码生成提示词。例如：/generate_code 编写一个计算斐波那契数列的函数")
            return False, None, False

        await self.send_text(f"正在根据您的提示词生成代码：{prompt}")

        # 调用LLM生成代码
        # 这里需要根据实际LLM API的返回格式进行调整
        # 假设llm_api.generate_with_model返回 (success, generated_content, inference_process, model_name)
        # 并且generated_content中包含Python代码
        success, generated_code, _, _ = await llm_api.generate_with_model(
            prompt=f"请生成一段Python代码来完成以下任务：{prompt}\n\n请只返回代码，不要包含任何解释性文字或Markdown格式。",
            model_config=llm_api.get_available_models().get("qwen2.5-coder-7b"), # 假设有一个默认模型
            request_type="plugin.generate_code"
        )

        if not success:
            await self.send_text("代码生成失败，请稍后再试。")
            return False, None, False

        # 提取代码块（如果LLM返回了Markdown格式）
        code_match = re.search(r"```python\n(.*?)```", generated_code, re.DOTALL)
        if code_match:
            code_to_execute = code_match.group(1).strip()
        else:
            code_to_execute = generated_code.strip()

        if not code_to_execute:
            await self.send_text("LLM未能生成有效的Python代码。")
            return False, None, False

        await self.send_text(f"生成的代码：\n```python\n{code_to_execute}\n```\n正在执行...")

        # 安全执行生成的代码
        exec_success, exec_result = await safe_execute_code(code_to_execute)

        if exec_success:
            response_message = f"代码执行成功！\n输出：\n```\n{exec_result}\n```"
        else:
            response_message = f"代码执行失败！\n错误：\n```\n{exec_result}\n```"
        
        await self.send_text(response_message)
        return True, None, False

@register_plugin
class CodeGenerationPlugin(BasePlugin):
    plugin_name = "code_generation_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = []
    config_file_name = "config.toml"
    config_schema = {}

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (CodeGeneratorCommand.get_command_info(), CodeGeneratorCommand),
        ]


