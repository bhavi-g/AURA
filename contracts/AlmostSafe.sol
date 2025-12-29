// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract AlmostSafe {
    mapping(address => uint256) balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;
        _unsafeSend(msg.sender, amount);
    }

    function _unsafeSend(address to, uint256 amount) internal {
        (bool ok, ) = to.call{value: amount}("");
        require(ok);
    }
}

