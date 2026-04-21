// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract AimiMicropayChannel {
    using SafeERC20 for IERC20;

    bytes32 public constant VOUCHER_DOMAIN_HASH = keccak256("AIMICROPAY_V1");
    bytes32 public constant CANCEL_DOMAIN_HASH = keccak256("AIMICROPAY_CANCEL_V1");

    struct PaymentChannel {
        address buyer;
        address seller;
        address token;
        uint256 totalDeposit;
        uint64 nonce;
        uint64 expiresAt;
        bool isActive;
    }

    mapping(bytes32 => PaymentChannel) public paymentChannels;

    event ChannelInitialized(
        bytes32 indexed channelId,
        address indexed buyer,
        address indexed seller,
        address token,
        uint256 totalDeposit,
        uint64 expiresAt
    );

    event ChannelClaimed(
        bytes32 indexed channelId,
        address indexed seller,
        uint256 amount,
        uint256 refund,
        uint64 nonce
    );

    event ChannelClosed(bytes32 indexed channelId, address indexed buyer, uint256 refundedAmount);

    event ChannelCancelled(
        bytes32 indexed channelId,
        address indexed buyer,
        address indexed seller,
        uint256 refundedAmount
    );

    error InvalidSeller();
    error InvalidToken();
    error InvalidDepositAmount();
    error InvalidClaimAmount();
    error ExpiryMustBeInFuture();
    error ChannelInactive();
    error ChannelAlreadyActive();
    error ChannelExpired();
    error ChannelStillLocked();
    error ClaimExceedsDeposit();
    error NonceMustIncrease();
    error VoucherExpiryMismatch();
    error RequestDeadlineExpired();
    error InvalidVoucherSigner();
    error InvalidCancelSigner();
    error UnauthorizedCaller();

    function channelIdOf(address buyer, address seller, address token) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(buyer, seller, token));
    }

    function getVoucherDigest(
        bytes32 channelId,
        address buyer,
        address seller,
        address token,
        uint256 amount,
        uint64 voucherNonce,
        uint64 voucherExpiresAt,
        uint64 requestDeadline,
        bytes32 requestDigest
    ) public view returns (bytes32) {
        return keccak256(
            abi.encode(
                VOUCHER_DOMAIN_HASH,
                block.chainid,
                address(this),
                channelId,
                buyer,
                seller,
                token,
                amount,
                voucherNonce,
                voucherExpiresAt,
                requestDeadline,
                requestDigest
            )
        );
    }

    function getCancelDigest(
        bytes32 channelId,
        address buyer,
        address seller,
        address token,
        uint256 totalDeposit,
        uint64 expiresAt
    ) public view returns (bytes32) {
        return keccak256(
            abi.encode(
                CANCEL_DOMAIN_HASH,
                block.chainid,
                address(this),
                channelId,
                buyer,
                seller,
                token,
                totalDeposit,
                expiresAt
            )
        );
    }

    function initializeChannel(address seller, address token, uint256 totalDeposit, uint64 expiresAt)
        external
        returns (bytes32 channelId)
    {
        if (seller == address(0) || seller == msg.sender) revert InvalidSeller();
        if (token == address(0)) revert InvalidToken();
        if (totalDeposit == 0) revert InvalidDepositAmount();
        if (expiresAt <= block.timestamp) revert ExpiryMustBeInFuture();

        channelId = channelIdOf(msg.sender, seller, token);
        PaymentChannel storage channel = paymentChannels[channelId];
        if (channel.isActive) revert ChannelAlreadyActive();

        IERC20(token).safeTransferFrom(msg.sender, address(this), totalDeposit);

        channel.buyer = msg.sender;
        channel.seller = seller;
        channel.token = token;
        channel.totalDeposit = totalDeposit;
        channel.nonce = 0;
        channel.expiresAt = expiresAt;
        channel.isActive = true;

        emit ChannelInitialized(channelId, msg.sender, seller, token, totalDeposit, expiresAt);
    }

    function claimPayment(
        bytes32 channelId,
        uint256 amount,
        uint64 voucherNonce,
        uint64 voucherExpiresAt,
        uint64 requestDeadline,
        bytes32 requestDigest,
        bytes calldata buyerSignature
    ) external {
        PaymentChannel storage channel = paymentChannels[channelId];
        if (!channel.isActive) revert ChannelInactive();
        if (msg.sender != channel.seller) revert UnauthorizedCaller();
        if (amount == 0) revert InvalidClaimAmount();
        if (voucherNonce <= channel.nonce) revert NonceMustIncrease();
        if (voucherExpiresAt != channel.expiresAt) revert VoucherExpiryMismatch();
        if (block.timestamp > channel.expiresAt) revert ChannelExpired();
        if (block.timestamp > requestDeadline) revert RequestDeadlineExpired();
        if (amount > channel.totalDeposit) revert ClaimExceedsDeposit();

        bytes32 digest = getVoucherDigest(
            channelId,
            channel.buyer,
            channel.seller,
            channel.token,
            amount,
            voucherNonce,
            voucherExpiresAt,
            requestDeadline,
            requestDigest
        );
        address recoveredBuyer = ECDSA.recover(digest, buyerSignature);
        if (recoveredBuyer != channel.buyer) revert InvalidVoucherSigner();

        uint256 available = channel.totalDeposit;
        uint256 refund = available - amount;

        channel.totalDeposit = 0;
        channel.nonce = voucherNonce;
        channel.isActive = false;

        IERC20 token = IERC20(channel.token);
        if (amount > 0) {
            token.safeTransfer(channel.seller, amount);
        }
        if (refund > 0) {
            token.safeTransfer(channel.buyer, refund);
        }

        emit ChannelClaimed(channelId, channel.seller, amount, refund, voucherNonce);
    }

    function closeChannel(bytes32 channelId) external {
        PaymentChannel storage channel = paymentChannels[channelId];
        if (!channel.isActive) revert ChannelInactive();
        if (msg.sender != channel.buyer) revert UnauthorizedCaller();
        if (block.timestamp < channel.expiresAt) revert ChannelStillLocked();

        uint256 refundable = channel.totalDeposit;
        channel.totalDeposit = 0;
        channel.isActive = false;

        if (refundable > 0) {
            IERC20(channel.token).safeTransfer(channel.buyer, refundable);
        }

        emit ChannelClosed(channelId, channel.buyer, refundable);
    }

    function cancelChannel(bytes32 channelId, bytes calldata buyerSignature, bytes calldata sellerSignature) external {
        PaymentChannel storage channel = paymentChannels[channelId];
        if (!channel.isActive) revert ChannelInactive();
        if (msg.sender != channel.buyer && msg.sender != channel.seller) revert UnauthorizedCaller();

        bytes32 digest = getCancelDigest(
            channelId,
            channel.buyer,
            channel.seller,
            channel.token,
            channel.totalDeposit,
            channel.expiresAt
        );
        if (ECDSA.recover(digest, buyerSignature) != channel.buyer) revert InvalidCancelSigner();
        if (ECDSA.recover(digest, sellerSignature) != channel.seller) revert InvalidCancelSigner();

        uint256 refundable = channel.totalDeposit;
        channel.totalDeposit = 0;
        channel.isActive = false;

        if (refundable > 0) {
            IERC20(channel.token).safeTransfer(channel.buyer, refundable);
        }

        emit ChannelCancelled(channelId, channel.buyer, channel.seller, refundable);
    }
}
