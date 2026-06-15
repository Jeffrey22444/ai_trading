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


def test_factory_keeps_binance_as_a_supported_exchange(monkeypatch):
    monkeypatch.setattr(factory.config.exchange, "name", "binance_futures")
    monkeypatch.setitem(factory.TRADER_CLASSES, "binance_futures", stub_trader_class)

    trader = factory.get_trader()

    assert isinstance(trader, StubTrader)
    assert factory.get_trader() is trader


def test_factory_selects_hyperliquid(monkeypatch):
    monkeypatch.setattr(factory.config.exchange, "name", "hyperliquid")
    monkeypatch.setitem(factory.TRADER_CLASSES, "hyperliquid", stub_trader_class)

    assert isinstance(factory.get_trader(), StubTrader)


def test_factory_rejects_unknown_exchange(monkeypatch):
    monkeypatch.setattr(factory.config.exchange, "name", "unknown")

    with pytest.raises(ValueError, match="不支持的交易所"):
        factory.get_trader()
