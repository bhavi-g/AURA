pragma solidity ^0.8.0;

contract AccessControl {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    // ❌ Missing access control
    function withdrawAll() external {
        payable(msg.sender).transfer(address(this).balance);
    }

    receive() external payable {}
}
