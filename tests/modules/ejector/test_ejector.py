from typing import Iterable, Iterator, cast
from unittest.mock import Mock

import pytest

from src.constants import MAX_EFFECTIVE_BALANCE
from src.modules.ejector import ejector as ejector_module
from src.modules.ejector.ejector import Ejector, EjectorProcessingState
from src.modules.ejector.ejector import logger as ejector_logger
from src.modules.submodules.typings import ChainConfig
from src.services.exit_order import (
    ValidatorToExitIterator,
    ValidatorToExitIteratorConfig,
)
from src.typings import BlockStamp, ReferenceBlockStamp
from src.web3py.extensions.contracts import LidoContracts
from src.web3py.extensions.lido_validators import NodeOperatorId, StakingModuleId
from src.web3py.typings import Web3
from tests.factory.blockstamp import BlockStampFactory, ReferenceBlockStampFactory
from tests.factory.configs import ChainConfigFactory
from tests.factory.no_registry import LidoValidatorFactory


@pytest.fixture(autouse=True)
def silence_logger() -> None:
    ejector_logger.disabled = True


@pytest.fixture()
def chain_config():
    return cast(ChainConfig, ChainConfigFactory.build())


@pytest.fixture()
def blockstamp() -> BlockStamp:
    return cast(BlockStamp, BlockStampFactory.build())


@pytest.fixture()
def ref_blockstamp() -> ReferenceBlockStamp:
    return cast(ReferenceBlockStamp, ReferenceBlockStampFactory.build())


@pytest.fixture()
def ejector(web3: Web3, contracts: LidoContracts) -> Ejector:
    mod = object.__new__(Ejector)
    mod.report_contract = web3.lido_contracts.validators_exit_bus_oracle
    mod.validators_state_service = Mock()
    mod.prediction_service = Mock()
    super(Ejector, mod).__init__(web3)
    return mod


@pytest.fixture()
def validator_to_exit_it(
    web3,
    ref_blockstamp: ReferenceBlockStamp,
    chain_config: ChainConfig,
) -> ValidatorToExitIterator:
    it = Mock(spec=ValidatorToExitIterator)
    it.w3 = web3
    it.blockstamp = ref_blockstamp
    it.c_conf = chain_config
    it.left_queue_count = 0
    it.v_conf = Mock(spec=ValidatorToExitIteratorConfig)
    it.v_conf.max_validators_to_exit = 100
    return it


@pytest.mark.unit
def test_ejector_execute_module(ejector: Ejector, blockstamp: BlockStamp) -> None:
    ejector.get_blockstamp_for_report = Mock(return_value=None)
    assert not ejector.execute_module(
        last_finalized_blockstamp=blockstamp
    ), "execute_module should return False"
    ejector.get_blockstamp_for_report.assert_called_once_with(blockstamp)

    ejector.get_blockstamp_for_report = Mock(return_value=blockstamp)
    ejector.process_report = Mock(return_value=True)
    assert ejector.execute_module(
        last_finalized_blockstamp=blockstamp
    ), "execute_module should return True"
    ejector.get_blockstamp_for_report.assert_called_once_with(blockstamp)
    ejector.process_report.assert_called_once_with(blockstamp)


@pytest.mark.unit
def test_ejector_build_report(ejector: Ejector, ref_blockstamp: ReferenceBlockStamp) -> None:
    ejector.get_validators_to_eject = Mock(return_value=[])
    result = ejector.build_report(ref_blockstamp)
    _, ref_slot, _, _, data = result
    assert ref_slot == ref_blockstamp.ref_slot, "Unexpected blockstamp.ref_slot"
    assert data == b"", "Unexpected encoded data"

    ejector.build_report(ref_blockstamp)
    ejector.get_validators_to_eject.assert_called_once_with(ref_blockstamp)


class TestGetValidatorsToEject:
    @pytest.fixture(autouse=True)
    def mock_validator_to_exit_it(
        self,
        validator_to_exit_it: ValidatorToExitIterator,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Iterator:
        with monkeypatch.context() as m:

            def _validator_to_exit_iter(*args, **kwargs):
                return validator_to_exit_it

            m.setattr(
                ejector_module,
                "ValidatorToExitIterator",
                Mock(side_effect=_validator_to_exit_iter),
            )

            yield

    @pytest.mark.unit
    def test_should_not_report_on_paused(
        self,
        ejector: Ejector,
        ref_blockstamp: ReferenceBlockStamp,
        validator_to_exit_it: ValidatorToExitIterator,
        chain_config: ChainConfig,
    ) -> None:
        ejector.get_chain_config = Mock(return_value=chain_config)
        validator_to_exit_it.v_conf.max_validators_to_exit = 0
        result = ejector.get_validators_to_eject(ref_blockstamp)
        assert result == [], "Should not report on paused"

    @pytest.mark.unit
    def test_should_not_report_on_no_withdraw_requests(
        self,
        ejector: Ejector,
        ref_blockstamp: ReferenceBlockStamp,
        validator_to_exit_it: ValidatorToExitIterator,
        chain_config: ChainConfig,
    ) -> None:
        ejector.get_chain_config = Mock(return_value=chain_config)
        ejector.get_total_unfinalized_withdrawal_requests_amount = Mock(return_value=0)
        validator_to_exit_it.v_conf.max_validators_to_exit = 100
        result = ejector.get_validators_to_eject(ref_blockstamp)
        assert result == [], "Should not report on no withdraw requests"

    @pytest.mark.unit
    @pytest.mark.usefixtures("consensus_client")
    def test_no_validators_to_eject(
        self,
        ejector: Ejector,
        ref_blockstamp: ReferenceBlockStamp,
        validator_to_exit_it: ValidatorToExitIterator,
        chain_config: ChainConfig,
    ):
        validator_to_exit_it.__iter__ = Mock(return_value=iter([]))

        ejector.get_chain_config = Mock(return_value=chain_config)
        ejector.get_total_unfinalized_withdrawal_requests_amount = Mock(
            return_value=100
        )
        ejector.prediction_service.get_rewards_per_epoch = Mock(return_value=1)
        ejector._get_sweep_delay_in_epochs = Mock(return_value=1)
        ejector._get_total_balance = Mock(return_value=50)
        ejector.validators_state_service.get_recently_requested_but_not_exited_validators = Mock(
            return_value=[]
        )

        result = ejector.get_validators_to_eject(ref_blockstamp)
        assert result == [], "Unexpected validators to eject"

    # NOTE: not sure if this test makes sense
    # @pytest.mark.unit
    # @pytest.mark.usefixtures("consensus_client")
    # def test_simple(
    #     self,
    #     ejector: Ejector,
    #     ref_blockstamp: ReferenceBlockStamp,
    #     validator_to_exit_it: ValidatorToExitIterator,
    #     chain_config: ChainConfig,
    # ):
    #     def _lido_validator(index: int):
    #         return Mock(index=index, validator=Mock(pubkey="0x00"))
    #
    #     validators = [
    #         ((StakingModuleId(0), NodeOperatorId(1)), _lido_validator(0)),
    #         ((StakingModuleId(0), NodeOperatorId(3)), _lido_validator(1)),
    #         ((StakingModuleId(0), NodeOperatorId(5)), _lido_validator(2)),
    #     ]
    #
    #     validator_to_exit_it.__iter__ = Mock(return_value=iter(validators))
    #
    #     ejector.get_chain_config = Mock(return_value=chain_config)
    #     ejector.get_total_unfinalized_withdrawal_requests_amount = Mock(
    #         return_value=200
    #     )
    #     ejector.prediction_service.get_rewards_per_epoch = Mock(return_value=1)
    #     ejector._get_sweep_delay_in_epochs = Mock(return_value=ref_blockstamp.ref_epoch)
    #     ejector._get_total_balance = Mock(return_value=100)
    #     ejector.validators_state_service.get_recently_requested_but_not_exited_validators = Mock(
    #         return_value=[]
    #     )
    #
    #     ejector._get_withdrawable_lido_validators = Mock(return_value=0)
    #     ejector._get_predicted_withdrawable_epoch = Mock(return_value=50)
    #     ejector._get_predicted_withdrawable_balance = Mock(return_value=50)
    #
    #     result = ejector.get_validators_to_eject(ref_blockstamp)
    #     assert result == [validators[0]], "Unexpected validators to eject"


@pytest.mark.unit
@pytest.mark.usefixtures("contracts")
def test_get_unfinalized_steth(ejector: Ejector, blockstamp: BlockStamp) -> None:
    result = ejector.get_total_unfinalized_withdrawal_requests_amount(blockstamp)
    assert result == 2181000000000000000, "Unexpected unfinalized stETH"


@pytest.mark.unit
def test_compute_activation_exit_epoch(
    ejector: Ejector,
    ref_blockstamp: ReferenceBlockStamp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as m:
        m.setattr(ejector_module, "MAX_SEED_LOOKAHEAD", 17)
        result = ejector.compute_activation_exit_epoch(ref_blockstamp)
        assert result == 3546 + 17 + 1, "Unexpected activation exit epoch"


@pytest.mark.unit
def test_is_main_data_submitted(ejector: Ejector, blockstamp: BlockStamp) -> None:
    ejector._get_processing_state = Mock(return_value=Mock(data_submitted=True))
    assert (
        ejector.is_main_data_submitted(blockstamp) == True
    ), "Unexpected is_main_data_submitted result"
    ejector._get_processing_state.assert_called_once_with(blockstamp)


@pytest.mark.unit
def test_is_contract_reportable(ejector: Ejector, blockstamp: BlockStamp) -> None:
    ejector.is_main_data_submitted = Mock(return_value=False)
    assert (
        ejector.is_contract_reportable(blockstamp) == True
    ), "Unexpected is_contract_reportable result"
    ejector.is_main_data_submitted.assert_called_once_with(blockstamp)


@pytest.mark.unit
def test_get_predicted_withdrawable_epoch(
    ejector: Ejector, ref_blockstamp: ReferenceBlockStamp
) -> None:
    ejector._get_latest_exit_epoch = Mock(return_value=[1, 32])
    ejector._get_churn_limit = Mock(return_value=2)
    result = ejector._get_predicted_withdrawable_epoch(ref_blockstamp, 2)
    assert result == 3824, "Unexpected predicted withdrawable epoch"


@pytest.mark.unit
@pytest.mark.usefixtures("consensus_client", "lido_validators")
def test_get_withdrawable_lido_validators(
    ejector: Ejector,
    ref_blockstamp: ReferenceBlockStamp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ejector.w3.lido_validators.get_lido_validators = Mock(
        return_value=[
            LidoValidatorFactory.build(balance="0"),
            LidoValidatorFactory.build(balance="0"),
            LidoValidatorFactory.build(balance="31"),
            LidoValidatorFactory.build(balance="42"),
        ]
    )

    with monkeypatch.context() as m:
        m.setattr(
            ejector_module,
            "is_fully_withdrawable_validator",
            Mock(side_effect=lambda v, _: int(v.balance) > 32),
        )

        result = ejector._get_withdrawable_lido_validators(ref_blockstamp, 42)
        assert result == 42 * 10**9, "Unexpected withdrawable amount"

        ejector._get_withdrawable_lido_validators(ref_blockstamp, 42)
        ejector.w3.lido_validators.get_lido_validators.assert_called_once()


@pytest.mark.unit
def test_get_predicted_withdrawable_balance(ejector: Ejector) -> None:
    validator = LidoValidatorFactory.build(balance="0")
    result = ejector._get_predicted_withdrawable_balance(validator)
    assert result == 0, "Expected zero"

    validator = LidoValidatorFactory.build(balance="42")
    result = ejector._get_predicted_withdrawable_balance(validator)
    assert result == 42 * 10**9, "Expected validator's balance in gwei"

    validator = LidoValidatorFactory.build(balance=str(MAX_EFFECTIVE_BALANCE + 1))
    result = ejector._get_predicted_withdrawable_balance(validator)
    assert result == MAX_EFFECTIVE_BALANCE * 10**9, "Expect MAX_EFFECTIVE_BALANCE"


@pytest.mark.unit
@pytest.mark.usefixtures("consensus_client")
def test_get_sweep_delay_in_epochs(
    ejector: Ejector,
    ref_blockstamp: ReferenceBlockStamp,
    chain_config: ChainConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ejector.w3.cc.get_validators = Mock(
        return_value=[
            LidoValidatorFactory.build(),
        ]
        * 1024
    )

    ejector.get_chain_config = Mock(return_value=chain_config)

    with monkeypatch.context() as m:
        m.setattr(
            ejector_module,
            "is_partially_withdrawable_validator",
            Mock(return_value=False),
        )
        m.setattr(
            ejector_module,
            "is_fully_withdrawable_validator",
            Mock(return_value=False),
        )

        # no validators at all
        result = ejector._get_sweep_delay_in_epochs(ref_blockstamp)
        assert result == 0, "Unexpected sweep delay in epochs"

    with monkeypatch.context() as m:
        m.setattr(
            ejector_module,
            "is_partially_withdrawable_validator",
            Mock(return_value=False),
        )
        m.setattr(
            ejector_module,
            "is_fully_withdrawable_validator",
            Mock(return_value=True),
        )

        # all 1024 validators
        result = ejector._get_sweep_delay_in_epochs(ref_blockstamp)
        assert result == 1, "Unexpected sweep delay in epochs"


@pytest.mark.unit
@pytest.mark.usefixtures("contracts")
def test_get_reserved_buffer(ejector: Ejector, blockstamp: BlockStamp) -> None:
    result = ejector._get_reserved_buffer(blockstamp)
    assert result == 31 * 10**18, "Unexpected reserved buffer"


@pytest.mark.usefixtures("contracts")
def test_get_total_balance(ejector: Ejector, blockstamp: BlockStamp) -> None:
    ejector.w3.lido_contracts.get_withdrawal_balance = Mock(return_value=3)
    ejector.w3.lido_contracts.get_el_vault_balance = Mock(return_value=17)
    ejector._get_reserved_buffer = Mock(return_value=1)

    result = ejector._get_total_balance(blockstamp)
    assert result == 21, "Unexpected total balance"

    ejector.w3.lido_contracts.get_withdrawal_balance.assert_called_once_with(blockstamp)
    ejector.w3.lido_contracts.get_el_vault_balance.assert_called_once_with(blockstamp)
    ejector._get_reserved_buffer.assert_called_once_with(blockstamp)


class TestChurnLimit:
    """_get_churn_limit tests"""

    @pytest.fixture(autouse=True)
    def mock_is_active_validator(self, monkeypatch: pytest.MonkeyPatch) -> Iterable:
        with monkeypatch.context() as m:
            m.setattr(
                ejector_module,
                "is_active_validator",
                Mock(side_effect=lambda v, _: bool(v)),
            )
            yield

    @pytest.mark.unit
    @pytest.mark.usefixtures("consensus_client")
    def test_get_churn_limit_no_validators(self, ejector: Ejector) -> None:
        ejector.w3.cc.get_validators = Mock(return_value=[])
        result = ejector._get_churn_limit(ref_blockstamp)
        assert (
            result == ejector_module.MIN_PER_EPOCH_CHURN_LIMIT
        ), "Unexpected churn limit"

    @pytest.mark.unit
    @pytest.mark.usefixtures("consensus_client")
    def test_get_churn_limit_validators_less_than_min_churn(
        self,
        ejector: Ejector,
        ref_blockstamp: ReferenceBlockStamp,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with monkeypatch.context() as m:
            ejector.w3.cc.get_validators = Mock(return_value=[1, 1, 0])
            m.setattr(ejector_module, "MIN_PER_EPOCH_CHURN_LIMIT", 4)
            m.setattr(ejector_module, "CHURN_LIMIT_QUOTIENT", 1)
            result = ejector._get_churn_limit(ref_blockstamp)
            assert result == 4, "Unexpected churn limit"
            ejector.w3.cc.get_validators.assert_called_once_with(ref_blockstamp)

    @pytest.mark.unit
    @pytest.mark.usefixtures("consensus_client")
    def test_get_churn_limit_basic(
        self,
        ejector: Ejector,
        ref_blockstamp: ReferenceBlockStamp,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with monkeypatch.context() as m:
            ejector.w3.cc.get_validators = Mock(return_value=[1] * 99)
            m.setattr(ejector_module, "MIN_PER_EPOCH_CHURN_LIMIT", 0)
            m.setattr(ejector_module, "CHURN_LIMIT_QUOTIENT", 2)
            result = ejector._get_churn_limit(ref_blockstamp)
            assert result == 49, "Unexpected churn limit"
            ejector._get_churn_limit(ref_blockstamp)
            ejector.w3.cc.get_validators.assert_called_once_with(ref_blockstamp)


@pytest.mark.unit
def test_get_processing_state(ejector: Ejector, blockstamp: BlockStamp) -> None:
    result = ejector._get_processing_state(blockstamp)
    assert isinstance(
        result, EjectorProcessingState
    ), "Unexpected processing state response"


@pytest.mark.unit
@pytest.mark.usefixtures("consensus_client")
def test_get_latest_exit_epoch(
    ejector: Ejector, blockstamp: BlockStamp, monkeypatch: pytest.MonkeyPatch
) -> None:
    ejector.w3.cc.get_validators = Mock(
        return_value=[
            Mock(validator=Mock(exit_epoch=999)),
            Mock(validator=Mock(exit_epoch=42)),
            Mock(validator=Mock(exit_epoch=42)),
            Mock(validator=Mock(exit_epoch=1)),
        ]
    )

    with monkeypatch.context() as m:
        m.setattr(ejector_module, "FAR_FUTURE_EPOCH", 999)

        (max_epoch, count) = ejector._get_latest_exit_epoch(blockstamp)
        assert count == 2, "Unexpected count of exiting validators"
        assert max_epoch == 42, "Unexpected max epoch"

        ejector._get_latest_exit_epoch(blockstamp)
        ejector.w3.cc.get_validators.assert_called_once_with(blockstamp)
