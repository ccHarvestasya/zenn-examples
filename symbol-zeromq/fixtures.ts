// Catapultの送信実装に合わせて構築したローカル検証用データ。
// 実Brokerから採取したデータでも、署名済みの実取引でもない。
import { PublicKey } from "symbol-sdk";
import { Network, SymbolFacade, models } from "symbol-sdk/symbol";
import {
  blockMarkers,
  transactionMarkers,
  type TransactionTopic,
} from "./topics.ts";

export function fixtureMessages() {
  const facade = new SymbolFacade(Network.TESTNET);
  const publicKey = new PublicKey("11".repeat(32));
  const address = Network.TESTNET.publicKeyToAddress(publicKey);
  const otherAddress = Network.TESTNET.publicKeyToAddress(
    new PublicKey("22".repeat(32)),
  );
  const tx = facade.transactionFactory.create({
    type: "transfer_transaction_v1",
    signerPublicKey: publicKey,
    deadline: 7_200_000n,
    fee: 0n,
    recipientAddress: address,
    mosaics: [],
    message: new Uint8Array(),
  });
  const inner = facade.transactionFactory.createEmbedded({
    type: "transfer_transaction_v1",
    signerPublicKey: publicKey,
    recipientAddress: address,
    mosaics: [],
    message: new Uint8Array(),
  });
  const partial = facade.transactionFactory.create({
    type: "aggregate_bonded_transaction_v3",
    signerPublicKey: publicKey,
    deadline: 7_200_000n,
    fee: 0n,
    transactionsHash: SymbolFacade.hashEmbeddedTransactions([inner]),
    transactions: [inner],
  });
  const entityHash = Buffer.alloc(32, 0xaa);
  const merkleHash = Buffer.alloc(32, 0xbb);
  const height = Buffer.alloc(8);
  height.writeBigUInt64LE(123n);
  const topic = (name: TransactionTopic, addr = address) =>
    Buffer.concat([Buffer.from([transactionMarkers[name]]), addr.bytes]);

  const block = new models.NormalBlockV1();
  block.network = models.NetworkType.TESTNET;
  block.height = new models.Height(123n);
  const headerSize = block.size;
  block.transactions.push(tx);
  const blockHeader = Buffer.from(block.serialize().subarray(0, headerSize));

  const finalized = new models.FinalizedBlockHeader();
  finalized.round.epoch = new models.FinalizationEpoch(1);
  finalized.round.point = new models.FinalizationPoint(2);
  finalized.height = new models.Height(123n);
  finalized.hash = new models.Hash256(entityHash);

  const cosignature = new models.DetachedCosignature();
  cosignature.signerPublicKey = new models.PublicKey(publicKey.bytes);
  cosignature.parentHash = new models.Hash256(entityHash);

  const status = Buffer.alloc(44);
  entityHash.copy(status);
  status.writeBigUInt64LE(BigInt(tx.deadline.value), 32);
  status.writeUInt32LE(0x80430001, 40); // Failure_Core_Past_Deadline

  const added = (name: TransactionTopic, confirmed = false) => [
    topic(name),
    Buffer.from((name === "partialAdded" ? partial : tx).serialize()),
    entityHash,
    merkleHash,
    confirmed ? height : Buffer.alloc(8),
  ];
  const messages: Buffer[][] = [
    [blockMarkers.block, blockHeader, entityHash, merkleHash],
    [blockMarkers.finalizedBlock, Buffer.from(finalized.serialize())],
    [blockMarkers.dropBlocks, height],
    added("confirmedAdded", true),
    added("unconfirmedAdded"),
    [topic("unconfirmedRemoved"), entityHash],
    added("partialAdded"),
    [topic("partialRemoved"), entityHash],
    [topic("cosignature"), Buffer.from(cosignature.serialize())],
    [topic("status"), status],
  ];
  return { messages, address, otherAddress, tx, topic };
}
