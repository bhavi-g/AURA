// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;
contract Vault {
    mapping(address => uint) public balances;
    function deposit() external payable { balances[msg.sender] += msg.value; }
    function withdraw() external {
        uint amount = balances[msg.sender];
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] = 0;
    }
}
