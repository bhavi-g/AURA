// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract OverflowDemo { uint8 public c; function add(uint8 a, uint8 b) external { c = a + b; } }
