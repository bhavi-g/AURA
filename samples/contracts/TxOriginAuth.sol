// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;
contract Wallet {
    address public owner;
    constructor(){ owner = msg.sender; }
    function withdraw(address payable to) external {
        require(tx.origin == owner, "not owner");
        to.transfer(address(this).balance);
    }
    receive() external payable {}
}
