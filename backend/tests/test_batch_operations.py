"""
批量操作服务测试
"""

import pytest



# 导入所需的异常类和模型
from app.core.error_handler import BusinessLogicError


class TestBatchService:
    """批量操作服务测试类"""

    @pytest.fixture
    def service(self, real_db_session):
        """创建服务实例"""
        from app.services.batch_service import BatchService
        return BatchService(real_db_session)

    @pytest.fixture
    def sample_projects(self, real_db_session):
        """创建示例项目数据"""
        from app.models.project import Project
        projects = []
        for i in range(5):
            project = Project(
                name=f"测试项目{i+1}",
                code=f"PRJ{i+1:03d}",
                status="active",
                budget=100000 * (i + 1)
            )
            real_db_session.add(project)
            projects.append(project)
        real_db_session.commit()
        for p in projects:
            real_db_session.refresh(p)
        return projects

    @pytest.mark.asyncio
    async def test_batch_update_valid(self, service, sample_projects):
        """测试批量更新 - 有效数据"""
        ids = [p.id for p in sample_projects[:3]]
        updates = {"status": "completed"}

        # 2026-10-29 审计（fail-open 修复）后，非超管且未绑组织必须 fail-closed
        # （返回 success=False）。本用例只验证批量更新本身，故以超管身份调用。
        result = await service.batch_update(
            table_name="projects",
            ids=ids,
            updates=updates,
            is_superuser=True,
        )

        assert result["success"] is True
        assert result["success_count"] == 3

    @pytest.mark.asyncio
    async def test_batch_update_invalid_table(self, service):
        """测试批量更新 - 无效表名"""
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            await service.batch_update(
                table_name="invalid_table",
                ids=[1, 2, 3],
                updates={"status": "completed"}
            )

    @pytest.mark.asyncio
    async def test_batch_delete_hard(self, service, sample_projects, real_db_session):
        """测试批量删除 - 硬删除"""
        from app.models.project import Project

        ids = [p.id for p in sample_projects[:2]]

        # 先验证记录存在
        count_before = real_db_session.query(Project).filter(Project.id.in_(ids)).count()
        assert count_before == 2

        result = await service.batch_delete(
            table_name="projects",
            ids=ids,
            soft_delete=False,
            is_superuser=True,
        )

        assert result["success"] is True
        assert result["success_count"] == 2

        # 验证记录已被删除
        count_after = real_db_session.query(Project).filter(Project.id.in_(ids)).count()
        assert count_after == 0

    @pytest.mark.asyncio
    async def test_batch_export_xlsx(self, service, sample_projects):
        """测试批量导出 - XLSX格式"""
        ids = [p.id for p in sample_projects]

        result = await service.batch_export(
            table_name="projects",
            ids=ids,
            format="xlsx"
        )

        assert result["success"] is True
        assert "data" in result
        assert result["exported_count"] == len(ids)

    @pytest.mark.asyncio
    async def test_batch_validate(self, service, sample_projects):
        """测试批量验证"""
        ids = [p.id for p in sample_projects]

        result = await service.validate_batch(
            table_name="projects",
            ids=ids
        )

        assert result["success"] is True
        assert result["existing_count"] == len(ids)
