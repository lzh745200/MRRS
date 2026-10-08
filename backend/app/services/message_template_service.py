"""
消息模板服务

Task 7.1: 实现消息模板服务
- 模板CRUD
- 变量占位符替换
- 预置常用模板（审批通知、任务提醒等）

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import re
from datetime import timezone, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.message_template import MessageTemplate, TemplateCode
from app.core.transaction import safe_commit


class TemplateHistoryEntry:
    """模板修改历史条目"""

    def __init__(
        self,
        template_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
        modified_by: Optional[int] = None,
        modified_at: Optional[datetime] = None,
    ):
        self.template_id = template_id
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.modified_by = modified_by
        self.modified_at = modified_at or datetime.now(timezone.utc)


class MessageTemplateService:
    """
    消息模板服务类

    Requirements:
    - 7.1: 提供消息模板管理界面
    - 7.2: 支持变量占位符（如用户名、时间、链接等）
    - 7.3: 预置常用消息模板
    - 7.4: 记录修改历史
    - 7.5: 支持模板的启用和禁用
    """

    # 支持的变量占位符
    SUPPORTED_VARIABLES = [
        "username",  # 用户名
        "user_id",  # 用户ID
        "time",  # 时间
        "date",  # 日期
        "datetime",  # 日期时间
        "link",  # 链接
        "title",  # 标题
        "content",  # 内容
        "entity_type",  # 实体类型
        "entity_id",  # 实体ID
        "entity_name",  # 实体名称
        "approver",  # 审批人
        "submitter",  # 提交人
        "opinion",  # 审批意见
        "status",  # 状态
        "task_name",  # 任务名称
        "deadline",  # 截止时间
        "system_name",  # 系统名称
    ]

    # 变量占位符正则表达式
    VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")

    def __init__(self, db: Session):
        self.db = db
        self._history: List[TemplateHistoryEntry] = []

    # ==================== 模板 CRUD ====================

    def create_template(
        self,
        code: str,
        name: str,
        message_type: str,
        title_template: str,
        content_template: str,
        email_subject_template: Optional[str] = None,
        email_body_template: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        is_system: bool = False,
        created_by: Optional[int] = None,
    ) -> MessageTemplate:
        """
        创建消息模板

        Args:
            code: 模板编码（唯一）
            name: 模板名称
            message_type: 消息类型 (system / approval / task)
            title_template: 标题模板
            content_template: 内容模板
            email_subject_template: 邮件主题模板
            email_body_template: 邮件正文模板
            description: 模板描述
            is_active: 是否启用
            is_system: 是否为系统预置模板
            created_by: 创建人ID

        Returns:
            MessageTemplate: 创建的模板

        Raises:
            ValueError: 模板编码已存在或消息类型无效
        """
        # 验证消息类型
        valid_types = ["system", "approval", "task"]
        if message_type not in valid_types:
            raise ValueError(f"无效的消息类型: {message_type}，有效类型: {valid_types}")

        # 检查编码是否已存在
        existing = self.get_template_by_code(code)
        if existing:
            raise ValueError(f"模板编码已存在: {code}")

        template = MessageTemplate(
            code=code,
            name=name,
            message_type=message_type,
            title_template=title_template,
            content_template=content_template,
            email_subject_template=email_subject_template,
            email_body_template=email_body_template,
            description=description,
            is_active=is_active,
            is_system=is_system,
            created_by=created_by,
        )

        self.db.add(template)
        safe_commit(self.db)
        self.db.refresh(template)
        return template

    def get_template(self, template_id: int) -> Optional[MessageTemplate]:
        """根据ID获取模板"""
        return self.db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()

    def get_template_by_code(self, code: str) -> Optional[MessageTemplate]:
        """根据编码获取模板"""
        return self.db.query(MessageTemplate).filter(MessageTemplate.code == code).first()

    def list_templates(
        self,
        message_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_system: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MessageTemplate]:
        """
        列出模板

        Args:
            message_type: 消息类型筛选
            is_active: 是否启用筛选
            is_system: 是否系统模板筛选
            skip: 跳过数量
            limit: 返回数量限制

        Returns:
            List[MessageTemplate]: 模板列表
        """
        query = self.db.query(MessageTemplate)

        if message_type:
            query = query.filter(MessageTemplate.message_type == message_type)
        if is_active is not None:
            query = query.filter(MessageTemplate.is_active == is_active)
        if is_system is not None:
            query = query.filter(MessageTemplate.is_system == is_system)

        return query.order_by(MessageTemplate.created_at.desc()).offset(skip).limit(limit).all()

    def update_template(
        self,
        template_id: int,
        name: Optional[str] = None,
        title_template: Optional[str] = None,
        content_template: Optional[str] = None,
        email_subject_template: Optional[str] = None,
        email_body_template: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        modified_by: Optional[int] = None,
    ) -> Optional[MessageTemplate]:
        """
        更新模板

        Requirements: 7.4 - 记录修改历史

        Args:
            template_id: 模板ID
            name: 新名称
            title_template: 新标题模板
            content_template: 新内容模板
            email_subject_template: 新邮件主题模板
            email_body_template: 新邮件正文模板
            description: 新描述
            is_active: 是否启用
            modified_by: 修改人ID

        Returns:
            Optional[MessageTemplate]: 更新后的模板，不存在返回None
        """
        template = self.get_template(template_id)
        if not template:
            return None

        # 记录修改历史
        if name is not None and name != template.name:
            self._record_history(template_id, "name", template.name, name, modified_by)
            template.name = name

        if title_template is not None and title_template != template.title_template:
            self._record_history(
                template_id,
                "title_template",
                template.title_template,
                title_template,
                modified_by,
            )
            template.title_template = title_template

        if content_template is not None and content_template != template.content_template:
            self._record_history(
                template_id,
                "content_template",
                template.content_template,
                content_template,
                modified_by,
            )
            template.content_template = content_template

        if email_subject_template is not None and email_subject_template != template.email_subject_template:
            self._record_history(
                template_id,
                "email_subject_template",
                template.email_subject_template,
                email_subject_template,
                modified_by,
            )
            template.email_subject_template = email_subject_template

        if email_body_template is not None and email_body_template != template.email_body_template:
            self._record_history(
                template_id,
                "email_body_template",
                template.email_body_template,
                email_body_template,
                modified_by,
            )
            template.email_body_template = email_body_template

        if description is not None and description != template.description:
            self._record_history(
                template_id,
                "description",
                template.description,
                description,
                modified_by,
            )
            template.description = description

        if is_active is not None and is_active != template.is_active:
            self._record_history(template_id, "is_active", template.is_active, is_active, modified_by)
            template.is_active = is_active

        safe_commit(self.db)
        self.db.refresh(template)
        return template

    def delete_template(self, template_id: int) -> bool:
        """
        删除模板

        Args:
            template_id: 模板ID

        Returns:
            bool: 是否删除成功
        """
        template = self.get_template(template_id)
        if not template:
            return False

        # 系统预置模板不能删除
        if template.is_system:
            return False

        self.db.delete(template)
        safe_commit(self.db)
        return True

    def enable_template(self, template_id: int, modified_by: Optional[int] = None) -> Optional[MessageTemplate]:
        """启用模板"""
        return self.update_template(template_id, is_active=True, modified_by=modified_by)

    def disable_template(self, template_id: int, modified_by: Optional[int] = None) -> Optional[MessageTemplate]:
        """禁用模板"""
        return self.update_template(template_id, is_active=False, modified_by=modified_by)

    # ==================== 模板渲染 ====================

    def render_template(
        self, code: str, variables: Dict[str, Any], use_defaults: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        渲染模板

        Requirements: 7.2 - 支持变量占位符

        Args:
            code: 模板编码
            variables: 变量字典
            use_defaults: 是否使用默认值填充缺失变量

        Returns:
            Optional[Dict[str, str]]: 渲染结果，包含title, content, email_subject, email_body
        """
        template = self.get_template_by_code(code)
        if not template or not template.is_active:
            return None

        # 准备变量
        render_vars = self._prepare_variables(variables, use_defaults)

        return {
            "title": self._render_string(template.title_template, render_vars),
            "content": self._render_string(template.content_template, render_vars),
            "email_subject": (
                self._render_string(template.email_subject_template, render_vars)
                if template.email_subject_template
                else None
            ),
            "email_body": (
                self._render_string(template.email_body_template, render_vars) if template.email_body_template else None
            ),
        }

    def render_title(self, code: str, variables: Dict[str, Any]) -> Optional[str]:
        """渲染标题"""
        result = self.render_template(code, variables)
        return result["title"] if result else None

    def render_content(self, code: str, variables: Dict[str, Any]) -> Optional[str]:
        """渲染内容"""
        result = self.render_template(code, variables)
        return result["content"] if result else None

    def _render_string(self, template_str: str, variables: Dict[str, Any]) -> str:
        """
        渲染字符串模板

        Args:
            template_str: 模板字符串
            variables: 变量字典

        Returns:
            str: 渲染后的字符串
        """
        if not template_str:
            return ""

        try:
            return template_str.format(**variables)
        except KeyError as e:
            # R20 复审：原实现只补第一个缺失变量，模板含 ≥2 个缺失占位符时
            # 二次 format 仍抛 KeyError。改为 format_map + 缺失键保留原占位符，
            # 一次渲染完成，不因多缺失变量中断发送链路。
            missing_key = str(e).strip("'")
            variables[missing_key] = f"{{{missing_key}}}"

            class _KeepMissingPlaceholders(dict):
                def __missing__(self, key: str) -> str:
                    return "{" + key + "}"

            return template_str.format_map(_KeepMissingPlaceholders(variables))

    def _prepare_variables(self, variables: Dict[str, Any], use_defaults: bool = True) -> Dict[str, Any]:
        """
        准备渲染变量

        Args:
            variables: 原始变量字典
            use_defaults: 是否使用默认值

        Returns:
            Dict[str, Any]: 处理后的变量字典
        """
        result = dict(variables)

        if use_defaults:  # 添加默认值
            defaults = {
                "system_name": "帮扶管理系统",
                "time": datetime.now().strftime("%H:%M:%S"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            for key, value in defaults.items():
                if key not in result:
                    result[key] = value

        return result

    def extract_variables(self, template_str: str) -> List[str]:
        """
        从模板字符串中提取变量名

        Args:
            template_str: 模板字符串

        Returns:
            List[str]: 变量名列表
        """
        if not template_str:
            return []
        return self.VARIABLE_PATTERN.findall(template_str)

    def validate_variables(self, template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证变量是否完整

        Args:
            template_str: 模板字符串
            variables: 变量字典

        Returns:
            Dict[str, Any]: 包含 is_valid, missing_variables, extra_variables
        """
        required_vars = set(self.extract_variables(template_str))
        provided_vars = set(variables.keys())

        missing = required_vars - provided_vars
        extra = provided_vars - required_vars

        return {
            "is_valid": len(missing) == 0,
            "missing_variables": list(missing),
            "extra_variables": list(extra),
            "required_variables": list(required_vars),
        }

    # ==================== 修改历史 ====================

    def _record_history(
        self,
        template_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
        modified_by: Optional[int] = None,
    ) -> None:
        """
        记录修改历史

        Requirements: 7.4 - 记录修改历史
        """
        entry = TemplateHistoryEntry(
            template_id=template_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            modified_by=modified_by,
        )
        self._history.append(entry)

    def get_template_history(self, template_id: int) -> List[TemplateHistoryEntry]:
        """
        获取模板修改历史

        Args:
            template_id: 模板ID

        Returns:
            List[TemplateHistoryEntry]: 修改历史列表
        """
        return [h for h in self._history if h.template_id == template_id]

    def get_all_history(self) -> List[TemplateHistoryEntry]:
        """获取所有修改历史"""
        return self._history.copy()

    def clear_history(self) -> None:
        """清空修改历史"""
        self._history.clear()

    # ==================== 预置模板 ====================

    def init_default_templates(self, created_by: Optional[int] = None) -> List[MessageTemplate]:
        """
        初始化预置模板

        Requirements: 7.3 - 预置常用消息模板

        Args:
            created_by: 创建人ID

        Returns:
            List[MessageTemplate]: 创建的模板列表
        """
        templates = []
        default_templates = self._get_default_templates()

        for template_data in default_templates:
            # 检查是否已存在
            existing = self.get_template_by_code(template_data["code"])
            if existing:
                continue

            template = self.create_template(
                code=template_data["code"],
                name=template_data["name"],
                message_type=template_data["message_type"],
                title_template=template_data["title_template"],
                content_template=template_data["content_template"],
                email_subject_template=template_data.get("email_subject_template"),
                email_body_template=template_data.get("email_body_template"),
                description=template_data.get("description"),
                is_active=True,
                is_system=True,
                created_by=created_by,
            )
            templates.append(template)

        return templates

    def _get_default_templates(self) -> List[Dict[str, Any]]:
        """
        获取预置模板配置

        Returns:
            List[Dict[str, Any]]: 预置模板配置列表
        """
        return [
            # 审批相关模板
            {
                "code": TemplateCode.APPROVAL_SUBMITTED,
                "name": "审批已提交通知",
                "message_type": "approval",
                "title_template": "您有新的审批任务待处理",
                "content_template": "{submitter}提交了{entity_type}变更申请，请及时审批。\n\n变更内容：{title}\n提交时间：{datetime}",
                "email_subject_template": "【待审批】{title}",
                "email_body_template": """
<html>
<body>
<h3>您有新的审批任务</h3>
<p>提交人：{submitter}</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>提交时间：{datetime}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当有新的审批任务提交时发送给审批人",
            },
            {
                "code": TemplateCode.APPROVAL_APPROVED,
                "name": "审批通过通知",
                "message_type": "approval",
                "title_template": "您的申请已通过审批",
                "content_template": "您提交的{entity_type}变更申请已通过审批。\n\n审批人：{approver}\n审批时间：{datetime}\n审批意见：{opinion}",
                "email_subject_template": "【已通过】{title}",
                "email_body_template": """
<html>
<body>
<h3>审批通过通知</h3>
<p>您提交的变更申请已通过审批。</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>审批人：{approver}</p>
<p>审批时间：{datetime}</p>
<p>审批意见：{opinion}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当审批通过时发送给提交人",
            },
            {
                "code": TemplateCode.APPROVAL_REJECTED,
                "name": "审批拒绝通知",
                "message_type": "approval",
                "title_template": "您的申请已被拒绝",
                "content_template": "您提交的{entity_type}变更申请已被拒绝。\n\n审批人：{approver}\n审批时间：{datetime}\n拒绝原因：{opinion}",
                "email_subject_template": "【已拒绝】{title}",
                "email_body_template": """
<html>
<body>
<h3>审批拒绝通知</h3>
<p>您提交的变更申请已被拒绝。</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>审批人：{approver}</p>
<p>审批时间：{datetime}</p>
<p>拒绝原因：{opinion}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当审批被拒绝时发送给提交人",
            },
            {
                "code": TemplateCode.APPROVAL_TRANSFERRED,
                "name": "审批转交通知",
                "message_type": "approval",
                "title_template": "您收到一个转交的审批任务",
                "content_template": "{approver}将一个审批任务转交给您处理。\n\n变更类型：{entity_type}\n变更内容：{title}\n转交时间：{datetime}",
                "email_subject_template": "【转交审批】{title}",
                "email_body_template": """
<html>
<body>
<h3>审批转交通知</h3>
<p>{approver}将一个审批任务转交给您处理。</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>转交时间：{datetime}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当审批任务被转交时发送给新审批人",
            },
            {
                "code": TemplateCode.APPROVAL_WITHDRAWN,
                "name": "审批撤回通知",
                "message_type": "approval",
                "title_template": "审批申请已被撤回",
                "content_template": "{submitter}撤回了{entity_type}变更申请。\n\n变更内容：{title}\n撤回时间：{datetime}",
                "email_subject_template": "【已撤回】{title}",
                "email_body_template": """
<html>
<body>
<h3>审批撤回通知</h3>
<p>{submitter}撤回了变更申请。</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>撤回时间：{datetime}</p>
</body>
</html>
""",
                "description": "当审批申请被撤回时发送给审批人",
            },
            {
                "code": TemplateCode.APPROVAL_PENDING,
                "name": "待审批提醒",
                "message_type": "approval",
                "title_template": "您有待处理的审批任务",
                "content_template": "您有{count}个审批任务待处理，请及时审批。\n\n最早提交时间：{earliest_time}",
                "email_subject_template": "【待审批提醒】您有{count}个任务待处理",
                "email_body_template": """
<html>
<body>
<h3>待审批提醒</h3>
<p>您有{count}个审批任务待处理，请及时审批。</p>
<p>最早提交时间：{earliest_time}</p>
<p><a href="{link}">点击查看待审批列表</a></p>
</body>
</html>
""",
                "description": "定期提醒审批人处理待审批任务",
            },
            {
                "code": TemplateCode.APPROVAL_TIMEOUT,
                "name": "审批超时提醒",
                "message_type": "approval",
                "title_template": "审批任务即将超时",
                "content_template": (
                    "您有一个审批任务即将超时，请尽快处理。\n\n"
                    "变更类型：{entity_type}\n变更内容：{title}\n"
                    "提交时间：{submit_time}\n截止时间：{deadline}"
                ),
                "email_subject_template": "【超时提醒】审批任务即将超时",
                "email_body_template": """
<html>
<body>
<h3>审批超时提醒</h3>
<p>您有一个审批任务即将超时，请尽快处理。</p>
<p>变更类型：{entity_type}</p>
<p>变更内容：{title}</p>
<p>提交时间：{submit_time}</p>
<p>截止时间：{deadline}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当审批任务即将超时时发送提醒",
            },
            # 任务相关模板
            {
                "code": TemplateCode.TASK_ASSIGNED,
                "name": "任务分配通知",
                "message_type": "task",
                "title_template": "您有新的任务分配",
                "content_template": "您被分配了一个新任务：{task_name}\n\n分配人：{assigner}\n截止时间：{deadline}\n任务描述：{content}",
                "email_subject_template": "【新任务】{task_name}",
                "email_body_template": """
<html>
<body>
<h3>任务分配通知</h3>
<p>您被分配了一个新任务。</p>
<p>任务名称：{task_name}</p>
<p>分配人：{assigner}</p>
<p>截止时间：{deadline}</p>
<p>任务描述：{content}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当任务被分配给用户时发送通知",
            },
            {
                "code": TemplateCode.TASK_COMPLETED,
                "name": "任务完成通知",
                "message_type": "task",
                "title_template": "任务已完成",
                "content_template": "{username}完成了任务：{task_name}\n\n完成时间：{datetime}",
                "email_subject_template": "【任务完成】{task_name}",
                "email_body_template": """
<html>
<body>
<h3>任务完成通知</h3>
<p>{username}完成了任务。</p>
<p>任务名称：{task_name}</p>
<p>完成时间：{datetime}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "当任务完成时发送通知",
            },
            {
                "code": TemplateCode.TASK_REMINDER,
                "name": "任务提醒",
                "message_type": "task",
                "title_template": "任务即将到期提醒",
                "content_template": "您的任务即将到期，请及时处理。\n\n任务名称：{task_name}\n截止时间：{deadline}",
                "email_subject_template": "【任务提醒】{task_name}即将到期",
                "email_body_template": """
<html>
<body>
<h3>任务到期提醒</h3>
<p>您的任务即将到期，请及时处理。</p>
<p>任务名称：{task_name}</p>
<p>截止时间：{deadline}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "任务即将到期时发送提醒",
            },
            # 系统相关模板
            {
                "code": TemplateCode.SYSTEM_ANNOUNCEMENT,
                "name": "系统公告",
                "message_type": "system",
                "title_template": "系统公告：{title}",
                "content_template": "{content}",
                "email_subject_template": "【系统公告】{title}",
                "email_body_template": """
<html>
<body>
<h3>系统公告</h3>
<p>{content}</p>
<p>发布时间：{datetime}</p>
</body>
</html>
""",
                "description": "系统公告通知",
            },
            {
                "code": TemplateCode.SYSTEM_MAINTENANCE,
                "name": "系统维护通知",
                "message_type": "system",
                "title_template": "系统维护通知",
                "content_template": "系统将于{start_time}至{end_time}进行维护，届时系统将暂停服务。\n\n维护内容：{content}\n\n给您带来的不便，敬请谅解。",
                "email_subject_template": "【系统维护】{system_name}维护通知",
                "email_body_template": """
<html>
<body>
<h3>系统维护通知</h3>
<p>系统将于{start_time}至{end_time}进行维护，届时系统将暂停服务。</p>
<p>维护内容：{content}</p>
<p>给您带来的不便，敬请谅解。</p>
</body>
</html>
""",
                "description": "系统维护时发送通知",
            },
            {
                "code": TemplateCode.IMPORT_COMPLETED,
                "name": "导入完成通知",
                "message_type": "system",
                "title_template": "数据导入完成",
                "content_template": (
                    "您的数据导入任务已完成。\n\n"
                    "导入文件：{filename}\n总记录数：{total}\n"
                    "成功：{success}\n失败：{failed}\n完成时间：{datetime}"
                ),
                "email_subject_template": "【导入完成】{filename}",
                "email_body_template": """
<html>
<body>
<h3>数据导入完成</h3>
<p>您的数据导入任务已完成。</p>
<p>导入文件：{filename}</p>
<p>总记录数：{total}</p>
<p>成功：{success}</p>
<p>失败：{failed}</p>
<p>完成时间：{datetime}</p>
<p><a href="{link}">点击查看详情</a></p>
</body>
</html>
""",
                "description": "数据导入完成时发送通知",
            },
            {
                "code": TemplateCode.EXPORT_COMPLETED,
                "name": "导出完成通知",
                "message_type": "system",
                "title_template": "数据导出完成",
                "content_template": "您的数据导出任务已完成，文件将保留7天。\n\n导出类型：{export_type}\n记录数：{count}\n完成时间：{datetime}",
                "email_subject_template": "【导出完成】{export_type}数据导出",
                "email_body_template": """
<html>
<body>
<h3>数据导出完成</h3>
<p>您的数据导出任务已完成，文件将保留7天。</p>
<p>导出类型：{export_type}</p>
<p>记录数：{count}</p>
<p>完成时间：{datetime}</p>
<p><a href="{link}">点击下载文件</a></p>
</body>
</html>
""",
                "description": "数据导出完成时发送通知",
            },
        ]
