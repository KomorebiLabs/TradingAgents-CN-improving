import os
import warnings

os.environ.setdefault("PYTHONUTF8", "1")

# Suppress noisy third-party library warnings
# 1. py_mini_racer: pkg_resources deprecation (third-party issue)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)
# 2. akshare: "正在下载数据，请稍等" warning during data fetching
warnings.filterwarnings("ignore", message="正在下载数据，请稍等", category=UserWarning)

__version__ = "2.0.0"
