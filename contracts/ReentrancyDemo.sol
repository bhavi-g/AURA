// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ReentrancyDemo {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "nothing");
        (bool ok, ) = msg.sender.call{value: amount}(""); // vulnerable pattern
        require(ok, "send failed");
        balances[msg.sender] = 0; // update after external call
    }
}
