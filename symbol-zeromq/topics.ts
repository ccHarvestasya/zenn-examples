import { Address, Network } from "symbol-sdk/symbol";

// 8バイトの整数マーカーを、通信上のリトルエンディアン順で記述。
export const blockMarkers = {
  block: Buffer.from("496ACA80E4D8F29F", "hex"),
  finalizedBlock: Buffer.from("5479CE31A032484D", "hex"),
  dropBlocks: Buffer.from("B0B025EE8AD6205C", "hex"),
};

export const transactionMarkers = {
  confirmedAdded: 0x61,
  unconfirmedAdded: 0x75,
  unconfirmedRemoved: 0x72,
  partialAdded: 0x70,
  partialRemoved: 0x71,
  cosignature: 0x63,
  status: 0x73,
};

export type BlockTopic = keyof typeof blockMarkers;
export type TransactionTopic = keyof typeof transactionMarkers;
export type Topic = BlockTopic | TransactionTopic;

export function topicPrefix(topic: string): Buffer {
  const [name, address, ...extra] = topic.split("/");
  if (extra.length || address === "")
    throw new Error(`Invalid topic: ${topic}`);
  if (Object.hasOwn(blockMarkers, name)) {
    if (address) throw new Error(`${name} does not accept an address`);
    return Buffer.from(blockMarkers[name as BlockTopic]);
  }
  if (!Object.hasOwn(transactionMarkers, name))
    throw new Error(`Unknown topic: ${name}`);
  const marker = Buffer.from([transactionMarkers[name as TransactionTopic]]);
  if (!address) return marker;
  if (
    !Network.NETWORKS.some((network) => network.isValidAddressString(address))
  ) {
    throw new Error("Use a valid Mainnet or Testnet address without hyphens");
  }
  return Buffer.concat([marker, new Address(address).bytes]);
}

export function parseTopic(frame: Buffer): { topic: Topic; address?: string } {
  for (const [name, marker] of Object.entries(blockMarkers)) {
    if (frame.equals(marker)) return { topic: name as BlockTopic };
  }
  // Brokerは関連アドレスごとに、1バイトのマーカー＋24バイトのアドレスを送る。
  if (frame.length !== 25)
    throw new Error("Unknown marker or invalid topic length");
  for (const [name, marker] of Object.entries(transactionMarkers)) {
    if (frame[0] === marker) {
      return {
        topic: name as TransactionTopic,
        address: new Address(frame.subarray(1)).toString(),
      };
    }
  }
  throw new Error("Unknown transaction marker");
}
