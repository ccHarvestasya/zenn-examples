import { XPublisher, Subscriber } from "zeromq";
import { fixtureMessages } from "./fixtures.ts";
import { decodeMessage } from "./decode.ts";

// XPUBで購読の反映を待ち、起動直後の通知欠落をデモから除く。
const publisher = new XPublisher({ linger: 0, receiveTimeout: 5000 });
const subscriber = new Subscriber({ linger: 0, receiveTimeout: 5000 });
try {
  await publisher.bind("tcp://127.0.0.1:*");
  subscriber.subscribe();
  subscriber.connect(publisher.lastEndpoint!);
  const [subscription] = await publisher.receive();
  if (subscription[0] !== 1) throw new Error("Expected a subscription");
  const { messages } = fixtureMessages();
  console.log("Local fixture demo (not a live Broker)");
  for (const message of messages) {
    await publisher.send(message);
    console.log(JSON.stringify(decodeMessage(await subscriber.receive())));
  }
} finally {
  subscriber.close();
  publisher.close();
}
