"""Tests for StructuredMemory."""

import unittest
from tradingagents.agents.utils.memory import StructuredMemory, FinancialSituationMemory, OrchestrationMemoryEntry


class StructuredMemoryTests(unittest.TestCase):
    """Tests for the StructuredMemory class."""

    def test_basic_add_and_retrieve(self):
        """Test basic add and retrieve functionality."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
        ])

        results = memory.get_memories("Situation A", n_matches=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["recommendation"], "Recommendation A")

    def test_add_with_metadata(self):
        """Test adding situations with metadata."""
        memory = StructuredMemory("test_memory")

        metadata = [
            {"segment": "cn_main_board_equity", "final_route": "portfolio"},
            {"segment": "cn_chinext_equity", "final_route": "portfolio_handoff"},
        ]

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
        ], metadata=metadata)

        results = memory.get_memories("Situation", n_matches=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["metadata"]["segment"], "cn_main_board_equity")
        self.assertEqual(results[1]["metadata"]["segment"], "cn_chinext_equity")

    def test_filter_by_field(self):
        """Test filtering by metadata field."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"segment": "cn_main_board_equity"},
            {"segment": "cn_chinext_equity"},
            {"segment": "cn_main_board_equity"},
        ])

        results = memory.get_memories("Situation", n_matches=10, filters={"segment": "cn_main_board_equity"})
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result["metadata"]["segment"], "cn_main_board_equity")

    def test_get_by_segment(self):
        """Test getting all memories for a specific segment."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"segment": "cn_main_board_equity"},
            {"segment": "cn_chinext_equity"},
            {"segment": "cn_main_board_equity"},
        ])

        results = memory.get_all_by_segment("cn_main_board_equity")
        self.assertEqual(len(results), 2)

    def test_get_by_route(self):
        """Test getting all memories for a specific route."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
        ], metadata=[
            {"final_route": "portfolio"},
            {"final_route": "portfolio_handoff"},
        ])

        results = memory.get_all_by_route("portfolio")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["recommendation"], "Recommendation A")

    def test_route_statistics(self):
        """Test getting route statistics."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
            ("Situation D", "Recommendation D"),
        ], metadata=[
            {"segment": "cn_main_board_equity", "compression_triggered": True},
            {"segment": "cn_main_board_equity", "compression_triggered": False},
            {"segment": "cn_chinext_equity", "compression_triggered": True},
            {"segment": "cn_chinext_equity", "compression_triggered": True},
        ])

        stats = memory.get_route_statistics()
        self.assertEqual(stats["total_memories"], 4)
        self.assertEqual(stats["segment_distribution"]["cn_main_board_equity"], 2)
        self.assertEqual(stats["segment_distribution"]["cn_chinext_equity"], 2)
        self.assertEqual(stats["compression_stats"]["with_compression"], 3)
        self.assertEqual(stats["compression_stats"]["without_compression"], 1)

    def test_export_and_import(self):
        """Test exporting and importing memories."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
        ], metadata=[
            {"segment": "cn_main_board_equity"},
            {"segment": "cn_chinext_equity"},
        ])

        exported = memory.export_memories()
        self.assertEqual(len(exported), 2)

        memory2 = StructuredMemory("test_memory_2")
        memory2.import_memories(exported)

        results = memory2.get_memories("Situation", n_matches=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["metadata"]["segment"], "cn_main_board_equity")

    def test_clear(self):
        """Test clearing memories."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
        ], metadata=[{"segment": "cn_main_board_equity"}])

        self.assertEqual(len(memory.documents), 1)

        memory.clear()

        self.assertEqual(len(memory.documents), 0)
        self.assertEqual(len(memory.metadata), 0)

    def test_add_situation_single(self):
        """Test adding a single situation."""
        memory = StructuredMemory("test_memory")

        memory.add_situation(
            situation="Situation A",
            recommendation="Recommendation A",
            metadata={"segment": "cn_main_board_equity"},
        )

        results = memory.get_memories("Situation A", n_matches=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["segment"], "cn_main_board_equity")

    def test_structured_index_maintained(self):
        """Test that structured indexes are properly maintained."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"segment": "cn_star", "style_bucket": "growth"},
            {"segment": "cn_star", "style_bucket": "value"},
            {"segment": "cn_chinext", "style_bucket": "growth"},
        ])

        # Check that indexes are built
        self.assertIn("cn_star", memory._structured_index["segment"])
        self.assertIn("cn_chinext", memory._structured_index["segment"])
        self.assertIn("growth", memory._structured_index["style_bucket"])
        self.assertIn("value", memory._structured_index["style_bucket"])

    def test_advanced_filters_list_values(self):
        """Test filtering with list values (OR match)."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"segment": "cn_star"},
            {"segment": "cn_chinext"},
            {"segment": "cn_main_board"},
        ])

        results = memory.get_memories(
            "Situation",
            n_matches=10,
            filters={"segment": ["cn_star", "cn_chinext"]}
        )
        self.assertEqual(len(results), 2)

    def test_advanced_filters_numeric_range(self):
        """Test filtering with numeric range filters."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"compression_rate": 0.2},
            {"compression_rate": 0.5},
            {"compression_rate": 0.8},
        ])

        results = memory.get_memories(
            "Situation",
            n_matches=10,
            filters={"compression_rate_min": 0.3, "compression_rate_max": 0.7}
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["compression_rate"], 0.5)

    def test_advanced_filters_date_range(self):
        """Test filtering with date range filters."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"trade_date": "2025-01-15"},
            {"trade_date": "2025-06-15"},
            {"trade_date": "2025-12-15"},
        ])

        results = memory.get_memories(
            "Situation",
            n_matches=10,
            filters={"trade_date_after": "2025-03-01", "trade_date_before": "2025-09-01"}
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["trade_date"], "2025-06-15")

    def test_advanced_filters_list_field_contains(self):
        """Test filtering with list field contains."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"skills": ["cn_macro_news", "cn_tech_news"]},
            {"skills": ["cn_real_estate_news"]},
            {"skills": ["cn_macro_news"]},
        ])

        results = memory.get_memories(
            "Situation",
            n_matches=10,
            filters={"skills": "cn_macro_news"}
        )
        self.assertEqual(len(results), 2)

    def test_get_route_statistics_by_segment(self):
        """Test getting route statistics filtered by segment."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
            ("Situation D", "Recommendation D"),
        ], metadata=[
            {"segment": "cn_star", "final_route": "direct", "compression_rate": 0.1, "decision_quality": "good"},
            {"segment": "cn_star", "final_route": "direct", "compression_rate": 0.2, "decision_quality": "good"},
            {"segment": "cn_chinext", "final_route": "handoff", "compression_rate": 0.5, "decision_quality": "neutral"},
            {"segment": "cn_chinext", "final_route": "handoff", "compression_rate": 0.6, "decision_quality": "poor"},
        ])

        stats = memory.get_route_statistics_by_segment(segment="cn_star")
        self.assertEqual(stats["total_memories"], 2)
        self.assertEqual(stats["segment"], "cn_star")
        self.assertEqual(stats["route_distribution"]["direct"], 2)
        self.assertAlmostEqual(stats["avg_compression_rate"], 0.15, places=5)

    def test_get_pattern_outcome_correlation(self):
        """Test getting pattern-outcome correlation."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
            ("Situation D", "Recommendation D"),
        ], metadata=[
            {"compression_triggered": False, "decision_quality": "good"},
            {"compression_triggered": False, "decision_quality": "good"},
            {"compression_triggered": True, "decision_quality": "poor"},
            {"compression_triggered": True, "decision_quality": "poor"},
        ])

        correlation = memory.get_pattern_outcome_correlation("direct")
        self.assertEqual(correlation["pattern_type"], "direct")
        self.assertEqual(correlation["count"], 2)
        self.assertIn("Positive", correlation["correlation"])

    def test_get_recent_memories(self):
        """Test getting recent memories."""
        memory = StructuredMemory("test_memory")

        for i in range(5):
            memory.add_situation(
                situation=f"Situation {i}",
                recommendation=f"Recommendation {i}",
                metadata={"segment": f"segment_{i % 2}"}
            )

        recent = memory.get_recent_memories(n=3)
        self.assertEqual(len(recent), 3)
        # Most recent first
        self.assertEqual(recent[0]["matched_situation"], "Situation 4")
        self.assertEqual(recent[1]["matched_situation"], "Situation 3")
        self.assertEqual(recent[2]["matched_situation"], "Situation 2")

    def test_get_high_performing_routes(self):
        """Test getting high-performing routes."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
            ("Situation C", "Recommendation C"),
        ], metadata=[
            {"decision_quality": "good"},
            {"decision_quality": "neutral"},
            {"decision_quality": "poor"},
        ])

        high_performers = memory.get_high_performing_routes(min_quality="neutral")
        self.assertEqual(len(high_performers), 2)

    def test_clear_with_indexes(self):
        """Test that clear also clears structured indexes."""
        memory = StructuredMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
        ], metadata=[{"segment": "cn_star"}])

        self.assertTrue(len(memory._structured_index["segment"]) > 0)

        memory.clear()

        self.assertEqual(len(memory._structured_index["segment"]), 0)
        self.assertEqual(len(memory.documents), 0)


class OrchestrationMemoryEntrySchemaTests(unittest.TestCase):
    """Tests for the OrchestrationMemoryEntry TypedDict schema."""

    def test_schema_fields_present(self):
        """Test that all expected fields are in the schema."""
        entry: OrchestrationMemoryEntry = {
            "situation": "Test situation",
            "recommendation": "Test recommendation",
            "stage_sequence": ["analyst", "research"],
            "phase_sequence": ["analyst_market"],
            "compression_phases": ["research"],
            "compression_rate": 0.3,
            "segment": "cn_star",
            "style_bucket": "growth",
            "selected_analysts": ["market_analyst"],
            "skills": ["cn_macro_news"],
            "final_route": "direct",
            "final_reason": "Simple query",
            "route_category": "normal",
            "total_events": 10,
            "unique_stages": ["analyst", "research"],
            "bottleneck_stages": [],
            "ticker": "688981",
            "company_name": "Test Company",
            "trade_date": "2025-05-01",
            "created_at": "2025-05-01T10:00:00",
        }
        # Should not raise any type errors
        self.assertEqual(entry["segment"], "cn_star")
        self.assertEqual(entry["compression_rate"], 0.3)

    def test_optional_fields(self):
        """Test that optional fields can be omitted."""
        entry: OrchestrationMemoryEntry = {
            "situation": "Test situation",
            "recommendation": "Test recommendation",
            "segment": "cn_main_board",
        }
        # Optional fields can be None
        self.assertIsNone(entry.get("actual_return"))
        self.assertIsNone(entry.get("decision_quality"))


class BackwardCompatibilityTests(unittest.TestCase):
    """Tests to ensure backward compatibility with FinancialSituationMemory."""

    def test_financial_situation_memory_still_works(self):
        """Ensure FinancialSituationMemory still works as before."""
        memory = FinancialSituationMemory("test_memory")

        memory.add_situations([
            ("Situation A", "Recommendation A"),
            ("Situation B", "Recommendation B"),
        ])

        results = memory.get_memories("Situation A", n_matches=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["recommendation"], "Recommendation A")


if __name__ == "__main__":
    unittest.main()
