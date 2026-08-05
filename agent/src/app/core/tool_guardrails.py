import re
import logging
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# List of dangerous/destructive tool names requiring Human-in-the-loop (HITL) or strict block
DESTRUCTIVE_TOOLS = {
    "delete_user_account",
    "drop_database",
    "execute_system_command",
    "delete_file",
    "purge_database_logs"
}

# Dangerous patterns inside tool string arguments (SQL Injection, Command Injection)
DANGEROUS_ARG_PATTERNS = [
    r";\s*DROP\s+TABLE",
    r";\s*DELETE\s+FROM",
    r";\s*TRUNCATE",
    r"&&\s*rm\s+-rf",
    r"\|\s*bash",
    r"__import__\s*\(",
    r"eval\s*\("
]


class ToolSecurityResult(BaseModel):
    is_allowed: bool
    requires_hitl: bool = False
    sanitized_args: Dict[str, Any]
    block_reason: Optional[str] = None


def validate_tool_execution(tool_name: str, tool_args: Dict[str, Any]) -> ToolSecurityResult:
    """
    Action Rail: Inspects, validates, and restricts LLM tool calls BEFORE execution.
    - Blocks dangerous system commands & SQL/Command injections in arguments.
    - Flags destructive actions for Human-In-The-Loop (HITL) confirmation.
    """
    logger.info(f"Action Rail: Validating tool call '{tool_name}' with args: {tool_args}")

    # 1. Restrict Destructive Actions -> Require HITL Approval
    if tool_name in DESTRUCTIVE_TOOLS:
        logger.warning(f"Action Rail Alert: Tool '{tool_name}' is classified as DESTRUCTIVE.")
        return ToolSecurityResult(
            is_allowed=False,
            requires_hitl=True,
            sanitized_args=tool_args,
            block_reason=f"Action '{tool_name}' is destructive and requires Human-In-The-Loop (HITL) admin approval."
        )

    # 2. Inspect Arguments for Command/SQL Injection
    for arg_name, arg_val in tool_args.items():
        if isinstance(arg_val, str):
            for pattern in DANGEROUS_ARG_PATTERNS:
                if re.search(pattern, arg_val, re.IGNORECASE):
                    logger.error(f"Action Rail Alert: Injection pattern '{pattern}' detected in arg '{arg_name}'!")
                    return ToolSecurityResult(
                        is_allowed=False,
                        requires_hitl=False,
                        sanitized_args=tool_args,
                        block_reason=f"Security Violation: Dangerous pattern detected in parameter '{arg_name}'."
                    )

    # 3. Passed validation
    return ToolSecurityResult(
        is_allowed=True,
        requires_hitl=False,
        sanitized_args=tool_args
    )
