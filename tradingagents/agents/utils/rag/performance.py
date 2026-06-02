"""
RAG性能优化模块。

提供模型预加载和冷启动优化功能。
"""

import os
import threading
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LoadStatus(Enum):
    """模型加载状态."""
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass
class PreloadConfig:
    """预加载配置."""
    enabled: bool = True
    background: bool = True  # 后台加载
    timeout_seconds: float = 30.0  # 超时时间
    retry_on_failure: bool = True
    max_retries: int = 2


@dataclass
class LoadState:
    """加载状态."""
    status: LoadStatus = LoadStatus.IDLE
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    retries: int = 0

    @property
    def elapsed_seconds(self) -> float:
        """获取加载耗时."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time


class ModelPreloader:
    """
    模型预加载器。

    功能:
    1. 后台异步预加载模型
    2. 启动时预加载，避免首次请求阻塞
    3. 模型状态监控
    """

    _instance: Optional["ModelPreloader"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: PreloadConfig = None):
        if self._initialized:
            return

        self.config = config or PreloadConfig()
        self._state = LoadState()
        self._load_thread: Optional[threading.Thread] = None
        self._callbacks: list[Callable] = []
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "ModelPreloader":
        """获取单例实例."""
        return cls()

    def add_ready_callback(self, callback: Callable[[], None]):
        """添加模型就绪回调."""
        self._callbacks.append(callback)

    def _notify_ready(self):
        """通知所有回调."""
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Callback error: {e}")

    def preload(self, config=None, on_ready: Callable = None) -> bool:
        """
        预加载模型.

        Args:
            config: RAG配置
            on_ready: 加载完成回调

        Returns:
            True 如果成功开始加载
        """
        if self._state.status == LoadStatus.READY:
            logger.info("Model already loaded")
            if on_ready:
                on_ready()
            return True

        if self._state.status == LoadStatus.LOADING:
            logger.info("Model loading in progress")
            if on_ready:
                self._callbacks.append(on_ready)
            return True

        if on_ready:
            self._callbacks.append(on_ready)

        if self.config.background:
            return self._preload_background(config)
        else:
            return self._preload_sync(config)

    def _preload_background(self, config) -> bool:
        """后台异步预加载."""
        self._state = LoadState(status=LoadStatus.LOADING, start_time=time.time())

        def _load():
            try:
                logger.info("Starting background model preload...")
                self._do_load(config)
                self._state.status = LoadStatus.READY
                self._state.end_time = time.time()
                logger.info(f"Model preload completed in {self._state.elapsed_seconds:.2f}s")
                self._notify_ready()
            except Exception as e:
                logger.error(f"Model preload failed: {e}")
                self._state.status = LoadStatus.FAILED
                self._state.error = str(e)
                self._state.end_time = time.time()

        self._load_thread = threading.Thread(target=_load, daemon=True, name="RAG-Preloader")
        self._load_thread.start()
        return True

    def _preload_sync(self, config) -> bool:
        """同步预加载（阻塞）."""
        self._state = LoadState(status=LoadStatus.LOADING, start_time=time.time())
        try:
            self._do_load(config)
            self._state.status = LoadStatus.READY
            self._state.end_time = time.time()
            logger.info(f"Model preload completed in {self._state.elapsed_seconds:.2f}s")
            return True
        except Exception as e:
            logger.error(f"Model preload failed: {e}")
            self._state.status = LoadStatus.FAILED
            self._state.error = str(e)
            return False

    def _do_load(self, config):
        """执行实际加载."""
        from tradingagents.agents.utils.rag import get_cn_news_retriever, CNNewsRetrievalConfig

        rag_config = config or CNNewsRetrievalConfig()
        retriever = get_cn_news_retriever(rag_config)
        return retriever

    def ensure_loaded(self, config=None, timeout: float = None) -> bool:
        """
        确保模型已加载，如未加载则同步加载.

        Args:
            config: RAG配置
            timeout: 超时时间

        Returns:
            True 如果加载成功
        """
        if self._state.status == LoadStatus.READY:
            return True

        if self._state.status == LoadStatus.LOADING:
            # 等待加载完成
            timeout = timeout or self.config.timeout_seconds
            start = time.time()
            while self._state.status == LoadStatus.LOADING:
                if time.time() - start > timeout:
                    logger.warning("Model load timeout")
                    return False
                time.sleep(0.1)
            return self._state.status == LoadStatus.READY

        # 未加载，开始同步加载
        return self._preload_sync(config)

    def get_status(self) -> dict:
        """获取加载状态."""
        return {
            "status": self._state.status.value,
            "elapsed_seconds": self._state.elapsed_seconds,
            "error": self._state.error,
            "is_ready": self._state.status == LoadStatus.READY,
            "is_loading": self._state.status == LoadStatus.LOADING,
        }

    def reset(self):
        """重置状态（用于测试）."""
        with self._lock:
            self._state = LoadState()
            self._callbacks.clear()


def preload_rag_models():
    """
    快捷函数：启动时调用预加载模型.

    用法:
        # app.py 或服务入口
        from tradingagents.agents.utils.rag.performance import preload_rag_models
        preload_rag_models()  # 后台异步加载
    """
    preloader = ModelPreloader.get_instance()

    if not preloader.config.enabled:
        logger.debug("RAG preload disabled")
        return

    env_enabled = os.environ.get("TRADINGAGENTS_RAG_ENABLED", "false").lower()
    if env_enabled not in ("true", "1", "yes"):
        logger.debug("RAG not enabled, skipping preload")
        return

    preloader.preload()
    logger.info("RAG model preload started in background")


def ensure_rag_ready():
    """确保RAG模型已就绪（阻塞式）."""
    preloader = ModelPreloader.get_instance()
    preloader.ensure_loaded()
