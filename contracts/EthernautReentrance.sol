// SPDX-License-Identifier: MIT
pragma solidity ^0.6.0;

contract EthernautReentrance {
    mapping(address => uint256) public balances;

    function donate(address _to) public payable {
        balances[_to] += msg.value;
    }

    function withdraw(uint256 _amount) public {
        if (balances[msg.sender] >= _amount) {
            (bool result, ) = msg.sender.call{value: _amount}("");
            if (result) {
                balances[msg.sender] -= _amount;
            }
        }
    }

    receive() external payable {}
}

