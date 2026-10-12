import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { XPublisher, Subscriber } from "zeromq";
import { fixtureMessages } from "../fixtures.ts";
import { topicPrefix } from "../topics.ts";
import { decodeMessage } from "../decode.ts";

test(
  "actual ZeroMQ filters by raw address and delivers multipart frames",
  { timeout: 10000 },
  async () => {
    const publisher = new XPublisher({ linger: 0, receiveTimeout: 5000 });
    const subscriber = new Subscriber({ linger: 0, receiveTimeout: 5000 });
    try {
      await publisher.bind("tcp://127.0.0.1:*");
      const fixture = fixtureMessages();
      const prefix = topicPrefix(`confirmedAdded/${fixture.address}`);
      subscriber.subscribe(prefix);
      subscriber.connect(publisher.lastEndpoint!);
      const [subscription] = await publisher.receive();
      assert.equal(subscription[0], 1);
      assert.deepEqual(subscription.subarray(1), prefix);
      const valid = fixture.messages[3];
      await publisher.send([
        fixture.topic("confirmedAdded", fixture.otherAddress),
        ...valid.slice(1),
      ]);
      await publisher.send(valid);
      const frames = await subscriber.receive();
      assert.equal(decodeMessage(frames).address, fixture.address.toString());
      assert.deepEqual(frames[0], prefix);
    } finally {
      subscriber.close();
      publisher.close();
    }
  },
);

test(
  "monitor skips a malformed notification, then prints a valid event and exits on SIGINT",
  { timeout: 10000 },
  async () => {
    const publisher = new XPublisher({ linger: 0, receiveTimeout: 5000 });
    let child: ReturnType<typeof spawn> | undefined;
    try {
      await publisher.bind("tcp://127.0.0.1:*");
      child = spawn(
        process.execPath,
        [
          fileURLToPath(new URL("../monitor.ts", import.meta.url)),
          publisher.lastEndpoint!,
          "status",
        ],
        { stdio: ["ignore", "pipe", "pipe"] },
      );
      let errors = "";
      child.stderr!.on("data", (chunk) => {
        errors += chunk;
      });
      const printed = new Promise<string>((resolve, reject) => {
        let output = "";
        child!.stdout!.on("data", (chunk) => {
          output += chunk;
          if (output.includes("\n")) resolve(output.split("\n")[0]);
        });
        child!.once("error", reject);
        child!.once("exit", () =>
          reject(new Error(`Monitor exited before a notification: ${errors}`)),
        );
      });
      const [subscription] = await publisher.receive();
      assert.deepEqual(subscription, Buffer.from([1, 0x73]));
      const valid = fixtureMessages().messages[9];
      await publisher.send([valid[0], Buffer.alloc(43)]);
      await publisher.send(valid);
      const event = JSON.parse(await printed);
      assert.equal(event.topic, "status");
      assert.equal(event.data.codeHex, "0x80430001");
      const exited = once(child, "exit");
      child.kill("SIGINT");
      const [code] = await exited;
      assert.equal(code, 0);
      assert.match(errors, /Skipped malformed message/);
    } finally {
      if (child && child.exitCode === null) child.kill("SIGKILL");
      publisher.close();
    }
  },
);
