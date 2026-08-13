"""
完整测试 - app.services.ai.nlp_query_service
覆盖率目标: 100%
"""
from unittest.mock import MagicMock, patch

class TestNLPQueryServiceParseQuery:
    """测试 parse_query 方法"""

    def test_parse_village_count(self):
        """测试解析村庄数量查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("有多少个村")

        assert result["template"] == "village_count"
        assert "COUNT(*)" in result["sql"]
        # village_count 的 SQL (SELECT COUNT(*) FROM villages) 不含 :limit 占位符，
        # parse_query 按设计只保留 SQL 中实际使用的命名参数（line 118-120 注释），
        # 因此 params 为空 dict。limit 作为辅助参数不进入 SQL 执行参数。
        assert result["params"] == {}

    def test_parse_village_by_province(self):
        """测试解析按省份查询村庄"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("广东省有多少个村")

        assert result["template"] == "village_by_province"
        assert "province" in result["params"]
        assert "广东省" in result["params"]["province"]  # 正则保留"省"字

    def test_parse_project_count(self):
        """测试解析项目数量查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("有多少个项目")

        assert result["template"] == "project_count"
        assert "projects" in result["sql"]

    def test_parse_project_by_status(self):
        """测试解析按状态查询项目"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("进行中状态的项目")

        assert result["template"] == "project_by_status"
        assert result["params"]["status"] == "in_progress"

    def test_parse_project_by_status_english(self):
        """测试解析按状态查询项目 - 英文状态"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("completed状态的项目")

        assert result["template"] == "project_by_status"
        assert result["params"]["status"] == "completed"

    def test_parse_total_funds(self):
        """测试解析资金总额查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("总资金是多少")

        assert result["template"] == "total_funds"
        assert "SUM(amount)" in result["sql"]

    def test_parse_village_income(self):
        """测试解析村庄收入查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("张家村的人均收入")

        assert result["template"] == "village_income"
        assert result["params"]["village_name"] == "张家村"

    def test_parse_top_villages_by_income(self):
        """测试解析收入最高村庄查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("人均收入排名前5")

        assert result["template"] == "top_villages_by_income"
        assert result["params"]["limit"] == 5

    def test_parse_top_villages_default_limit(self):
        """测试解析收入最高村庄查询 - 默认限制"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("人均收入排名")

        assert result["template"] == "top_villages_by_income"
        assert result["params"]["limit"] == 10

    def test_parse_unknown_query(self):
        """测试解析未知查询"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("这是一个无法理解的查询")

        assert result["template"] is None
        assert result["sql"] is None
        assert "error" in result

    def test_parse_query_strip(self):
        """测试解析时去除空白"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService.parse_query("  有多少个村  ")

        assert result["template"] == "village_count"

class TestNLPQueryServiceExecuteQuery:
    """测试 execute_query 方法"""

    def test_execute_query_success(self):
        """测试执行查询成功"""
        from app.services.ai.nlp_query_service import NLPQueryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(10,)]
        mock_result.keys.return_value = ["count"]
        mock_db.execute.return_value = mock_result

        result = NLPQueryService.execute_query(mock_db, "有多少个村")

        assert result["success"] is True
        assert result["data"] == [{"count": 10}]
        assert "explanation" in result
        mock_db.execute.assert_called_once()

    def test_execute_query_no_sql(self):
        """测试执行查询 - 无法解析"""
        from app.services.ai.nlp_query_service import NLPQueryService

        mock_db = MagicMock()

        result = NLPQueryService.execute_query(mock_db, "无法理解的查询")

        assert result["success"] is False
        assert "error" in result
        mock_db.execute.assert_not_called()

    def test_execute_query_empty_result(self):
        """测试执行查询 - 空结果"""
        from app.services.ai.nlp_query_service import NLPQueryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        result = NLPQueryService.execute_query(mock_db, "有多少个村")

        assert result["success"] is True
        assert result["data"] == []

    def test_execute_query_exception(self):
        """测试执行查询异常"""
        from app.services.ai.nlp_query_service import NLPQueryService

        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB Error")

        with patch('app.services.ai.nlp_query_service.logger') as mock_logger:
            result = NLPQueryService.execute_query(mock_db, "有多少个村")

        assert result["success"] is False
        assert "DB Error" in result["error"]
        mock_logger.error.assert_called_once()

    def test_execute_query_multiple_rows(self):
        """测试执行查询 - 多行结果"""
        from app.services.ai.nlp_query_service import NLPQueryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("village1", 10000, 2024),
            ("village2", 12000, 2024),
        ]
        mock_result.keys.return_value = ["village_name", "per_capita_income", "year"]
        mock_db.execute.return_value = mock_result

        result = NLPQueryService.execute_query(mock_db, "收入最高的村庄")

        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["village_name"] == "village1"

class TestNLPQueryServiceGenerateExplanation:
    """测试 _generate_explanation 方法"""

    def test_generate_explanation_village_count(self):
        """测试生成村庄数量解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"count": 50}]
        result = NLPQueryService._generate_explanation("village_count", data, {})

        assert "50" in result
        assert "村庄" in result

    def test_generate_explanation_village_by_province(self):
        """测试生成按省份村庄数量解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"count": 10}]
        result = NLPQueryService._generate_explanation("village_by_province", data, {"province": "广东"})

        assert "广东" in result
        assert "10" in result

    def test_generate_explanation_project_count(self):
        """测试生成项目数量解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"count": 100}]
        result = NLPQueryService._generate_explanation("project_count", data, {})

        assert "100" in result
        assert "项目" in result

    def test_generate_explanation_project_by_status(self):
        """测试生成按状态项目数量解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"count": 20}]
        result = NLPQueryService._generate_explanation("project_by_status", data, {"status": "in_progress"})

        assert "in_progress" in result
        assert "20" in result

    def test_generate_explanation_total_funds(self):
        """测试生成资金总额解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"total": 1000000.50}]
        result = NLPQueryService._generate_explanation("total_funds", data, {})

        assert "1,000,000.50" in result
        assert "元" in result

    def test_generate_explanation_village_income(self):
        """测试生成村庄收入解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"village_name": "张家村", "per_capita_income": 15000.50, "year": 2024}]
        result = NLPQueryService._generate_explanation("village_income", data, {})

        assert "张家村" in result
        assert "2024" in result
        assert "15,000.50" in result

    def test_generate_explanation_top_villages(self):
        """测试生成收入最高村庄解释"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [
            {"village_name": "富村", "per_capita_income": 50000},
            {"village_name": "中村", "per_capita_income": 30000},
        ]
        result = NLPQueryService._generate_explanation("top_villages_by_income", data, {})

        assert "富村" in result
        assert "50,000" in result
        assert "2" in result

    def test_generate_explanation_empty_data(self):
        """测试生成解释 - 空数据"""
        from app.services.ai.nlp_query_service import NLPQueryService

        result = NLPQueryService._generate_explanation("unknown_template", [], {})

        assert result == "未找到相关数据"

    def test_generate_explanation_unknown_template(self):
        """测试生成解释 - 未知模板但有数据"""
        from app.services.ai.nlp_query_service import NLPQueryService

        data = [{"id": 1}, {"id": 2}]
        result = NLPQueryService._generate_explanation("unknown_template", data, {})

        assert "2" in result
        assert "记录" in result

class TestNLPQueryServiceStatusMap:
    """测试 STATUS_MAP 映射"""

    def test_status_map_values(self):
        """测试状态映射值"""
        from app.services.ai.nlp_query_service import NLPQueryService

        assert NLPQueryService.STATUS_MAP["进行中"] == "in_progress"
        assert NLPQueryService.STATUS_MAP["已完成"] == "completed"
        assert NLPQueryService.STATUS_MAP["计划中"] == "planned"
        assert NLPQueryService.STATUS_MAP["暂停"] == "paused"
        assert NLPQueryService.STATUS_MAP["取消"] == "cancelled"

class TestNLPQueryServiceTemplates:
    """测试 QUERY_TEMPLATES 模板"""

    def test_templates_structure(self):
        """测试模板结构"""
        from app.services.ai.nlp_query_service import NLPQueryService

        for name, template in NLPQueryService.QUERY_TEMPLATES.items():
            assert "patterns" in template
            assert "sql" in template
            assert "description" in template
            assert isinstance(template["patterns"], list)
            assert len(template["patterns"]) > 0
