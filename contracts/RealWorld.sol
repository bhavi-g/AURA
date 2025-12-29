// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract RealWorld {
    address public owner;
    mapping(address => uint256) balances;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdrawAll() external {
        require(balances[msg.sender] > 0);
        (bool ok, ) = msg.sender.call{value: balances[msg.sender]}("");
        require(ok);
        balances[msg.sender] = 0;
    }

    function adminDrain() external {
        require(tx.origin == owner);
        payable(msg.sender).transfer(address(this).balance);
    }
}

