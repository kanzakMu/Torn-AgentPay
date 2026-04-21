// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockUSDT6 is ERC20 {
    constructor(address initialHolder, uint256 initialSupply) ERC20("Mock USDT", "USDT") {
        _mint(initialHolder, initialSupply);
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }
}
