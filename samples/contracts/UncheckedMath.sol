// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;
contract Counter {
    uint256 public x;
    function inc(uint256 y) external { x += y; } // potential overflow in old compilers
}
