"""Реестр стратегий: подключение через config.yaml без правки кода."""
STRATEGY_REGISTRY: dict[str, type] = {}


def register_strategy(name: str):
    def deco(cls):
        cls.name = name
        STRATEGY_REGISTRY[name] = cls
        return cls
    return deco


def build_strategies(cfg: dict) -> list:
    """Создаёт включённые стратегии из конфига."""
    import strategies  # noqa: F401 — импорт регистрирует классы
    out = []
    for s in cfg.get("strategies", []):
        if not s.get("enabled", True):
            continue
        name = s["name"]
        if name not in STRATEGY_REGISTRY:
            raise KeyError(f"Стратегия '{name}' не зарегистрирована. Есть: {list(STRATEGY_REGISTRY)}")
        out.append(STRATEGY_REGISTRY[name](params=s.get("params", {}), weight=s.get("weight", 1.0)))
    return out
