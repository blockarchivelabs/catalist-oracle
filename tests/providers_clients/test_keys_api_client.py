"""Simple tests for the keys api client responses validity."""
import pytest

from src.providers.keys.client import KeysAPIClient
from src.typings import BlockStamp
from src.variables import KEYS_API_URI

pytestmark = pytest.mark.integration


@pytest.fixture()
def keys_api_client():
    return KeysAPIClient(KEYS_API_URI)


empty_blockstamp = BlockStamp(
        ref_slot_number=0,
        ref_epoch=0,
        block_root=None,
        state_root=None,
        slot_number='',
        block_hash='',
        block_number=0
    )


def test_get_all_lido_keys(keys_api_client):
    lido_keys = keys_api_client.get_all_lido_keys(empty_blockstamp)
    assert lido_keys

