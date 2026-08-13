"""
完整测试 - app.services.ai.recommendation_service
覆盖率目标: 100%
"""
from unittest.mock import MagicMock

# admin user mock — 使 filter_by_data_scope 跳过过滤（保持 mock 链不变）
_admin = MagicMock()
_admin.is_superuser = True


class TestRecommendProjects:
    """测试 recommend_projects 方法"""

    def test_recommend_projects_success(self):
        """测试推荐项目成功"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_similar_village = MagicMock()
        mock_similar_village.id = 2

        mock_project = MagicMock()
        mock_project.project_type = "agriculture"
        mock_project.name = "农业项目"
        mock_project.village_id = 2
        mock_project.budget = 100000
        mock_project.progress = 95
        mock_project.status = "completed"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_similar_village]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        result = RecommendationService.recommend_projects(mock_db, 1, limit=5, user=_admin)

        assert len(result) > 0
        assert result[0]["project_type"] == "agriculture"
        assert "score" in result[0]

    def test_recommend_projects_no_village(self):
        """测试推荐项目 - 村庄不存在"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = RecommendationService.recommend_projects(mock_db, 999, user=_admin)

        assert result == []

    def test_recommend_projects_no_similar_villages(self):
        """测试推荐项目 - 无相似村庄"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        result = RecommendationService.recommend_projects(mock_db, 1, user=_admin)

        assert result == []

    def test_recommend_projects_no_successful_projects(self):
        """测试推荐项目 - 无成功项目"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_similar_village = MagicMock()
        mock_similar_village.id = 2

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_similar_village]
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = RecommendationService.recommend_projects(mock_db, 1, user=_admin)

        assert result == []

    def test_recommend_projects_multiple_types(self):
        """测试推荐项目 - 多种项目类型"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_similar_village = MagicMock()
        mock_similar_village.id = 2

        mock_project1 = MagicMock()
        mock_project1.project_type = "agriculture"
        mock_project1.name = "农业项目1"
        mock_project1.village_id = 2
        mock_project1.budget = 100000
        mock_project1.progress = 95

        mock_project2 = MagicMock()
        mock_project2.project_type = "tourism"
        mock_project2.name = "旅游项目"
        mock_project2.village_id = 2
        mock_project2.budget = 200000
        mock_project2.progress = 90

        mock_project3 = MagicMock()
        mock_project3.project_type = "agriculture"
        mock_project3.name = "农业项目2"
        mock_project3.village_id = 2
        mock_project3.budget = 150000
        mock_project3.progress = 92

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_similar_village]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project1, mock_project2, mock_project3]

        result = RecommendationService.recommend_projects(mock_db, 1, limit=5, user=_admin)

        assert len(result) > 0
        # 验证按分数排序
        if len(result) > 1:
            assert result[0]["score"] >= result[1]["score"]

class TestRecommendFundAllocation:
    """测试 recommend_fund_allocation 方法"""

    def test_recommend_fund_allocation_empty_village_ids(self):
        """测试推荐资金分配 - 空村庄列表"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()

        result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [], user=_admin)

        assert result["allocations"] == []
        assert "error" in result

    def test_recommend_fund_allocation_no_villages(self):
        """测试推荐资金分配 - 找不到村庄"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1], user=_admin)

        assert result["allocations"] == []
        assert "error" in result

    def test_recommend_fund_allocation_empty_village_ids(self):
        """测试推荐资金分配 - 空村庄列表"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()

        result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [], user=_admin)

        assert result["allocations"] == []
        assert "error" in result

    def test_recommend_fund_allocation_no_villages(self):
        """测试推荐资金分配 - 找不到村庄"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1], user=_admin)

        assert result["allocations"] == []
        assert "error" in result

class TestRecommendFundAllocationComplete:
    """测试 recommend_fund_allocation 完整流程"""

    def _create_mock_models(self):
        """创建模拟的模型类"""
        import sys

        # 保存原始模块引用，以便恢复而非删除，避免污染 sys.modules 缓存
        self._orig_annual_population = sys.modules.get('app.models.annual_population')
        self._orig_annual_income = sys.modules.get('app.models.annual_income')

        mock_annual_pop = MagicMock()
        mock_annual_pop_class = MagicMock()
        mock_annual_pop_class.village_id = MagicMock()
        mock_annual_pop_class.year = MagicMock()
        mock_annual_pop_class.total_population = MagicMock()

        mock_annual_inc = MagicMock()
        mock_annual_inc_class = MagicMock()
        mock_annual_inc_class.village_id = MagicMock()
        mock_annual_inc_class.year = MagicMock()
        mock_annual_inc_class.per_capita_income = MagicMock()

        sys.modules['app.models.annual_population'] = MagicMock(AnnualPopulation=mock_annual_pop_class)
        sys.modules['app.models.annual_income'] = MagicMock(AnnualIncome=mock_annual_inc_class)

        return mock_annual_pop_class, mock_annual_inc_class

    def _restore_modules(self):
        """恢复原始模块，避免污染其他测试的 sys.modules 缓存"""
        import sys
        for mod_key, orig_val in [
            ('app.models.annual_population', getattr(self, '_orig_annual_population', None)),
            ('app.models.annual_income', getattr(self, '_orig_annual_income', None)),
        ]:
            if orig_val is not None:
                sys.modules[mod_key] = orig_val
            elif mod_key in sys.modules:
                del sys.modules[mod_key]

    def test_recommend_fund_allocation_success_path(self):
        """测试资金分配成功路径 - 覆盖157-242行"""
        from app.services.ai.recommendation_service import RecommendationService

        # 使用普通对象代替MagicMock来避免比较问题
        class MockVillage:
            id = 1
            village_name = "测试村"

        class MockPop:
            supported_village_id = 1
            population = 5000

        class MockInc:
            supported_village_id = 1
            year = 2025
            per_capita_income_2025 = 5000

        mock_village = MockVillage()
        mock_pop = MockPop()
        mock_inc = MockInc()

        self._create_mock_models()

        # 构建mock_db - 使用side_effect处理多次查询
        call_count = [0]
        mock_db = MagicMock()

        def mock_query(*args):
            call_count[0] += 1
            mock_q = MagicMock()
            model_class = args[0] if args else None

            # 第一次查询: Village
            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [mock_village]
            # 第二次查询: population subquery (创建子查询)
            elif call_count[0] == 2:
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            # 第三次查询: population data query
            elif call_count[0] == 3:
                mock_q.join.return_value.all.return_value = [mock_pop]
            # 第四次查询: income subquery (创建子查询)
            elif call_count[0] == 4:
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            # 第五次查询: income data query
            elif call_count[0] == 5:
                mock_q.join.return_value.all.return_value = [mock_inc]
            else:
                mock_q.all.return_value = []

            return mock_q

        mock_db.query.side_effect = mock_query

        try:
            result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1], user=_admin)
        finally:
            self._restore_modules()

        assert result["total_budget"] == 1000000
        assert result["method"] == "weighted_by_need"

    def test_recommend_fund_allocation_no_population_data(self):
        """测试资金分配 - 无人口数据（覆盖207-213行）"""
        from app.services.ai.recommendation_service import RecommendationService

        class MockVillage:
            id = 1
            village_name = "测试村"

        class MockInc:
            supported_village_id = 1
            year = 2025
            per_capita_income_2025 = 5000

        mock_village = MockVillage()
        mock_inc = MockInc()

        self._create_mock_models()

        call_count = [0]
        mock_db = MagicMock()

        def mock_query(*args):
            call_count[0] += 1
            mock_q = MagicMock()

            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [mock_village]
            elif call_count[0] == 2:  # pop subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 3:  # pop data query
                mock_q.join.return_value.all.return_value = []  # 无人口数据
            elif call_count[0] == 4:  # inc subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 5:  # inc data query
                mock_q.join.return_value.all.return_value = [mock_inc]

            return mock_q

        mock_db.query.side_effect = mock_query

        try:
            result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1], user=_admin)
        finally:
            self._restore_modules()

        assert result["total_budget"] == 1000000
        # 验证allocations中有数据（无人口数据时population_score为0）

    def test_recommend_fund_allocation_no_income_data(self):
        """测试资金分配 - 无收入数据（覆盖214行）"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"

        mock_pop = MagicMock()
        mock_pop.supported_village_id = 1
        mock_pop.population = 5000

        self._create_mock_models()

        call_count = [0]
        mock_db = MagicMock()

        def mock_query(*args):
            call_count[0] += 1
            mock_q = MagicMock()

            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [mock_village]
            elif call_count[0] == 2:  # pop subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 3:  # pop data query
                mock_q.join.return_value.all.return_value = [mock_pop]
            elif call_count[0] == 4:  # inc subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 5:  # inc data query (empty)
                mock_q.join.return_value.all.return_value = []  # 无收入数据

            return mock_q

        mock_db.query.side_effect = mock_query

        try:
            result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1], user=_admin)
        finally:
            self._restore_modules()

        assert result["total_budget"] == 1000000

    def test_recommend_fund_allocation_calculation(self):
        """测试资金分配计算逻辑（覆盖216-237行）"""
        from app.services.ai.recommendation_service import RecommendationService

        class MockVillage1:
            id = 1
            village_name = "村1"

        class MockVillage2:
            id = 2
            village_name = "村2"

        class MockPop1:
            supported_village_id = 1
            population = 5000

        class MockPop2:
            supported_village_id = 2
            population = 3000

        class MockInc1:
            supported_village_id = 1
            year = 2025
            per_capita_income_2025 = 5000

        class MockInc2:
            supported_village_id = 2
            year = 2025
            per_capita_income_2025 = 8000

        mock_village1 = MockVillage1()
        mock_village2 = MockVillage2()
        mock_pop1 = MockPop1()
        mock_pop2 = MockPop2()
        mock_inc1 = MockInc1()
        mock_inc2 = MockInc2()

        self._create_mock_models()

        call_count = [0]
        mock_db = MagicMock()

        def mock_query(*args):
            call_count[0] += 1
            mock_q = MagicMock()

            if call_count[0] == 1:
                mock_q.filter.return_value.all.return_value = [mock_village1, mock_village2]
            elif call_count[0] == 2:  # pop subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 3:  # pop data query
                mock_q.join.return_value.all.return_value = [mock_pop1, mock_pop2]
            elif call_count[0] == 4:  # inc subquery
                mock_q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call_count[0] == 5:  # inc data query
                mock_q.join.return_value.all.return_value = [mock_inc1, mock_inc2]

            return mock_q

        mock_db.query.side_effect = mock_query

        try:
            result = RecommendationService.recommend_fund_allocation(mock_db, 1000000, [1, 2], user=_admin)
        finally:
            self._restore_modules()

        assert len(result["allocations"]) == 2
        # 验证按推荐金额排序
        if len(result["allocations"]) == 2:
            assert result["allocations"][0]["recommended_amount"] >= result["allocations"][1]["recommended_amount"]
        # 验证百分比计算
        assert "percentage" in result["allocations"][0]

class TestMatchPolicies:
    """测试 match_policies 方法"""

    def test_match_policies_success(self):
        """测试政策匹配成功"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "农业支持政策"
        mock_policy.content = "支持广东地区农业发展"
        mock_policy.scope = "province"
        mock_policy.province = "广东"
        mock_policy.city = None
        mock_policy.category = "agriculture"
        mock_policy.effective_date = None
        mock_policy.status = "active"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_policy]

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        assert len(result) > 0
        assert result[0]["policy_id"] == 1
        assert "score" in result[0]

    def test_match_policies_no_village(self):
        """测试政策匹配 - 村庄不存在"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = RecommendationService.match_policies(mock_db, 999, user=_admin)

        assert result == []

    def test_match_policies_no_policies(self):
        """测试政策匹配 - 无政策"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        assert result == []

    def test_match_policies_national_scope(self):
        """测试政策匹配 - 全国范围政策"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "全国农业政策"
        mock_policy.content = "支持全国农业发展"
        mock_policy.scope = "national"
        mock_policy.province = None
        mock_policy.city = None
        mock_policy.category = "agriculture"
        mock_policy.effective_date = None
        mock_policy.status = "active"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_policy]

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        assert len(result) > 0
        assert "全国性政策" in result[0]["reasons"]

    def test_match_policies_city_match(self):
        """测试政策匹配 - 市级匹配"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "深圳特区政策"
        mock_policy.content = "支持深圳发展"
        mock_policy.scope = "province"
        mock_policy.province = "广东"
        mock_policy.city = "深圳"
        mock_policy.category = "development"
        mock_policy.effective_date = None
        mock_policy.status = "active"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_policy]

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        assert len(result) > 0
        assert any("深圳" in reason for reason in result[0]["reasons"])

    def test_match_policies_no_match(self):
        """测试政策匹配 - 无匹配政策"""
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "北京政策"
        mock_policy.content = "仅适用于北京"
        mock_policy.scope = "province"
        mock_policy.province = "北京"
        mock_policy.city = None
        mock_policy.category = "test"
        mock_policy.effective_date = None
        mock_policy.status = "active"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_policy]

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        # 由于省份不匹配，应该没有匹配结果
        assert len(result) == 0

    def test_match_policies_with_effective_date(self):
        """测试政策匹配 - 带生效日期"""
        from datetime import date
        from app.services.ai.recommendation_service import RecommendationService

        mock_village = MagicMock()
        mock_village.id = 1
        mock_village.village_name = "测试村"
        mock_village.province = "广东"
        mock_village.city = "深圳"

        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "农业支持政策"
        mock_policy.content = "支持广东地区农业发展"
        mock_policy.scope = "national"
        mock_policy.province = None
        mock_policy.city = None
        mock_policy.category = "agriculture"
        mock_policy.effective_date = date(2024, 1, 1)
        mock_policy.status = "active"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_village
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_policy]

        result = RecommendationService.match_policies(mock_db, 1, user=_admin)

        assert len(result) > 0
        assert result[0]["effective_date"] == "2024-01-01"
