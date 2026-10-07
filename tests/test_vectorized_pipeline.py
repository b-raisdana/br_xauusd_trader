from application.xauusd_trading_strategy_1_vector.reporting import print_strategy_summary


def test_summary_counts_candidates_not_non_null_containers(capsys, tmp_path):
    from test_vectorized_tick_separation import Zones, inputs

    from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
    from infrastructure.result_processing.io import ResultFilesManifest

    ticks, candles = inputs()
    day = ticks.broker_day.iloc[0]
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        manifest.save_daily_ticks(day, ticks).save_daily_candles(day, candles)
        VectorizedXauUsdStrategy(Zones()).process_tick_data(manifest)
        expected = manifest.read_daily_signals(day).family.eq(0).sum()
        print_strategy_summary(manifest)
        assert f"Breakout signals: {expected}" in capsys.readouterr().out
    finally:
        manifest.close()
