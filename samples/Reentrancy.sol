// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract ReentrancyDemo {
    mapping(address=>uint) public bal;
    function deposit() external payable { bal[msg.sender]+=msg.value; }
    function withdraw() external {
        uint amt = bal[msg.sender];
        (bool ok,) = msg.sender.call{value: amt}(""); // bad pattern
        require(ok);
        bal[msg.sender]=0;
    }
}
