/**
 * Check wallet address derived from mnemonic
 */

const { MeshWallet, BlockfrostProvider } = require('@meshsdk/core');

async function checkWallet() {
    const networkId = 0; // Preprod testnet
    const blockfrostApiKey = process.env.BLOCKFROST_API_KEY || 'preprodS0e1FdYRFcseIJjzxWbpxlhXbtdHEja3';
    const mnemonic = process.env.WALLET_MNEMONIC;

    if (!mnemonic) {
        console.log('WALLET_MNEMONIC not provided');
        return;
    }

    const provider = new BlockfrostProvider(blockfrostApiKey);

    const wallet = new MeshWallet({
        networkId: networkId,
        fetcher: provider,
        submitter: provider,
        key: {
            type: 'mnemonic',
            words: mnemonic.split(' '),
        },
    });

    console.log('=== Wallet Info ===');

    // Get unused addresses (what MeshSDK uses)
    const unusedAddresses = await wallet.getUnusedAddresses();
    console.log('Unused Addresses:', unusedAddresses);

    // Get used addresses
    const usedAddresses = await wallet.getUsedAddresses();
    console.log('Used Addresses:', usedAddresses);

    // Get all addresses
    const rewardAddresses = await wallet.getRewardAddresses();
    console.log('Reward Addresses:', rewardAddresses);

    // Get UTXOs
    const utxos = await wallet.getUtxos();
    console.log('UTXOs:', utxos.length, 'found');

    if (utxos.length > 0) {
        console.log('First UTXO:', JSON.stringify(utxos[0], null, 2));
    }
}

checkWallet().catch(console.error);