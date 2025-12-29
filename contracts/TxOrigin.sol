pragma solidity ^0.8.0;

contract TxOrigin {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    // ❌ Vulnerable: uses tx.origin for authorization
    function withdrawAll() external {
        require(tx.origin == owner, "Not owner");
        payable(msg.sender).transfer(address(this).balance);
    }

    receive() external payable {}
}
