import { AFHClient } from "../src";

const client = new AFHClient({ baseUrl: "http://127.0.0.1:8000" });

async function main() {
  const task = await client.createTask("default");

  await client.streamChat(
    {
      task_id: task.task_id,
      message: "基于知识库和商品库，推荐本次活动上架商品",
      knowledge_ids: [],
    },
    {
      onText: (chunk) => console.log(chunk),
      onEvent: (event) => {
        if (event.type === "risks") console.log("risk event", event.items);
      },
    },
  );
}

void main();
