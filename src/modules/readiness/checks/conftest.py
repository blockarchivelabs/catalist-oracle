import pytest

from src.modules.accounting.accounting import Accounting
from src.modules.ejector.ejector import Ejector
from src.modules.readiness.ReadinessModule import Web3Plugin
from src.typings import EpochNumber, SlotNumber, BlockRoot
from src.utils.blockstamp import build_blockstamp
from src.utils.slot import get_reference_blockstamp


@pytest.fixture()
def web3(request):
    return next(filter(lambda x: isinstance(x, Web3Plugin), request.config.pluginmanager.get_plugins())).web3


@pytest.fixture
def accounting(web3):
    return Accounting(web3)


@pytest.fixture
def ejector(web3):
    return Ejector(web3)


@pytest.fixture(params=[pytest.param("finalized_blockstamp", id="Finalized blockstamp"),
                        pytest.param("blockstamp_frame_ago", id="Blockstamp frame ago")])
def blockstamp(request):
    return request.getfixturevalue(request.param)


@pytest.fixture
def finalized_blockstamp(accounting, web3):
    block_root = BlockRoot(web3.cc.get_block_root('finalized').root)
    block_details = web3.cc.get_block_details(block_root)
    bs = build_blockstamp(block_details)
    chain_config = accounting.get_chain_config(bs)
    return get_reference_blockstamp(
        web3.cc,
        bs.slot_number,
        ref_epoch=EpochNumber(bs.slot_number // chain_config.slots_per_epoch),
        last_finalized_slot_number=bs.slot_number
    )


@pytest.fixture
def blockstamp_frame_ago(web3, finalized_blockstamp, accounting):
    frame_config = accounting.get_frame_config(finalized_blockstamp)
    chain_config = accounting.get_chain_config(finalized_blockstamp)
    slots_per_frame = frame_config.epochs_per_frame * chain_config.slots_per_epoch
    last_report_ref_slot = SlotNumber(finalized_blockstamp.slot_number - slots_per_frame)

    return get_reference_blockstamp(
        web3.cc,
        last_report_ref_slot,
        ref_epoch=EpochNumber(last_report_ref_slot // chain_config.slots_per_epoch),
        last_finalized_slot_number=finalized_blockstamp.slot_number
    )


def pytest_collection_modifyitems(items):
    """Sort tests by finalized blockstamp first."""
    items.sort(key=lambda x: "Finalized blockstamp" in x.nodeid, reverse=True)


def pytest_report_teststatus(report, config):
    if report.when == "call":
        if report.passed:
            return "passed", "P", "✅ Checked"
        if report.failed:
            return "failed", "F", "❌ Failed"
        if report.skipped:
            return "skipped", "S", "Skipped"
    return None


def pytest_runtest_makereport(item, call):
    """Print test name before running it."""
    if call.when == "setup":
        print(f"\n    >> {item.obj.__doc__}... ", end="")
