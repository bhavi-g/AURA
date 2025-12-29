pragma solidity ^0.8.0;

contract Vault {
    mapping(address => uint256) public balances;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");

        // ❌ Reentrancy risk
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "ETH transfer failed");

        balances[msg.sender] -= amount;
    }

    function emergencyWithdraw() external {
        // ❌ tx.origin auth bug
        require(tx.origin == owner, "Not authorized");

        // ❌ arbitrary send
        payable(msg.sender).transfer(address(this).balance);
    }
}
