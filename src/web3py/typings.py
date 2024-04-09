from web3 import Web3 as _Web3


from src.web3py.extensions import (
    CatalistContracts,
    TransactionUtils,
    ConsensusClientModule,
    KeysAPIClientModule,
    CatalistValidatorsProvider,
)


class Web3(_Web3):
    catalist_contracts: CatalistContracts
    catalist_validators: CatalistValidatorsProvider
    transaction: TransactionUtils
    cc: ConsensusClientModule
    kac: KeysAPIClientModule
