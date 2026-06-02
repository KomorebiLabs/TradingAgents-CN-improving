import unittest
from unittest.mock import patch

from tradingagents.dataflows.akshare_interface import (
    _normalize_cn_symbol,
    get_akshare_cn_market_flow,
    get_akshare_cn_policy_news,
    get_akshare_fundamentals,
    get_akshare_fund_flow,
    get_akshare_news,
)
from tradingagents.dataflows.interface import VENDOR_METHODS


class AkShareInterfaceTests(unittest.TestCase):
    def test_normalize_cn_symbol_with_exchange_suffix(self):
        self.assertEqual(_normalize_cn_symbol("600519.SH"), ("600519", "sh"))
        self.assertEqual(_normalize_cn_symbol("000001.SZ"), ("000001", "sz"))

    def test_normalize_cn_symbol_by_prefix(self):
        self.assertEqual(_normalize_cn_symbol("600036"), ("600036", "sh"))
        self.assertEqual(_normalize_cn_symbol("300750"), ("300750", "sz"))

    def test_akshare_vendor_registered_for_stock_data(self):
        self.assertIn("akshare", VENDOR_METHODS["get_stock_data"])

    def test_akshare_vendor_registered_for_cn_batch_two_tools(self):
        self.assertIn("akshare", VENDOR_METHODS["get_fundamentals"])
        self.assertIn("akshare", VENDOR_METHODS["get_news"])
        self.assertIn("akshare", VENDOR_METHODS["get_global_news"])
        self.assertIn("akshare", VENDOR_METHODS["get_insider_transactions"])
        self.assertIn("akshare", VENDOR_METHODS["get_cn_policy_news"])
        self.assertIn("akshare", VENDOR_METHODS["get_cn_market_flow"])

    @patch("tradingagents.dataflows.akshare_interface._require_akshare")
    def test_fund_flow_output_is_labeled_as_cn_proxy(self, mock_require_akshare):
        class MockAkshare:
            @staticmethod
            def stock_individual_fund_flow(stock, market):
                import pandas as pd

                return pd.DataFrame(
                    [
                        {
                            "日期": "2026-05-01",
                            "收盘价": 10.5,
                            "涨跌幅": 1.2,
                            "主力净流入-净额": 123456,
                            "主力净流入-净占比": 3.4,
                        }
                    ]
                )

        mock_require_akshare.return_value = MockAkshare()

        result = get_akshare_fund_flow("000001.SZ")

        self.assertIn("CN A-share fund-flow proxy", result)
        self.assertIn("replaces insider transactions", result)
        self.assertIn("2026-05-01", result)
        self.assertIn("MainForceNetInflow", result)
        self.assertNotIn("日期,收盘价", result)

    @patch("tradingagents.dataflows.akshare_interface._require_akshare")
    def test_fundamentals_snapshot_is_pruned_to_core_fields(self, mock_require_akshare):
        class MockAkshare:
            @staticmethod
            def stock_individual_info_em(symbol):
                import pandas as pd

                return pd.DataFrame(
                    [
                        {"item": "股票代码", "value": symbol},
                        {"item": "股票简称", "value": "贵州茅台"},
                        {"item": "行业", "value": "白酒"},
                        {"item": "上市时间", "value": "2001-08-27"},
                        {"item": "总市值", "value": "2100000000000"},
                        {"item": "流通市值", "value": "2100000000000"},
                        {"item": "总股本", "value": "1256197800"},
                        {"item": "流通股", "value": "1256197800"},
                        {"item": "最新", "value": "1678.88"},
                        {"item": "无关字段", "value": "should-not-appear"},
                    ]
                )

        mock_require_akshare.return_value = MockAkshare()

        result = get_akshare_fundamentals("600519.SH", "2026-05-05")

        self.assertIn("Fields pruned for LLM consumption", result)
        self.assertIn("Name: 贵州茅台", result)
        self.assertIn("Industry: 白酒", result)
        self.assertNotIn("无关字段", result)

    @patch("tradingagents.dataflows.akshare_interface._require_akshare")
    def test_news_output_truncates_long_content_and_uses_bullets(self, mock_require_akshare):
        class MockAkshare:
            @staticmethod
            def stock_news_em(symbol):
                import pandas as pd

                return pd.DataFrame(
                    [
                        {
                            "发布时间": "2026-05-05 09:30:00",
                            "新闻标题": "测试标题" * 30,
                            "文章来源": "证券时报",
                            "关键词": "新能源",
                            "新闻内容": "长文本" * 100,
                            "新闻链接": "https://example.com/news",
                        }
                    ]
                )

        mock_require_akshare.return_value = MockAkshare()

        result = get_akshare_news("300750.SZ", "2026-05-01", "2026-05-05")

        self.assertIn("Total articles included: 1", result)
        self.assertIn("- Title:", result)
        self.assertIn("- Summary:", result)
        self.assertIn("...", result)
        self.assertNotIn("新闻标题,文章来源", result)

    @patch("tradingagents.dataflows.akshare_interface._require_akshare")
    def test_cn_policy_news_filters_for_policy_sensitive_events(self, mock_require_akshare):
        class MockAkshare:
            @staticmethod
            def news_economic_baidu(date):
                import pandas as pd

                return pd.DataFrame(
                    [
                        {"日期": "2026-05-05", "时间": "09:00", "地区": "中国", "事件": "科技创新补贴政策出台", "公布": "", "预期": "", "前值": "", "重要性": 5},
                        {"日期": "2026-05-05", "时间": "10:00", "地区": "美国", "事件": "Nonfarm payrolls", "公布": "", "预期": "", "前值": "", "重要性": 4},
                    ]
                )

        mock_require_akshare.return_value = MockAkshare()

        result = get_akshare_cn_policy_news("2026-05-05", look_back_days=1, limit=5)

        self.assertIn("policy and regulation-sensitive events", result)
        self.assertIn("科技创新补贴政策出台", result)
        self.assertNotIn("Nonfarm payrolls", result)

    @patch("tradingagents.dataflows.akshare_interface._require_akshare")
    def test_cn_market_flow_output_is_execution_focused(self, mock_require_akshare):
        class MockAkshare:
            @staticmethod
            def stock_individual_fund_flow(stock, market):
                import pandas as pd

                return pd.DataFrame(
                    [
                        {"日期": "2026-05-05", "收盘价": 25.1, "涨跌幅": 4.2, "主力净流入-净额": 1230000, "主力净流入-净占比": 11.2}
                    ]
                )

        mock_require_akshare.return_value = MockAkshare()

        result = get_akshare_cn_market_flow("300750.SZ")

        self.assertIn("execution-risk, liquidity, and main-force flow proxy", result)
        self.assertIn("MainForceNetInflow", result)


if __name__ == "__main__":
    unittest.main()
