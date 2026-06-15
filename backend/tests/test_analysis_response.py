from agent.nodes.analysis_node import parse_json_response


def test_hold_decision_accepts_null_optional_trade_fields():
    decision = parse_json_response(
        """
        {
          "symbol_decisions": [
            {
              "symbol": "BTC",
              "action": "HOLD",
              "reasoning": "Signals conflict, wait.",
              "position_size_usd": null,
              "stop_loss_price": null,
              "take_profit_price": null
            }
          ],
          "overall_summary": "Wait for confirmation."
        }
        """
    )

    btc = decision.symbol_decisions[0]
    assert btc.action == "HOLD"
    assert btc.reasoning == "Signals conflict, wait."
    assert btc.position_size_usd == 0.0
