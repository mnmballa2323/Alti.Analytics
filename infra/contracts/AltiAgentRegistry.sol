// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title AltiAgentRegistry
 * @dev Epic 19: The Web3 Autonomous Marketplace for the Alti.Analytics Swarm.
 * Allows independent data scientists to publish specialized sub-agents.
 * The Alti Swarm automatically compensates creators in USDC when their 
 * agent is invoked to solve complex enterprise edge cases.
 */
contract AltiAgentRegistry is Ownable, ReentrancyGuard {
    
    struct SubAgent {
        string ipfsHash;        // Pointer to the Agent's Python/Wasm executable & weights
        string capabilityTag;   // e.g., "SUPPLY_CHAIN_OPT", "ESG_REPORTING"
        address creator;        // Wallet of the data scientist
        uint256 invocationFee;  // Cost in USDC/Stablecoin to invoke this agent once
        bool isActive;
        uint256 totalInvocations;
    }

    IERC20 public usdcToken;
    mapping(uint256 => SubAgent) public registry;
    uint256 public nextAgentId;
    
    event AgentPublished(uint256 indexed agentId, string capabilityTag, address creator);
    event AgentInvoked(uint256 indexed agentId, address indexed invoker, uint256 feePaid);

    constructor(address _usdcTokenAddress) Ownable(msg.sender) {
        usdcToken = IERC20(_usdcTokenAddress);
    }

    /**
     * @dev Allows anyone to publish a verifiable LangGraph Sub-Agent.
     */
    function publishAgent(string memory _ipfsHash, string memory _capabilityTag, uint256 _invocationFee) external {
        registry[nextAgentId] = SubAgent({
            ipfsHash: _ipfsHash,
            capabilityTag: _capabilityTag,
            creator: msg.sender,
            invocationFee: _invocationFee,
            isActive: true,
            totalInvocations: 0
        });
        
        emit AgentPublished(nextAgentId, _capabilityTag, msg.sender);
        nextAgentId++;
    }

    /**
     * @dev The core Alti.Analytics Swarm invokes this function to autonomously 
     * lease specialized intelligence from the decentralized network.
     */
    function invokeAgent(uint256 _agentId) external nonReentrant {
        SubAgent storage agent = registry[_agentId];
        require(agent.isActive, "Agent is deactivated");
        
        // Transfer the USDC fee directly from the Swarm's treasury to the Creator
        require(
            usdcToken.transferFrom(msg.sender, agent.creator, agent.invocationFee),
            "USDC Payment to Creator Failed"
        );
        
        agent.totalInvocations++;
        
        emit AgentInvoked(_agentId, msg.sender, agent.invocationFee);
    }
    
    /**
     * @dev Allows the Creator to update or patch their agent logic on IPFS.
     */
    function updateAgentIPFS(uint256 _agentId, string memory _newIpfsHash) external {
        SubAgent storage agent = registry[_agentId];
        require(msg.sender == agent.creator, "Only the creator can patch this agent");
        agent.ipfsHash = _newIpfsHash;
    }
}
