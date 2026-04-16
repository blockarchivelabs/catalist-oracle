"""Simple tests for the consensus client responses validity."""
from unittest.mock import Mock

import pytest

from src.providers.consensus.client import ConsensusClient
from src.providers.http_provider import NotOkResponse
from src.providers.consensus.typings import Validator
from src.typings import SlotNumber
from src.utils.blockstamp import build_blockstamp
from src.variables import CONSENSUS_CLIENT_URI
from tests.factory.blockstamp import BlockStampFactory


@pytest.fixture
def consensus_client():
    return ConsensusClient(CONSENSUS_CLIENT_URI, 5 * 60, 5, 5)


@pytest.mark.integration
def test_get_block_root(consensus_client: ConsensusClient):
    block_root = consensus_client.get_block_root('head')
    assert len(block_root.root) == 66


@pytest.mark.integration
def test_get_block_details(consensus_client: ConsensusClient, web3):
    root = consensus_client.get_block_root('head').root
    block_details = consensus_client.get_block_details(root)
    assert block_details


@pytest.mark.integration
def test_get_validators(consensus_client: ConsensusClient):
    root = consensus_client.get_block_root('finalized').root
    block_details = consensus_client.get_block_details(root)
    blockstamp = build_blockstamp(block_details)

    validators: list[Validator] = consensus_client.get_validators(blockstamp)
    assert validators

    validator = validators[0]
    validator_by_pub_key = consensus_client.get_validators_no_cache(blockstamp, pub_keys=validator.validator.pubkey)
    assert validator_by_pub_key[0] == validator


@pytest.mark.unit
def test_get_returns_nor_dict_nor_list(consensus_client: ConsensusClient):
    consensus_client._get_without_fallbacks = Mock(return_value=(1, None))
    bs = BlockStampFactory.build()

    raises = pytest.raises(ValueError, match='Expected (mapping|list) response')

    with raises:
        consensus_client.get_config_spec()

    with raises:
        consensus_client.get_genesis()

    with raises:
        consensus_client.get_block_root('head')

    with raises:
        consensus_client.get_block_header(SlotNumber(0))

    with raises:
        consensus_client.get_block_details(SlotNumber(0))

    with raises:
        consensus_client.get_validators_no_cache(bs)

    with raises:
        consensus_client._get_validators_with_prysm(bs)

    with raises:
        consensus_client._get_chain_id_with_provider(0)


@pytest.mark.unit
def test_get_validators_fallback_to_slot_on_state_not_found(consensus_client: ConsensusClient):
    blockstamp = BlockStampFactory.build()
    validator_response = [{
        'index': '1',
        'balance': '32000000000',
        'status': 'active_ongoing',
        'validator': {
            'pubkey': '0x' + '11' * 48,
            'withdrawal_credentials': '0x' + '22' * 32,
            'effective_balance': '32000000000',
            'slashed': False,
            'activation_eligibility_epoch': '0',
            'activation_epoch': '0',
            'exit_epoch': '18446744073709551615',
            'withdrawable_epoch': '18446744073709551615',
        }
    }]

    consensus_client._get = Mock(side_effect=[  # pylint: disable=protected-access
        NotOkResponse(
            'State not found',
            status=404,
            text='{"message":"State not found","code":404}',
        )
    ])
    consensus_client._get_validators_with_prysm = Mock(return_value=validator_response)  # pylint: disable=protected-access

    validators = consensus_client.get_validators_no_cache(blockstamp)

    assert len(validators) == 1
    assert validators[0].validator.pubkey == validator_response[0]['validator']['pubkey']
    consensus_client._get_validators_with_prysm.assert_called_once_with(blockstamp, None)  # pylint: disable=protected-access
