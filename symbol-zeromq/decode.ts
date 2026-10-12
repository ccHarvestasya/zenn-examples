import { Hash256 } from "symbol-sdk";
import { models } from "symbol-sdk/symbol";
import { parseTopic, type Topic } from "./topics.ts";

export type Event = {
  topic: Topic;
  address?: string;
  data: object;
};

function expectParts(frames: Buffer[], count: number): void {
  if (frames.length !== count)
    throw new Error(`Expected ${count} frames, got ${frames.length}`);
}

function expectBytes(frame: Buffer, size: number): void {
  if (frame.length !== size)
    throw new Error(`Expected ${size} bytes, got ${frame.length}`);
}

function hash(frame: Buffer): string {
  expectBytes(frame, 32);
  return new Hash256(frame).toString();
}

function height(frame: Buffer): string {
  expectBytes(frame, 8);
  return frame.readBigUInt64LE().toString();
}

export function decodeMessage(parts: readonly Uint8Array[]): Event {
  const frames = parts.map((part) => Buffer.from(part));
  if (!frames.length) throw new Error("Empty message");
  const topic = parseTopic(frames[0]);
  let data: object;

  switch (topic.topic) {
    case "block": {
      expectParts(frames, 4);
      const header = frames[1];
      if (header.length < 4 || header.readUInt32LE() < header.length) {
        throw new Error("Invalid block header size");
      }
      // 通知にはヘッダーだけが入る。複製したBufferのsizeを補正してSDKで読む。
      header.writeUInt32LE(header.length);
      const block = models.BlockFactory.deserialize(Uint8Array.from(header));
      if (block.size !== header.length || block.transactions.length !== 0) {
        throw new Error("Expected a block header without transactions");
      }
      data = {
        block: block.toJson(),
        meta: { hash: hash(frames[2]), generationHash: hash(frames[3]) },
      };
      break;
    }
    case "finalizedBlock": {
      expectParts(frames, 2);
      expectBytes(frames[1], 48);
      data = models.FinalizedBlockHeader.deserialize(
        Uint8Array.from(frames[1]),
      ).toJson();
      break;
    }
    case "dropBlocks": {
      expectParts(frames, 2);
      data = { height: height(frames[1]) };
      break;
    }
    case "confirmedAdded":
    case "unconfirmedAdded":
    case "partialAdded": {
      expectParts(frames, 5);
      const bytes = frames[1];
      if (bytes.length < 4 || bytes.readUInt32LE() !== bytes.length) {
        throw new Error("Invalid transaction size");
      }
      const transaction = models.TransactionFactory.deserialize(
        Uint8Array.from(bytes),
      );
      if (transaction.size !== bytes.length)
        throw new Error("Unexpected transaction length");
      data = {
        transaction: transaction.toJson(),
        meta: {
          hash: hash(frames[2]),
          merkleComponentHash: hash(frames[3]),
          height: height(frames[4]),
        },
      };
      break;
    }
    case "unconfirmedRemoved":
    case "partialRemoved": {
      expectParts(frames, 2);
      data = { meta: { hash: hash(frames[1]) } };
      break;
    }
    case "cosignature": {
      expectParts(frames, 2);
      expectBytes(frames[1], 136);
      data = models.DetachedCosignature.deserialize(
        Uint8Array.from(frames[1]),
      ).toJson();
      break;
    }
    case "status": {
      expectParts(frames, 2);
      expectBytes(frames[1], 44);
      const status = frames[1];
      const code = status.readUInt32LE(40);
      data = {
        hash: hash(status.subarray(0, 32)),
        deadline: status.readBigUInt64LE(32).toString(),
        code,
        codeHex: `0x${code.toString(16).padStart(8, "0").toUpperCase()}`,
      };
      break;
    }
  }
  return { ...topic, data };
}
