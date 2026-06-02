"""Entry point: python -m tradingagents.commands.report"""

from tradingagents.commands.report import view_report

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/"
    view_report(path)
