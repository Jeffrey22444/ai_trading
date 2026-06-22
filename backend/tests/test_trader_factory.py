import pytest

from trading import factory


class StubTrader:
    pass


def stub_trader_class():
    return StubTrader


@pytest.fixture(autouse=True)
def reset_factory():
    factory.reset_trader()
    yield
    factory.reset_trader()


def test_factory_selects_hyperliquid(monkeypatch):
    monkeypatch.setattr(factory.config.exchange, "name", "hyperliquid")
    monkeypatch.setattr(factory, "HyperliquidTrader", StubTrader)

    assert isinstance(factory.get_trader(), StubTrader)


def test_factory_rejects_unknown_exchange(monkeypatch):
    monkeypatch.setattr(factory.config.exchange, "name", "unknown")

    with pytest.raises(ValueError, match="仅支持 Hyperliquid"):
        factory.get_trader()
