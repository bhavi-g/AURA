// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract ModifierVault {
    address public owner;
    mapping(address => uint256) balances;

    modifier onlyOwner() {
        require(tx.origin == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Too much");
        balances[msg.sender] -= amount;
        payable(msg.sender).call{value: amount}("");
    }

    function sweep() external onlyOwner {
        payable(msg.sender).transfer(address(this).balance);
    }
}

