"""
The UI/API "experiment" setup must be exactly the evaluation harness configuration
(experiments/run_experiments.py), so the comparison shown in the app reproduces the
Chapter 4 table. The "live" setup is the interactive map configuration and must differ.

Run:  pytest -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SimConfig
from app.model import FloodResponseModel
from app import scenario as SC


def test_experiment_setup_matches_harness_exactly():
    for strat in ("random", "ai_optimised"):
        harness = FloodResponseModel(SimConfig(grid_size=36, seed=3, strategy=strat)).run().to_dict()
        api = SC.build_model(setup="experiment", seed=3, strategy=strat).run().to_dict()
        assert api == harness, f"experiment setup drifted from the harness for {strat}"


def test_live_setup_is_a_different_configuration():
    exp = SC.build_model(setup="experiment", seed=3, strategy="random").run().to_dict()
    live = SC.build_model(setup="live", region="lokoja", seed=3, strategy="random").run().to_dict()
    assert exp != live, "live and experiment setups should not coincide"
