from unittest.mock import Mock

import pytest

from src.web3py.extensions.catalist_validators import CountOfKeysDiffersException, CatalistValidatorsProvider
from tests.factory.blockstamp import ReferenceBlockStampFactory
from tests.factory.no_registry import (
    CatalistKeyFactory,
    CatalistValidatorFactory,
    NodeOperatorFactory,
    StakingModuleFactory,
    ValidatorFactory,
)

blockstamp = ReferenceBlockStampFactory.build()


@pytest.mark.unit
def test_get_catalist_validators(web3, catalist_validators, contracts):
    validators = ValidatorFactory.batch(30)
    catalist_keys = CatalistKeyFactory.generate_for_validators(validators[:10])
    catalist_keys.extend(CatalistKeyFactory.batch(10))

    web3.cc.get_validators = Mock(return_value=validators)
    web3.kac.get_used_catalist_keys = Mock(return_value=catalist_keys)

    catalist_validators = web3.catalist_validators.get_catalist_validators(blockstamp)

    assert len(catalist_validators) == 10
    assert len(catalist_keys) != len(catalist_validators)
    assert len(validators) != len(catalist_validators)

    for v in catalist_validators:
        assert v.catalist_id.key == v.validator.pubkey


@pytest.mark.unit
def test_kapi_has_lesser_keys_than_deposited_validators_count(web3, catalist_validators, contracts):
    validators = ValidatorFactory.batch(10)
    catalist_keys = []

    web3.cc.get_validators = Mock(return_value=validators)
    web3.kac.get_used_catalist_keys = Mock(return_value=catalist_keys)

    with pytest.raises(CountOfKeysDiffersException):
        web3.catalist_validators.get_catalist_validators(blockstamp)


@pytest.mark.unit
def test_get_node_operators(web3, catalist_validators, contracts):
    node_operators = web3.catalist_validators.get_catalist_node_operators(blockstamp)

    assert len(node_operators) == 2

    registry_map = {
        0: '0xB099EC462e42Ac2570fB298B42083D7A499045D8',
        1: '0xB099EC462e42Ac2570fB298B42083D7A499045D8',
    }

    for no in node_operators:
        assert no.staking_module.staking_module_address == registry_map[no.id]


@pytest.mark.unit
def test_get_catalist_validators_by_node_operator(web3, catalist_validators, contracts):
    no_validators = web3.catalist_validators.get_catalist_validators_by_node_operators(blockstamp)

    assert len(no_validators.keys()) == 2
    assert len(no_validators[(1, 0)]) == 10
    assert len(no_validators[(1, 1)]) == 7


@pytest.mark.unit
@pytest.mark.usefixtures('catalist_validators', 'contracts')
def test_get_catalist_validators_by_node_operator_inconsistent(web3, caplog):
    validator = CatalistValidatorFactory.build()
    web3.catalist_validators.get_catalist_validators = Mock(return_value=[validator])
    web3.catalist_validators.get_catalist_node_operators = Mock(
        return_value=[
            NodeOperatorFactory.build(
                staking_module=StakingModuleFactory.build(
                    staking_module_address=validator.catalist_id.moduleAddress,
                ),
            ),
        ]
    )

    web3.catalist_validators.get_catalist_validators_by_node_operators(blockstamp)
    assert "not exist in staking router" in caplog.text
