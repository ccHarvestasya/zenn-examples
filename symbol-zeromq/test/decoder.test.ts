import assert from "node:assert/strict";
import test from "node:test";
import { models } from "symbol-sdk/symbol";
import { decodeMessage } from "../decode.ts";
import { fixtureMessages } from "../fixtures.ts";
import { blockMarkers, topicPrefix } from "../topics.ts";

const fixture = fixtureMessages();
const names = [
  "block",
  "finalizedBlock",
  "dropBlocks",
  "confirmedAdded",
  "unconfirmedAdded",
  "unconfirmedRemoved",
  "partialAdded",
  "partialRemoved",
  "cosignature",
  "status",
];

test("all ten message kinds decode and their original buffers remain intact", () => {
  fixture.messages.forEach((frames, index) => {
    const originals = frames.map((frame) => Buffer.from(frame));
    const event = decodeMessage(frames);
    assert.equal(event.topic, names[index]);
    frames.forEach((frame, i) => assert.deepEqual(frame, originals[i]));
  });
});

test("header-only block ignores the original full block size without inventing transactions", () => {
  const frames = fixture.messages[0];
  assert.ok(frames[1].readUInt32LE() > frames[1].length);
  const event = decodeMessage(frames);
  const data = event.data as {
    block: { height: string; transactions: unknown[] };
  };
  assert.equal(data.block.height, "123");
  assert.deepEqual(data.block.transactions, []);
  const importance = new models.ImportanceBlockV1();
  importance.height = new models.Height(456n);
  const importanceEvent = decodeMessage([
    blockMarkers.block,
    importance.serialize(),
    frames[2],
    frames[3],
  ]);
  assert.equal(
    (importanceEvent.data as { block: { height: string } }).block.height,
    "456",
  );
});

test("partialAdded contains an Aggregate Bonded, while unconfirmed height is zero", () => {
  const partial = decodeMessage(fixture.messages[6]);
  assert.equal(
    (partial.data as { transaction: { type: number } }).transaction.type,
    0x4241,
  );
  const unconfirmed = decodeMessage(fixture.messages[4]);
  assert.equal(
    (unconfirmed.data as { meta: { height: string } }).meta.height,
    "0",
  );
});

test("detached cosignature retains parentHash and requires 136 bytes", () => {
  const frames = fixture.messages[8];
  const event = decodeMessage(frames);
  assert.equal(
    (event.data as { parentHash: string }).parentHash,
    "AA".repeat(32),
  );
  assert.throws(
    () => decodeMessage([frames[0], frames[1].subarray(0, 104)]),
    /136 bytes/,
  );
});

test("status reads unsigned uint32 at offset 40 and uint64 deadline at offset 32", () => {
  const frames = fixture.messages[9].map((frame) => Buffer.from(frame));
  frames[1].writeBigUInt64LE(9_007_199_254_740_993n, 32);
  assert.deepEqual(decodeMessage(frames).data, {
    hash: "AA".repeat(32),
    deadline: "9007199254740993",
    code: 0x80430001,
    codeHex: "0x80430001",
  });
});

test("topic filters use raw address bytes and distinguish removal from status", () => {
  assert.equal(topicPrefix("unconfirmedRemoved").toString("hex"), "72");
  assert.equal(topicPrefix("status").toString("hex"), "73");
  assert.deepEqual(
    topicPrefix(`confirmedAdded/${fixture.address}`),
    fixture.topic("confirmedAdded"),
  );
  for (const topic of [
    "unknown",
    "block/anything",
    "confirmedAdded/",
    "status/not-an-address",
    "status/a/b",
  ]) {
    assert.throws(() => topicPrefix(topic));
  }
});

test("invalid counts, markers, hashes and truncated payloads fail before yielding an event", () => {
  assert.throws(() => decodeMessage([]), /Empty/);
  assert.throws(() => decodeMessage([Buffer.from([0x61])]), /topic length/);
  assert.throws(() => decodeMessage([Buffer.from([0xff]), Buffer.alloc(44)]));
  for (const frames of fixture.messages) {
    assert.throws(() => decodeMessage(frames.slice(0, -1)));
    const truncated = frames.map((frame, i) =>
      i === 1 ? frame.subarray(0, 1) : frame,
    );
    assert.throws(() => decodeMessage(truncated));
  }
  const removed = fixture.messages[5];
  assert.throws(
    () => decodeMessage([removed[0], Buffer.alloc(31)]),
    /32 bytes/,
  );
});
