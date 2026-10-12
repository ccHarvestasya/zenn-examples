import { Subscriber } from "zeromq";
import { decodeMessage } from "./decode.ts";
import { topicPrefix } from "./topics.ts";

const endpoint = process.argv[2] ?? "tcp://127.0.0.1:7902";
const topics = process.argv.slice(3);
if (!topics.length) topics.push("block");
// 不正なチャンネル指定は、ソケットを作る前にエラーにする。
const prefixes = topics.map(topicPrefix);
const socket = new Subscriber({ connectTimeout: 3000, linger: 0 });
const stop = () => socket.close();
process.once("SIGINT", stop);
process.once("SIGTERM", stop);

try {
  for (const prefix of prefixes) socket.subscribe(prefix);
  socket.connect(endpoint);
  // connect()は接続完了や購読の反映を待つAPIではない。
  console.error(`Subscriptions configured: ${endpoint} [${topics.join(", ")}]`);
  for await (const frames of socket) {
    try {
      console.log(JSON.stringify(decodeMessage(frames)));
    } catch (error) {
      console.error("Skipped malformed message:", error);
    }
  }
} catch (error) {
  if (!socket.closed) throw error;
} finally {
  if (!socket.closed) socket.close();
  process.removeListener("SIGINT", stop);
  process.removeListener("SIGTERM", stop);
}
