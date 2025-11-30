/**
 * Send ADA Reward Script
 * Uses MeshSDK for wallet/tx but direct Blockfrost API for UTXOs
 * (bypasses MeshSDK's buggy UTXO fetching)
 */

const { MeshWallet, BlockfrostProvider, Transaction } = require('@meshsdk/core');
const https = require('https');

// Fetch UTXOs directly from Blockfrost API (bypasses MeshSDK bugs)
function fetchUtxosFromBlockfrost(address, apiKey) {
    return new Promise((resolve, reject) => {
        const hostname = apiKey.startsWith('preprod')
            ? 'cardano-preprod.blockfrost.io'
            : apiKey.startsWith('preview')
            ? 'cardano-preview.blockfrost.io'
            : 'cardano-mainnet.blockfrost.io';

        const options = {
            hostname: hostname,
            path: `/api/v0/addresses/${address}/utxos`,
            method: 'GET',
            headers: { 'project_id': apiKey },
            timeout: 30000
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                if (res.statusCode !== 200) {
                    reject(new Error(`Blockfrost API error: ${res.statusCode} - ${data}`));
                    return;
                }
                try {
                    const rawUtxos = JSON.parse(data);
                    // Convert to MeshSDK UTxO format
                    const utxos = rawUtxos.map(utxo => ({
                        input: {
                            outputIndex: utxo.output_index,
                            txHash: utxo.tx_hash
                        },
                        output: {
                            address: address,
                            amount: utxo.amount.map(a => ({
                                unit: a.unit,
                                quantity: a.quantity
                            }))
                        }
                    }));
                    resolve(utxos);
                } catch (e) {
                    reject(new Error(`Parse error: ${e.message}`));
                }
            });
        });

        req.on('error', reject);
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timed out'));
        });
        req.end();
    });
}

async function sendADAReward(recipientAddress, amountLovelace, mnemonic, blockfrostApiKey) {
    try {
        const networkId = 0; // Preprod testnet

        if (!mnemonic) {
            console.log(JSON.stringify({ success: false, error: 'Mnemonic not provided' }));
            process.exit(1);
        }

        if (!blockfrostApiKey) {
            console.log(JSON.stringify({ success: false, error: 'Blockfrost API key not provided' }));
            process.exit(1);
        }

        // Initialize Blockfrost provider
        const blockfrostProvider = new BlockfrostProvider(blockfrostApiKey);

        // Create MeshWallet from mnemonic
        const wallet = new MeshWallet({
            networkId: networkId,
            fetcher: blockfrostProvider,
            submitter: blockfrostProvider,
            key: {
                type: 'mnemonic',
                words: mnemonic.split(' ')
            }
        });

        // Get wallet address
        //addr_test1qrdcyfry5wzlefwzaqlrj8x6epzce6rhunwdntpg39ds0tlal6a39g8umszr36axxktf787x90wfk3ahwgt2c4efpdjq5tuzn6
        //addr_test1qrdcyfry5wzlefwzaqlrj8x6epzce6rhunwdntpg39ds0tlal6a39g8umszr36axxktf787x90wfk3ahwgt2c4efpdjq5tuzn6
        const senderAddress = wallet.getChangeAddress();
        console.error('Debug: Sender address:', senderAddress);

        // Use direct https fetch for UTXOs (bypasses MeshSDK's buggy UTXO fetching)
        console.error('Debug: Fetching UTXOs via direct Blockfrost API...');
        const utxos = await fetchUtxosFromBlockfrost(senderAddress, blockfrostApiKey);
        console.error('Debug: UTXOs found:', utxos.length);

        if (!utxos || utxos.length === 0) {
            console.log(JSON.stringify({
                success: false,
                error: 'No UTXOs available in wallet',
                address: senderAddress
            }));
            process.exit(1);
        }

        // Build transaction with UTXOs set explicitly
        const tx = new Transaction({ initiator: wallet });
        tx.setTxInputs(utxos);
        tx.sendLovelace(recipientAddress, amountLovelace.toString());
        tx.setChangeAddress(senderAddress);

        // Build the transaction
        console.error('Debug: Building transaction...');
        const unsignedTx = await tx.build();

        // Sign the transaction
        console.error('Debug: Signing transaction...');
        const signedTx = await wallet.signTx(unsignedTx);

        // Submit the transaction
        console.error('Debug: Submitting transaction...');
        const txHash = await wallet.submitTx(signedTx);

        // Build explorer URL
        const explorerUrl = `https://preprod.cardanoscan.io/transaction/${txHash}`;

        // Output result as JSON
        console.log(JSON.stringify({
            success: true,
            tx_hash: txHash,
            explorer_url: explorerUrl,
            sender_address: senderAddress,
            recipient_address: recipientAddress,
            amount_lovelace: amountLovelace
        }));

    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            error: error.message || String(error)
        }));
        process.exit(1);
    }
}

// Parse command line arguments
const args = process.argv.slice(2);
if (args.length < 4) {
    console.log(JSON.stringify({
        success: false,
        error: 'Usage: node send_ada_reward.js <recipient_address> <amount_lovelace> <mnemonic> <blockfrost_api_key>'
    }));
    process.exit(1);
}

const recipientAddress = args[0];
const amountLovelace = parseInt(args[1], 10);
const mnemonicArg = args[2];
const blockfrostApiKeyArg = args[3];

if (isNaN(amountLovelace) || amountLovelace <= 0) {
    console.log(JSON.stringify({
        success: false,
        error: 'Invalid amount. Must be a positive integer (lovelace)'
    }));
    process.exit(1);
}

// Run the function
sendADAReward(recipientAddress, amountLovelace, mnemonicArg, blockfrostApiKeyArg)
    .catch(err => {
        console.log(JSON.stringify({ success: false, error: err.message }));
        process.exit(1);
    });